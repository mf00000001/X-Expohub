"""智能推荐匹配工作流测试：文本层 / 打分排序 / API 契约 / 通知闭环

覆盖点：
1. textkit：品类归一化（非标 → 标准）、分词停用词过滤、规格词过滤、同义词/上位词方向性
2. workflow：展商侧排序（相关需求排前、无关需求被门控剔除）、非标品类修复、已应标剔除
3. API：/recommendations/for-exhibitor、/recommendations/score-procurements、
   /procurements/{id}/recommendations 的契约（match_score/match_level/reasons/pipeline）
4. 发布采购 → 匹配展商收到通知（工作流阈值）
5. 零云依赖：pipeline.engine == match-workflow-local（无 LLM 调用）

运行: cd expohub-backend && python -m pytest tests/test_match_workflow.py -v
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, hash_password
from app.models.base import SessionLocal
from app.models.notification import Notification
from app.models.procurement import Procurement
from app.models.product import Product
from app.models.user import User
from app.modules.matching import textkit, workflow


# ============================================================
# 公共夹具
# ============================================================

def _seed_user(db, username: str, role: str, industry: str | None = None,
               company: str = "测试公司") -> User:
    now = datetime.now(timezone.utc)
    u = User(
        username=username, email=f"{username}@test.local",
        password_hash=hash_password("testpass123"), role=role, status="active",
        is_onboarded=True, company=company, industry_domain=industry,
        total_points=0, token_version=0, created_at=now, updated_at=now,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.id, 'role': user.role, 'ver': 0})}"}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def ctx(request, client):
    """隔离上下文：展商（机械+空调展品）、买家、三条采购需求（相关/非标品类/无关）。"""
    tag = request.node.name[:24].replace("::", "_").replace("[", "").replace("]", "")
    now = datetime.now(timezone.utc)
    db = SessionLocal()

    ex = _seed_user(db, f"{tag}_exh", "exhibitor", industry="机械", company="智造科技")
    buyer = _seed_user(db, f"{tag}_buyer", "buyer")

    products = []
    for name, cat, price in [
        ("五轴数控加工中心 CNC", "机械", 800000.0),
        ("六轴工业机器人", "机械", 300000.0),
        ("智能变频空调", "电子及家电", 3000.0),
    ]:
        p = Product(exhibitor_id=ex.id, name=name, description=f"{name}，适用于工业场景",
                    category=cat, price=price, status="published",
                    view_count=50, favorite_count=5, search_appearances=10,
                    created_at=now, updated_at=now)
        db.add(p)
        products.append(p)
    db.commit()
    for p in products:
        db.refresh(p)

    procs = []
    for title, cat in [
        ("采购10台数控加工中心", "机械"),            # 相关
        ("采购500台变频空调", "家用电器"),           # 非标品类（应归一化到电子及家电）
        ("采购进口红酒全年供应", "食品饮料"),        # 无关（无关键词命中 → 应被门控）
    ]:
        proc = Procurement(
            purchaser_id=buyer.id, purchaser_name="测试买家", title=title,
            description=f"演示需求：{title}", category=cat,
            budget_min=200000.0, budget_max=1200000.0, status="pending",
            created_at=now, updated_at=now,
        )
        db.add(proc)
        procs.append(proc)
    db.commit()
    for p in procs:
        db.refresh(p)

    workflow.invalidate_corpus()  # 数据已变化，失效语料缓存
    yield {
        "client": client, "db": db, "ex": ex, "buyer": buyer,
        "products": products, "procs": procs, "tag": tag,
    }
    db.close()


# ============================================================
# 1) 文本层（无数据库依赖）
# ============================================================

def test_normalize_category_nonstandard():
    """非标准品类 → 标准展区品类（跨体系断链修复）。"""
    assert textkit.normalize_category("家用电器") == "电子及家电"
    assert textkit.normalize_category("小家电") == "电子及家电"
    assert textkit.normalize_category("工业自动化") == "机械"
    assert textkit.normalize_category("新能源") == "能源"
    assert textkit.normalize_category("医疗器械") == "医药及医疗保健"
    assert textkit.normalize_category("AI基础设施") == "AI/科技"
    assert textkit.normalize_category("机械类") == "机械"
    assert textkit.normalize_category("机械") == "机械"
    assert textkit.normalize_category(None) == ""


def test_tokenize_filters_stopwords_and_specs():
    toks = textkit.tokenize("采购1000台智能空调")
    assert "智能" in toks and "空调" in toks
    assert "采购" not in toks and "台" not in toks

    q = textkit.build_query([("采购200MW光伏组件，支持5G联网", 2)])
    assert "光伏组件" in q and "5g" in q          # 业务词保留
    assert "200mw" not in q                        # 规格词过滤


def test_synonym_direction():
    """上位词→下位词单向命中；并列词（空调/冰箱）不得互相命中。"""
    doc_text = "格力 变频空调"
    doc_tokens = set(textkit.tokenize(doc_text))
    # 查询"家电"（上位词）→ 命中"空调"（下位词）
    assert textkit.token_hit("家电", doc_text, doc_tokens) > 0
    # 查询"冰箱"（并列词）→ 不得命中"空调"
    assert textkit.token_hit("冰箱", doc_text, doc_tokens) == 0
    # 数据线族：Type-C 与 数据线 互相命中（真同义词族）
    assert textkit.token_hit("type-c", doc_text="tcl 快充数据线", doc_tokens=set(textkit.tokenize("tcl 快充数据线"))) > 0


# ============================================================
# 2) 工作流排序与门控
# ============================================================

def test_exhibitor_ranking_and_gating(ctx):
    """相关需求排前、非标品类命中、无关需求被门控剔除。"""
    db, ex = ctx["db"], ctx["ex"]
    pr1, pr2, pr3 = ctx["procs"]

    out = workflow.match_procurements_for_exhibitor(db, ex, limit=10)
    ids = [it["id"] for it in out.items]

    assert pr1.id in ids, "数控加工中心需求应被推荐"
    assert pr2.id in ids, "非标品类（家用电器→电子及家电）需求应被推荐"
    assert pr3.id not in ids, "无关需求（红酒）应被关键词门控剔除"

    # 非标品类归一化后应给出「品类精确匹配」理由
    pr2_item = next(it for it in out.items if it["id"] == pr2.id)
    assert any("品类精确匹配" in r for r in pr2_item["reasons"]), pr2_item["reasons"]

    # 分数降序 + 契约字段
    scores = [it["match_score"] for it in out.items]
    assert scores == sorted(scores, reverse=True)
    for it in out.items:
        assert 0 <= it["match_score"] <= 100
        assert it["match_level"] in ("high", "medium", "low")
        assert isinstance(it["reasons"], list) and it["reasons"]

    # 工作流 trace：S0-S4 阶段齐全，纯本地引擎
    payload = out.as_payload()
    assert payload["engine"] == "match-workflow-local"
    stage_names = [s["name"] for s in payload["stages"]]
    assert any("S0" in n for n in stage_names) and any("S4" in n for n in stage_names)


def test_exhibitor_excludes_own_and_bid(ctx):
    """自家发布的需求与已应标的需求不出现在推荐里。"""
    db, ex, buyer = ctx["db"], ctx["ex"], ctx["buyer"]
    pr1 = ctx["procs"][0]

    # 展商自己发布一条采购（应被剔除）
    now = datetime.now(timezone.utc)
    own = Procurement(purchaser_id=ex.id, purchaser_name="展商自采",
                      title=f"采购数控加工中心备件-{ctx['tag']}", category="机械",
                      status="pending", created_at=now, updated_at=now)
    db.add(own)
    db.commit()
    db.refresh(own)

    out = workflow.match_procurements_for_exhibitor(db, ex, limit=20)
    ids = [it["id"] for it in out.items]
    assert own.id not in ids

    # 对 pr1 应标后，应被剔除
    from app.models.procurement_match import ProcurementMatch
    db.add(ProcurementMatch(procurement_id=pr1.id, exhibitor_id=ex.id, message="已应标"))
    db.commit()
    out2 = workflow.match_procurements_for_exhibitor(db, ex, limit=20)
    assert pr1.id not in [it["id"] for it in out2.items]


def test_products_recommendation_ranks_relevant(ctx):
    """采购需求 → 展品方向：关键词相关展品排前。"""
    db = ctx["db"]
    pr1, pr2 = ctx["procs"][0], ctx["procs"][1]

    out1 = workflow.match_products_for_procurement(db, pr1, limit=5)
    top_names = [it["name"] for it in out1.items]
    assert any("数控加工中心" in n for n in top_names), top_names

    out2 = workflow.match_products_for_procurement(db, pr2, limit=5)
    hit = [it for it in out2.items if "空调" in it["name"]]
    assert hit, [it["name"] for it in out2.items]
    assert hit[0]["match_score"] >= 40
    assert any("空调" in r for r in hit[0]["match_reasons"])


# ============================================================
# 3) API 契约
# ============================================================

def test_api_for_exhibitor_contract(ctx):
    c, ex = ctx["client"], ctx["ex"]
    r = c.get("/api/recommendations/for-exhibitor", headers=_auth(ex))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert body["pipeline"]["engine"] == "match-workflow-local"
    assert body["pipeline"]["stages"], "应返回工作流阶段 trace"
    assert body["pipeline"]["total_ms"] >= 0
    for it in body["data"]:
        assert {"id", "title", "match_score", "match_level", "reasons"} <= set(it.keys())


def test_api_score_procurements(ctx):
    c, ex = ctx["client"], ctx["ex"]
    pr1, pr2, pr3 = ctx["procs"]
    r = c.get(f"/api/recommendations/score-procurements?ids={pr1.id},{pr2.id},{pr3.id}",
              headers=_auth(ex))
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert str(pr1.id) in data and str(pr2.id) in data
    assert data[str(pr1.id)]["match_score"] > 0
    # 无关需求（红酒）零分（被门控）
    assert data[str(pr3.id)]["match_score"] == 0


def test_api_procurement_recommendations_ownership(ctx):
    c, ex, buyer = ctx["client"], ctx["ex"], ctx["buyer"]
    pr1 = ctx["procs"][0]

    # 非归属者（展商）→ 403
    r = c.get(f"/api/procurements/{pr1.id}/recommendations", headers=_auth(ex))
    assert r.status_code == 403

    # 归属者（买家）→ 200，契约齐全
    r = c.get(f"/api/procurements/{pr1.id}/recommendations", headers=_auth(buyer))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data"], "应有推荐展品"
    first = body["data"][0]
    assert 0 <= first["match_score"] <= 100
    assert first["match_reasons"]
    assert body["pipeline"]["stages"]


def test_publish_notifies_matched_exhibitor(ctx):
    """发布采购后，匹配度达标的展商收到通知（工作流驱动）。"""
    c, ex, buyer = ctx["client"], ctx["ex"], ctx["buyer"]
    db = ctx["db"]
    now = datetime.now(timezone.utc)

    # 独占关键词（防爆型）：确保本用例展商在同库多展商中排进通知 Top5
    db.add(Product(exhibitor_id=ex.id, name="防爆型数控加工中心", description="防爆型五轴加工中心",
                   category="机械", price=500000.0, status="published",
                   created_at=now, updated_at=now))
    db.commit()
    workflow.invalidate_corpus()

    r = c.post("/api/procurements", json={
        "title": "采购20台防爆型数控加工中心",
        "description": "防爆型五轴联动加工中心，欢迎应标",
        "category": "机械", "budget_min": 100000, "budget_max": 3000000,
    }, headers=_auth(buyer))
    assert r.status_code == 200, r.text

    db.expire_all()
    notif = db.query(Notification).filter(
        Notification.user_id == ex.id,
        Notification.title.like("%防爆型数控加工中心%"),
    ).first()
    assert notif is not None, "匹配展商应收到通知"
    assert "匹配" in notif.title
