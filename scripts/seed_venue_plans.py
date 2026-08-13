"""场馆平面图种子数据: 为 venues 表生成示意 SVG 平面图(data URI, 幂等)

运行: python scripts/seed_venue_plans.py
说明: 平面图为通用示意图(展馆外框+展位网格+入口标注), 实际展馆平面图可由
      admin 通过 PUT /api/venues/:id 的 plan_image 字段替换为真实图片 URL。
"""
import os
import sqlite3
import urllib.parse

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "expohub-backend", "expohub.db")


def build_svg(name: str) -> str:
    """生成展馆平面示意图 SVG"""
    cells = []
    for r in range(5):
        for c in range(8):
            x = 40 + c * 65
            y = 80 + r * 58
            cells.append(
                f'<rect x="{x}" y="{y}" width="58" height="50" rx="4" '
                f'fill="#e0edff" stroke="#93b8f0" stroke-width="1"/>'
                f'<text x="{x+29}" y="{y+29}" text-anchor="middle" font-size="10" fill="#5b7db8">展位</text>'
            )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="620" height="440">'
        '<rect width="620" height="440" fill="#f0f4f8"/>'
        f'<text x="310" y="34" text-anchor="middle" font-size="18" font-weight="bold" fill="#1f2937">{name} 平面示意图</text>'
        '<rect x="30" y="55" width="560" height="330" fill="#ffffff" stroke="#2563eb" stroke-width="2"/>'
        + "".join(cells) +
        '<rect x="250" y="350" width="120" height="26" rx="13" fill="#2563eb"/>'
        '<text x="310" y="368" text-anchor="middle" font-size="12" fill="#ffffff">主入口</text>'
        '<text x="310" y="415" text-anchor="middle" font-size="11" fill="#9ca3af">示意图 — 实际布局以展馆官方平面图为准</text>'
        '</svg>'
    )


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    rows = cur.execute("SELECT id, name FROM venues").fetchall()
    updated = 0
    for vid, name in rows:
        # 已有平面图的跳过(幂等)
        has = cur.execute("SELECT plan_image FROM venues WHERE id=?", (vid,)).fetchone()[0]
        if has:
            continue
        svg = build_svg(name)
        data_uri = "data:image/svg+xml;charset=utf-8," + urllib.parse.quote(svg, safe="")
        cur.execute("UPDATE venues SET plan_image=? WHERE id=?", (data_uri, vid))
        updated += 1
    conn.commit()
    conn.close()
    print(f"平面图已生成: {updated} 个场馆(共 {len(rows)} 个)")


if __name__ == "__main__":
    main()
