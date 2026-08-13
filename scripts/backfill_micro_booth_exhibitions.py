"""微展位分类到展会(幂等: 仅分配 exhibition_id 为空的)

映射规则: 行业领域 -> 展会
- 展会1 人工智能产业博览会: AI/科技、电子及家电、办公与文具
- 展会2 新能源汽车与工业: 机械、五金工具、车辆与配件
- 展会3 新能源低碳: 能源、照明、化工产品
其余行业按轮询分散到三个正式展会。
运行: python scripts/backfill_micro_booth_exhibitions.py
"""
import os
import sqlite3

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "expohub-backend", "expohub.db")

EXHIBITION_AI = 1
EXHIBITION_AUTO = 2
EXHIBITION_ENERGY = 3

DOMAIN_MAP = {
    "AI/科技": EXHIBITION_AI,
    "电子及家电": EXHIBITION_AI,
    "办公与文具": EXHIBITION_AI,
    "机械": EXHIBITION_AUTO,
    "五金工具": EXHIBITION_AUTO,
    "车辆与配件": EXHIBITION_AUTO,
    "能源": EXHIBITION_ENERGY,
    "照明": EXHIBITION_ENERGY,
    "化工产品": EXHIBITION_ENERGY,
}

FALLBACK_POOL = [EXHIBITION_AI, EXHIBITION_AUTO, EXHIBITION_ENERGY]


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # 确认正式展会存在
    exhs = cur.execute("SELECT id FROM exhibitions WHERE id IN (1,2,3)").fetchall()
    valid = {r[0] for r in exhs}
    print(f"可用展会: {sorted(valid)}")

    rows = cur.execute(
        "SELECT id, industry_domain FROM micro_booths WHERE exhibition_id IS NULL"
    ).fetchall()
    assigned = 0
    fallback_counts = {e: 0 for e in FALLBACK_POOL}
    fallback_idx = 0
    for mb_id, domain in rows:
        domain = domain or ""
        eid = DOMAIN_MAP.get(domain)
        if eid is None or eid not in valid:
            # 兜底轮询
            eid = FALLBACK_POOL[fallback_idx % len(FALLBACK_POOL)]
            fallback_idx += 1
            fallback_counts[eid] = fallback_counts.get(eid, 0) + 1
        cur.execute("UPDATE micro_booths SET exhibition_id=? WHERE id=?", (eid, mb_id))
        assigned += 1

    conn.commit()
    dist = cur.execute(
        "SELECT exhibition_id, COUNT(*) FROM micro_booths WHERE exhibition_id IS NOT NULL GROUP BY exhibition_id"
    ).fetchall()
    conn.close()
    print(f"已分配: {assigned} 个微展位(兜底轮询: {fallback_counts})")
    print(f"分布: {sorted(dist)}")


if __name__ == "__main__":
    main()
