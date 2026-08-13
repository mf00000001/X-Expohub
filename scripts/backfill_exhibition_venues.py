"""为已创建展会回填展馆关联 + 重点场馆配置真实图片(幂等)

运行: python scripts/backfill_exhibition_venues.py
"""
import json
import os
import sqlite3

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "expohub-backend", "expohub.db")

# 展馆实景图(官网图片)
VENUE_IMAGES = {
    "厦门国际会展中心": "https://www.xicec.com/img/venue/xicec.jpg",
    "国家会议中心": "https://www.cnccchina.com/Uploads/Picture/2021/05/20/s60a62385da2b2.jpg",
    "国家会展中心(上海)": "https://www.neccsh.com/cecsh/r/cms/www/default/assets/img/zgss/zgss-top.png",
}

# 展会 location 关键词 -> 展馆名称
LOCATION_MATCH = [
    ("国家会议中心", "国家会议中心"),
    ("国家会展中心", "国家会展中心(上海)"),
    ("深圳国际会展中心", "深圳国际会展中心"),
    ("广交会展馆", "广交会展馆"),
    ("上海新国际博览中心", "上海新国际博览中心"),
    ("国际博览中心", "杭州国际博览中心"),
]


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # 1. 配置展馆实景图
    img_updated = 0
    for name, url in VENUE_IMAGES.items():
        row = cur.execute("SELECT id FROM venues WHERE name=?", (name,)).fetchone()
        if row:
            cur.execute("UPDATE venues SET image_url=? WHERE id=?", (url, row[0]))
            img_updated += 1

    # 2. 现有展会回填 venue_id(仅 venue_id 为空的)
    exhs = cur.execute("SELECT id, location FROM exhibitions WHERE venue_id IS NULL").fetchall()
    matched = 0
    for eid, loc in exhs:
        if not loc:
            continue
        for keyword, venue_name in LOCATION_MATCH:
            if keyword in loc:
                v = cur.execute("SELECT id FROM venues WHERE name=?", (venue_name,)).fetchone()
                if v:
                    cur.execute("UPDATE exhibitions SET venue_id=? WHERE id=?", (v[0], eid))
                    matched += 1
                    print(f"  [OK] 展会 id={eid} -> {venue_name}({loc[:24]}...)")
                break

    conn.commit()
    conn.close()
    print(f"实景图配置: {img_updated} 个场馆; 展会回填: {matched} 个")


if __name__ == "__main__":
    main()
