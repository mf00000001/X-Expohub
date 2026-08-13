"""用官网官方信息更新重点场馆数据(幂等, 按名称匹配)

数据来源: 各场馆官方网站(2026-08 抓取)
- 国家会展中心(上海): neccsh.com 公司介绍页
- 国家会议中心: cnccchina.com 官网
- 厦门国际会展中心: xicec.com 场馆介绍页
- 深圳国际会展中心: shenzhen-world.com 官网
运行: python scripts/update_venue_official.py
"""
import json
import os
import sqlite3

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "expohub-backend", "expohub.db")

UPDATES = [
    {
        "name": "国家会展中心(上海)",
        "area": 150.0,
        "important_info": (
            "官方资料:2011年由商务部和上海市政府合作共建的国家级超大型会展项目,"
            "总建筑面积超过 150 万平方米,因'四叶幸运草'外形被誉为'中国新地标';"
            "紧邻虹桥国际机场和高铁站,馆内会议中心、酒店、商业、办公等功能设施一应俱全;"
            "地铁 2 号线徐泾东站直达。"
        ),
        "honors": ["中国国际进口博览会举办地", "被誉为'中国新地标'(四叶幸运草造型)", "国家级超大型会展项目"],
    },
    {
        "name": "国家会议中心",
        "area": 53.0,
        "important_info": (
            "官方资料:位于北京市朝阳区天辰东路 7 号;大宴会厅 4800㎡(层高10米无柱设计)、"
            "大会堂 6400㎡(层高12米)、多功能厅 1800㎡;配套国家会议中心大酒店步行仅 3-5 分钟,"
            "紧邻奥林匹克公园,地铁 8/15 号线奥林匹克公园站。"
        ),
        "honors": ["ICCA 国际大会及会议协会会员", "UFI 全球展览业协会会员", "获评全国文明单位", "2008 北京奥运会主新闻中心与击剑馆"],
    },
    {
        "name": "厦门国际会展中心",
        "area": 20.0,
        "important_info": (
            "官方资料:位于厦门岛东南海岸,与小金门岛隔海相望(直线距离 4500 米);"
            "总建筑面积近 53 万平方米,A/B/C/D 展馆共 23 个展厅,展览面积合计 20 万平方米,"
            "可设 9000 个国际标准展位,含 76 间中高档会议室及一座 248 间客房准五星酒店;"
            "地铁 2 号线会展中心站,会展热线 0592-5959151。"
        ),
        "honors": ["中国国际投资贸易洽谈会(投洽会)举办主场馆", "厦门会展集团运营"],
    },
    {
        "name": "深圳国际会展中心",
        "area": 40.0,
        "important_info": (
            "官方资料:室内展览面积约 40 万平方米,全球规模最大的会展中心之一;"
            "官网提供 360°VR 逛馆、展会排期查询、交通指引等服务;"
            "紧邻深圳机场,地铁 20 号线国展站。"
        ),
        "honors": ["全球最大室内展馆之一", "深圳新地标建筑", "官网支持 VR 全景逛馆"],
    },
]


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    updated = 0
    for u in UPDATES:
        row = cur.execute("SELECT id FROM venues WHERE name=?", (u["name"],)).fetchone()
        if not row:
            print(f"  [SKIP] 未找到场馆: {u['name']}")
            continue
        cur.execute(
            "UPDATE venues SET area=?, important_info=?, honors=? WHERE id=?",
            (u["area"], u["important_info"], json.dumps(u["honors"], ensure_ascii=False), row[0]),
        )
        updated += 1
    conn.commit()
    conn.close()
    print(f"官方信息更新完成: {updated} 个场馆")


if __name__ == "__main__":
    main()
