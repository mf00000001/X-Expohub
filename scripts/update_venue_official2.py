"""官网官方信息更新(第二批): 广交会展馆 / 天津国家会展中心(幂等)

数据来源: 官方公开资料(广交会官网资料/国家会展中心(天津)官网 ncectj.com)
运行: python scripts/update_venue_official2.py
"""
import json
import os
import sqlite3

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "expohub-backend", "expohub.db")

UPDATES = [
    {
        "name": "广交会展馆",
        "area": 33.8,
        "important_info": (
            "官方资料:中国进出口商品交易会展馆(简称广交会展馆)坐落于广州琶洲岛,"
            "总建筑面积 110 万平方米,室内展厅总面积 33.8 万平方米(A区13万㎡/B区12.8万㎡/C区8万㎡),"
            "室外展场 4.36 万平方米,四期扩建后展览面积达 50 万平方米;"
            "地址:广州市海珠区阅江中路 382 号,地铁 8 号线琶洲站/新港东站,服务热线 4000-888-999。"
        ),
        "honors": ["中国进出口商品交易会(广交会)主场馆", "亚洲最大、全球第二的会展中心", "四期扩建后展览面积达50万平方米"],
    },
    {
        "name": "天津国家会展中心",
        "area": 40.0,
        "important_info": (
            "官方资料:总建筑面积约 138 万平方米,室内展览面积 40 万平方米,室外展览面积约 15.8 万平方米,"
            "总停车位 9000 余个;32 个单层无柱展厅(每个约 1.25 万㎡,净高 16m,地面荷载 5T/8T),"
            "会议室约 100 余间;地址:天津市津南区咸水沽镇国展大道 888 号,地铁 1 号线国家会展中心站直达。"
        ),
        "honors": ["中国北方展览面积最大、使用体验最佳的会展综合体", "商务部与天津市政府合作共建", "京津冀协同发展标志性工程"],
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
