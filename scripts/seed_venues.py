"""展馆种子数据: 国内常用会展场馆(幂等, 已存在则跳过)

运行: python scripts/seed_venues.py
"""
import json
import os
import sqlite3
import sys

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "expohub-backend", "expohub.db")

VENUES = [
    {
        "name": "广交会展馆",
        "city": "广州",
        "address": "广州市海珠区阅江中路 380 号",
        "area": 162.0,
        "important_info": "亚洲规模最大的会展综合体之一,中国进出口商品交易会(广交会)主场馆;地铁 8 号线琶洲站/新港东站直达,紧邻琶洲港澳客运口岸。",
        "honors": ["中国进出口商品交易会永久会址", "亚洲最大会展综合体之一"],
    },
    {
        "name": "国家会展中心(上海)",
        "city": "上海",
        "address": "上海市青浦区崧泽大道 333 号",
        "area": 147.0,
        "important_info": "总建筑面积约 147 万平方米,室内展览面积约 40 万平方米;地铁 2 号线徐泾东站直达;四叶草造型地标建筑。",
        "honors": ["中国国际进口博览会永久会址", "全球最大单体建筑之一"],
    },
    {
        "name": "上海新国际博览中心",
        "city": "上海",
        "address": "上海市浦东新区龙阳路 2345 号",
        "area": 20.0,
        "important_info": "室内展览面积约 20 万平方米,17 个无柱展厅;地铁 2/7/16/18 号线龙阳路站;浦东核心会展商圈。",
        "honors": ["中国展览馆协会常务理事单位", "上海知名老牌展馆"],
    },
    {
        "name": "深圳国际会展中心",
        "city": "深圳",
        "address": "深圳市宝安区福海街道展城路 1 号",
        "area": 40.0,
        "important_info": "室内展览面积约 40 万平方米,全球规模最大的会展中心之一;紧邻深圳机场,地铁 20 号线国展站;采用智慧化运营体系。",
        "honors": ["全球最大室内展馆之一", "深圳新地标建筑"],
    },
    {
        "name": "国家会议中心",
        "city": "北京",
        "address": "北京市朝阳区天辰东路 7 号",
        "area": 53.0,
        "important_info": "总建筑面积约 53 万平方米;紧邻奥林匹克公园,地铁 8/15 号线奥林匹克公园站;集会议、展览、餐饮、酒店于一体。",
        "honors": ["2008 北京奥运会主新闻中心与击剑馆", "APEC 峰会会场之一"],
    },
    {
        "name": "中国国际展览中心(顺义馆)",
        "city": "北京",
        "address": "北京市顺义区裕翔路 88 号",
        "area": 10.0,
        "important_info": "室内展览面积约 10 万平方米,8 个大型展厅;地铁 15 号线国展站直达;北京大型专业展会主要举办地之一。",
        "honors": ["北京老牌专业展馆", "中国国际展览中心集团旗下"],
    },
    {
        "name": "中国西部国际博览城",
        "city": "成都",
        "address": "成都市天府新区福州路东段 88 号",
        "area": 20.5,
        "important_info": "室内展览面积约 20.5 万平方米;地铁 1/6/18 号线西博城站直达;西部规模最大的会展场馆之一。",
        "honors": ["中国西部最大会展场馆之一", "西博会永久会址"],
    },
    {
        "name": "杭州国际博览中心",
        "city": "杭州",
        "address": "杭州市萧山区奔竞大道 353 号",
        "area": 9.0,
        "important_info": "总建筑面积约 85 万平方米,展览面积约 9 万平方米;钱江世纪城核心区,地铁 6 号线博览中心站。",
        "honors": ["G20 杭州峰会主会场", "中国国际动漫节主会场"],
    },
    {
        "name": "武汉国际博览中心",
        "city": "武汉",
        "address": "武汉市汉阳区鹦鹉大道 619 号",
        "area": 15.0,
        "important_info": "室内展览面积约 15 万平方米,12 个展厅;华中地区规模最大的会展场馆;地铁 6 号线国博中心南站。",
        "honors": ["华中最大会展场馆", "长江经济带会展标杆"],
    },
    {
        "name": "重庆国际博览中心",
        "city": "重庆",
        "address": "重庆市渝北区悦来大道 66 号",
        "area": 20.0,
        "important_info": "室内展览面积约 20 万平方米;两江新区悦来会展城,轻轨 10 号线国博中心站;智慧展馆试点。",
        "honors": ["中国西部重要会展中心", "重庆智博会永久会址"],
    },
    {
        "name": "南京国际博览中心",
        "city": "南京",
        "address": "南京市建邺区江东中路 300 号",
        "area": 12.0,
        "important_info": "室内展览面积约 12 万平方米;河西新城核心区,地铁 2/10 号线元通站直达。",
        "honors": ["中国(南京)软博会永久会址"],
    },
    {
        "name": "西安国际会展中心",
        "city": "西安",
        "address": "西安市灞桥区会展一路 1399 号",
        "area": 7.2,
        "important_info": "室内展览面积约 7.2 万平方米;浐灞生态区,地铁 3 号线香湖湾站;西北地区现代化展馆代表。",
        "honors": ["欧亚经济论坛永久会址", "西北现代化展馆代表"],
    },
]


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM venues")
    existing = cur.fetchone()[0]
    if existing > 0:
        print(f"venues 表已有 {existing} 条记录, 跳过种子导入")
        conn.close()
        return

    for v in VENUES:
        cur.execute(
            "INSERT INTO venues (name, city, address, area, important_info, honors, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            (v["name"], v["city"], v["address"], v["area"], v["important_info"],
             json.dumps(v["honors"], ensure_ascii=False)),
        )
    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
    conn.close()
    print(f"展馆种子数据导入完成: {total} 个场馆")


if __name__ == "__main__":
    main()
