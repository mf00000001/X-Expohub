"""展馆种子数据补充: 第二批国内常用会展场馆(幂等, 按名称查重)

运行: python scripts/seed_venues_extra.py
数据来源: 公开网络资料(展馆官网/行业名录), 面积与信息为约数。
"""
import json
import os
import sqlite3

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "expohub-backend", "expohub.db")

VENUES = [
    {
        "name": "天津国家会展中心",
        "city": "天津",
        "address": "天津市津南区国展大道 888 号",
        "area": 40.0,
        "important_info": "室内展览面积约 40 万平方米,北方规模最大的会展综合体;紧邻天津大道,地铁 1 号线延长线可达;京津冀会展协同发展重要载体。",
        "honors": ["中国北方最大会展综合体", "国家会展项目(天津)有限公司运营"],
    },
    {
        "name": "郑州国际会展中心",
        "city": "郑州",
        "address": "郑州市郑东新区商务内环路 1 号",
        "area": 7.0,
        "important_info": "坐落于郑东新区如意湖畔,展览面积约 7 万平方米;全国文明城市窗口工程,地铁 1 号线会展中心站直达。",
        "honors": ["中部地区重要会展场馆", "中国(郑州)国际汽车后市场博览会举办地"],
    },
    {
        "name": "厦门国际会展中心",
        "city": "厦门",
        "address": "厦门市思明区会展路 198 号",
        "area": 8.0,
        "important_info": "展览面积约 8 万平方米,环岛路会展商圈核心;紧邻厦门国际会议中心,地铁 2 号线会展中心站。",
        "honors": ["中国国际投资贸易洽谈会(投洽会)永久会址", "金砖国家领导人会晤配套场馆"],
    },
    {
        "name": "苏州国际博览中心",
        "city": "苏州",
        "address": "苏州市苏州工业园区苏州大道东 688 号",
        "area": 10.0,
        "important_info": "展览面积约 10 万平方米,位于金鸡湖商务区;地铁 1 号线文化博览中心站直达;苏州高端会展核心场馆。",
        "honors": ["金鸡湖商务区地标建筑", "中国(苏州)电子信息博览会举办地"],
    },
    {
        "name": "昆明滇池国际会展中心",
        "city": "昆明",
        "address": "昆明市官渡区环湖东路(滇池湖畔)",
        "area": 30.0,
        "important_info": "室内展览面积约 30 万平方米,毗邻滇池,环境优越;昆明南博会、旅交会等国家级展会主场馆。",
        "honors": ["中国-南亚博览会主场馆", "西南地区最大会展中心之一"],
    },
    {
        "name": "长沙国际会展中心",
        "city": "长沙",
        "address": "长沙市长沙县国展路 118 号",
        "area": 11.0,
        "important_info": "展览面积约 11 万平方米,位于长沙高铁新城片区;地铁 2 号线光达站直达;湖南最大会展场馆。",
        "honors": ["湖南最大会展场馆", "中国中部(湖南)农业博览会举办地"],
    },
    {
        "name": "宁波国际会展中心",
        "city": "宁波",
        "address": "宁波市鄞州区会展路 181 号",
        "area": 8.0,
        "important_info": "展览面积约 8 万平方米,东部新城会展商圈;地铁 5 号线会展中心站直达;中国-中东欧国家博览会举办地。",
        "honors": ["中国-中东欧国家博览会主场馆", "浙江重要会展场馆"],
    },
    {
        "name": "山东国际会展中心",
        "city": "济南",
        "address": "济南市槐荫区日照路 1 号",
        "area": 10.6,
        "important_info": "展览面积约 10.6 万平方米,济南西部新城核心;京沪高铁济南西站直达;山东最大会展综合体。",
        "honors": ["山东最大会展综合体", "中国(济南)国际机床展览会举办地"],
    },
    {
        "name": "哈尔滨国际会展体育中心",
        "city": "哈尔滨",
        "address": "哈尔滨市南岗区红旗大街 301 号",
        "area": 3.6,
        "important_info": "展览面积约 3.6 万平方米,集会展、体育、会议于一体;中国-俄罗斯博览会举办地之一。",
        "honors": ["中国-俄罗斯博览会举办地", "东北地区重要会展场馆"],
    },
    {
        "name": "大连世界博览广场",
        "city": "大连",
        "address": "大连市沙河口区星海广场 F 区 10 号",
        "area": 6.0,
        "important_info": "展览面积约 6 万平方米,坐落于星海广场,面朝大海;大连夏季达沃斯论坛主会场。",
        "honors": ["夏季达沃斯论坛主会场", "大连服装博览会举办地"],
    },
]


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    added = 0
    skipped = 0
    for v in VENUES:
        exists = cur.execute("SELECT id FROM venues WHERE name=?", (v["name"],)).fetchone()
        if exists:
            skipped += 1
            continue
        cur.execute(
            "INSERT INTO venues (name, city, address, area, important_info, honors, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            (v["name"], v["city"], v["address"], v["area"], v["important_info"],
             json.dumps(v["honors"], ensure_ascii=False)),
        )
        added += 1
    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
    conn.close()
    print(f"新增展馆: {added}, 跳过(已存在): {skipped}, 当前总数: {total}")


if __name__ == "__main__":
    main()
