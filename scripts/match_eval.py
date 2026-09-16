#!/usr/bin/env python
"""
智能匹配工作流 · 新旧算法对比评测 (match_eval)

在 expohub.db 的**临时副本**上运行（绝不改动原库）：

- 老算法：原 recommendations.py / procurements.py 的内联规则
  （字符集合交叠 + 品类硬匹配 + 最近 500 条截断，无分词/无 IDF/无同义词）
- 新算法：app.modules.matching.workflow 多阶段匹配工作流

金标（关键词金标，透明可复现）：对每条采购需求人工指定核心关键词 K，
「展品名包含 K」即视为该需求的相关展品；同理「展商产品名包含 K」即视为
该展商对需求 P 相关。指标：P@5 / P@10 / MRR + 单次调用耗时。

用法：
    cd expohub-backend && ../.venv/Scripts/python.exe ../scripts/match_eval.py
    cd expohub-backend && ../.venv/Scripts/python.exe ../scripts/match_eval.py D:/path/to/other.db
"""
import os
import shutil
import sys
import time

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "expohub-backend"))
sys.path.insert(0, BACKEND)

# 可传入其他库文件（如演示容器库的副本）；默认开发库 expohub.db
SRC_DB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BACKEND, "expohub.db")
TMP_DB = os.path.join(os.environ.get("TEMP", "."), "match_eval_copy.db")
shutil.copyfile(SRC_DB, TMP_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{TMP_DB}"

from app.models.base import SessionLocal  # noqa: E402
from app.models.category import match_category_score  # noqa: E402
from app.models.procurement import Procurement  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.user import User  # noqa: E402
from app.modules.matching import workflow  # noqa: E402

# ---------- 金标：采购需求 → 核心关键词（人工指定） ----------
GOLD_K = {
    1: ["空调"], 2: ["电饭煲", "电磁炉", "榨汁机", "电热水壶"], 3: ["自动化", "机器人", "产线"],
    5: ["影像", "ct", "mri", "x光"], 6: ["服务器", "gpu", "集群"], 7: ["光伏", "储能"],
    10: ["扫地机器人"], 11: ["会议平板", "显示器", "屏幕"], 12: ["数据线"],
    13: ["路灯"], 14: ["生长灯"], 15: ["球泡灯"], 16: ["充电桩"], 17: ["轮胎"],
    18: ["后视镜"], 19: ["螺丝刀"], 20: ["扳手"], 21: ["加工中心"], 22: ["机器人"],
    23: ["包装机", "灌装机", "封口机"], 24: ["铝单板", "铝板"], 25: ["钢管", "镀锌"],
    26: ["岩棉", "保温板"], 27: ["涂料", "漆"], 28: ["树脂"], 29: ["光伏", "太阳能", "组件"],
    30: ["风机", "风电"], 31: ["储能柜", "储能"], 32: ["门锁"], 33: ["咖啡机"],
    34: ["陶瓷", "餐具"], 35: ["卫浴", "挂件", "花洒"],
}


def name_hit_kw(name: str, kws: list[str]) -> bool:
    n = (name or "").lower()
    return any(k.lower() in n for k in kws)


# ---------- 老算法（逐字复刻原实现） ----------
def old_keyword_score(query: str, text: str) -> int:
    if not query or not text:
        return 0
    q_chars = set(query.replace(" ", ""))
    t_chars = set(text.replace(" ", ""))
    return min(len(q_chars & t_chars) * 3, 30)


def old_category_score(cat1: str, cat2: str) -> int:
    if not cat1 or not cat2:
        return 0
    if cat1 == cat2:
        return 50
    return match_category_score(cat1, cat2)


def old_products_top(db, proc, limit=10):
    """老算法：/{id}/recommendations 实现（最近 500 条 + 品类 + 字符交叠）。"""
    products = (db.query(Product).filter(Product.status == "published")
                .order_by(Product.created_at.desc()).limit(500).all())
    result = []
    for p in products:
        score = 0
        cat_score = old_category_score(p.category or "", proc.category or "")
        if cat_score >= 50:
            score += 50
        elif cat_score >= 30:
            score += 30
        elif cat_score >= 10:
            score += 10
        if proc.exhibition_id and p.exhibition_id == proc.exhibition_id:
            score += 15
        if p.price and proc.budget_min and proc.budget_max and proc.budget_min <= p.price <= proc.budget_max:
            score += 10
        score += 5
        if score > 5:
            result.append((score, p))
    if not result:
        for p in products[:limit]:
            result.append((1, p))
    result.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in result[:limit]]


def old_exhibitor_scores(db, user, procs):
    """老算法：for-exhibitor 实现（品类 + 字符交叠 + 预算加分）。"""
    domain = user.industry_domain or ""
    cats = {c[0] for c in db.query(Product.category).filter(
        Product.exhibitor_id == user.id, Product.status == "published").distinct().all() if c[0]}
    all_cats = {domain} | cats
    all_cats.discard("")
    out = {}
    for p in procs:
        score = 0
        for cat in all_cats:
            s = old_category_score(cat, p.category or "")
            if s >= 50:
                score += 50
                break
            elif s >= 30:
                score += 30
                break
            elif s >= 10:
                score += 10
        for cat in all_cats:
            score += old_keyword_score(cat, p.title or "")
        if p.budget_max:
            score += 5
        out[p.id] = score
    return out


def precision_at(ranked_names, kws, k):
    top = ranked_names[:k]
    if not top:
        return 0.0
    hits = sum(1 for n in top if name_hit_kw(n, kws))
    return hits / min(k, len(top))


def main():
    db = SessionLocal()
    procs = {p.id: p for p in db.query(Procurement).all()}
    exhibitors = db.query(User).filter(User.role == "exhibitor").all()
    exhibitors = [u for u in exhibitors if u.username.startswith("exhibitor_")]

    def has_products(kws):
        for kw in kws:
            if db.query(Product.id).filter(Product.status == "published",
                                            Product.name.like(f"%{kw}%")).first():
                return True
        return False

    evaluable, skipped = [], []
    for pid in GOLD_K:
        if pid not in procs:
            continue
        (evaluable if has_products(GOLD_K[pid]) else skipped).append(pid)

    print("=" * 92)
    print("方向一：采购需求 → 推荐展品   金标=展品名含需求核心词")
    print("=" * 92)
    if skipped:
        print(f"（跳过 {len(skipped)} 条演示库中无对应展品的需求：{skipped}）")
    print(f"{'需求':<28}{'老P@5':>8}{'新P@5':>8}{'老P@10':>8}{'新P@10':>8}{'老耗时':>9}{'新耗时':>9}")
    old_p5 = new_p5 = old_p10 = new_p10 = 0.0
    old_ms = new_ms = 0.0
    n = 0
    for pid in evaluable:
        p = procs[pid]
        kws = GOLD_K[pid]
        t0 = time.perf_counter()
        old_names = [x.name for x in old_products_top(db, p)]
        om = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        out = workflow.match_products_for_procurement(db, p, limit=10)
        nm = (time.perf_counter() - t0) * 1000
        new_names = [x["name"] for x in out.items]
        op5, np5 = precision_at(old_names, kws, 5), precision_at(new_names, kws, 5)
        op10, np10 = precision_at(old_names, kws, 10), precision_at(new_names, kws, 10)
        old_p5 += op5; new_p5 += np5; old_p10 += op10; new_p10 += np10
        old_ms += om; new_ms += nm; n += 1
        print(f"#{pid:<4}{p.title[:22]:<24}{op5:>8.2f}{np5:>8.2f}{op10:>8.2f}{np10:>8.2f}{om:>8.0f}ms{nm:>8.0f}ms")
    print("-" * 92)
    print(f"{'平均 ('+str(n)+' 条)':<28}{old_p5/n:>8.2f}{new_p5/n:>8.2f}{old_p10/n:>8.2f}{new_p10/n:>8.2f}{old_ms/n:>8.0f}ms{new_ms/n:>8.0f}ms")

    print()
    print("=" * 92)
    print("方向二：展商 → 推荐采购需求   金标=展商产品名含需求核心词  (MRR / P@10)")
    print("=" * 92)
    all_procs = list(procs.values())
    print(f"{'展商':<22}{'老MRR':>8}{'新MRR':>8}{'老P@10':>8}{'新P@10':>8}")
    o_mrr = n_mrr = o_p10 = n_p10 = 0.0
    processed = 0
    for u in exhibitors:
        my_names = [x[0] for x in db.query(Product.name).filter(
            Product.exhibitor_id == u.id, Product.status == "published").all()]
        relevant = {pid for pid in evaluable if any(name_hit_kw(nm, GOLD_K[pid]) for nm in my_names)}
        if not relevant:
            continue
        processed += 1

        old_scores = old_exhibitor_scores(db, u, all_procs)
        old_ranked = sorted(all_procs, key=lambda p: old_scores.get(p.id, 0), reverse=True)
        new_map, _meta = workflow.score_procurements_for_exhibitor(db, u, [p.id for p in all_procs])
        new_ranked = sorted(all_procs, key=lambda p: new_map.get(p.id, {}).get("match_score", 0), reverse=True)

        def mrr_p10(ranked):
            mrr = 0.0
            for i, p in enumerate(ranked, 1):
                if p.id in relevant:
                    mrr = 1.0 / i
                    break
            top10 = {p.id for p in ranked[:10]}
            p10 = len(top10 & relevant) / min(10, len(relevant))
            return mrr, p10

        om, op10 = mrr_p10(old_ranked)
        nm, np10 = mrr_p10(new_ranked)
        o_mrr += om; n_mrr += nm; o_p10 += op10; n_p10 += np10
        print(f"{u.username:<22}{om:>8.2f}{nm:>8.2f}{op10:>8.2f}{np10:>8.2f}   (相关需求 {len(relevant)} 条)")
    if processed:
        print("-" * 92)
        print(f"{'平均 ('+str(processed)+' 家)':<22}{o_mrr/processed:>8.2f}{n_mrr/processed:>8.2f}{o_p10/processed:>8.2f}{n_p10/processed:>8.2f}")

    print()
    print("引擎自检：", workflow.match_products_for_procurement(db, procs[evaluable[0]], limit=5).as_payload()["engine"],
          "| 阶段：", [s.name for s in workflow.match_products_for_procurement(db, procs[evaluable[0]], limit=5).trace])
    db.close()


if __name__ == "__main__":
    main()
