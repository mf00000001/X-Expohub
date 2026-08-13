"""采购需求示例数据补充(幂等: 按标题查重)

覆盖 EXHIBITION_CATEGORIES 全部分类, 便于演示分类筛选。
运行: python scripts/seed_procurements.py
"""
import os
import sqlite3
from datetime import datetime, timedelta

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "expohub-backend", "expohub.db")

# (title, category, quantity, unit, budget_min, budget_max, deadline_days, status, description)
PROCUREMENTS = [
    # 电子及家电
    ("采购5000台智能扫地机器人", "电子及家电", 5000, "台", 300, 500, 30, "open",
     "出口东南亚市场,要求支持多语言语音,带激光导航,需提供CE认证。"),
    ("批量采购65寸商用会议平板", "电子及家电", 200, "台", 8000, 12000, 20, "open",
     "应用于企业会议室,需内置OPS电脑、4K屏、支持无线投屏。"),
    ("采购10万只Type-C快充数据线", "电子及家电", 100000, "只", 2, 5, 15, "published",
     "3A电流、锌合金接口,支持OEM定制logo,交期45天。"),
    # 照明
    ("采购3万套LED智慧路灯", "照明", 30000, "套", 800, 1500, 60, "open",
     "市政道路改造项目,需智能调光+远程控制,防护等级IP65。"),
    ("采购2万支植物生长灯", "照明", 20000, "支", 30, 60, 25, "open",
     "温室大棚用,全光谱,功率15W-30W,需提供光效检测报告。"),
    ("采购5万只LED球泡灯", "照明", 50000, "只", 3, 8, 20, "closed",
     "家用E27螺口,9W-12W,光通量800lm以上,需3C认证。"),
    # 车辆及配件
    ("采购2000套新能源车充电桩", "车辆及配件", 2000, "套", 5000, 9000, 45, "open",
     "交流慢充7kW,需支持国标GB/T,含安装调试服务。"),
    ("采购50万条汽车轮胎", "车辆及配件", 500000, "条", 150, 300, 90, "open",
     "17-19寸轿车胎,耐磨指数400+,出口中东市场。"),
    ("采购1万套车载智能后视镜", "车辆及配件", 10000, "套", 400, 700, 35, "published",
     "含行车记录+倒车影像+语音助手功能。"),
    # 五金工具
    ("采购10万把电动螺丝刀", "五金工具", 100000, "把", 25, 45, 30, "open",
     "家用级,锂电充电,双档调速,需CE/ROHS认证。"),
    ("采购5万套棘轮扳手套装", "五金工具", 50000, "套", 60, 100, 25, "open",
     "铬钒钢材质,含常见规格,礼盒包装出口。"),
    # 机械
    ("采购50台数控加工中心", "机械", 50, "台", 250000, 400000, 120, "open",
     "五轴联动,行程800x600x500,含编程培训与质保。"),
    ("采购200台工业机器人", "机械", 200, "台", 80000, 150000, 150, "open",
     "六轴关节机器人,负载6-20kg,用于汽车产线上下料。"),
    ("采购20条食品包装生产线", "机械", 20, "条", 600000, 1200000, 180, "published",
     "含灌装、封口、贴标、装箱环节,产能6000瓶/小时。"),
    # 建材
    ("采购30万平方米铝单板", "建材", 300000, "平方米", 120, 200, 60, "open",
     "3mm氟碳喷涂,用于幕墙工程,需提供色卡打样。"),
    ("采购5万吨镀锌钢管", "建材", 50000, "吨", 4500, 6000, 75, "open",
     "DN20-DN100,热镀锌,市政管网项目用。"),
    ("采购10万平米岩棉保温板", "建材", 100000, "平方米", 20, 35, 40, "closed",
     "A级防火,厚度50-100mm,建筑外墙保温。"),
    # 化工产品
    ("采购500吨环保水性涂料", "化工产品", 500, "吨", 8000, 12000, 50, "open",
     "建筑内外墙用,低VOC,需符合GB 18582标准。"),
    ("采购1000吨环氧树脂", "化工产品", 1000, "吨", 12000, 18000, 70, "open",
     "风电叶片用,粘度适中,需提供批次质检报告。"),
    # 能源
    ("采购200MW光伏组件", "能源", 200, "兆瓦", 700000, 900000, 120, "open",
     "182/210尺寸,单晶双面,功率550W+,需TUV认证。"),
    ("采购50台5MW海上风机", "能源", 50, "台", 15000000, 20000000, 240, "published",
     "海上风电项目,含运输吊装,质保5年。"),
    ("采购1000套工商业储能柜", "能源", 1000, "套", 150000, 250000, 90, "open",
     "200kWh-400kWh液冷储能系统,含EMS管理。"),
    # 综合
    ("采购2万套智能门锁", "电子及家电", 20000, "套", 200, 350, 30, "open",
     "指纹+密码+IC卡+APP四合一,锌合金面板。"),
    ("采购1万台商用咖啡机", "电子及家电", 10000, "台", 3000, 6000, 45, "published",
     "办公室场景,全自动研磨,双锅炉,含售后服务。"),
    ("采购3万件陶瓷餐具套装", "建材", 30000, "套", 30, 60, 20, "open",
     "酒店用,釉下彩,微波炉/洗碗机适用。"),
    ("采购8万套五金卫浴挂件", "五金工具", 80000, "套", 25, 50, 35, "open",
     "304不锈钢,含毛巾架/置物架/挂钩,出口欧洲。"),
]


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # 找买家用户(买家优先, 其次游客)
    buyers = cur.execute(
        "SELECT id, username FROM users WHERE role='buyer' ORDER BY id LIMIT 5"
    ).fetchall()
    if not buyers:
        buyers = cur.execute(
            "SELECT id, username FROM users WHERE role='visitor' ORDER BY id LIMIT 5"
        ).fetchall()
    if not buyers:
        print("没有可用的买家/游客账号")
        return
    print(f"买家池: {[b[1] for b in buyers]}")

    now = datetime.now()
    added = 0
    skipped = 0
    for i, (title, cat, qty, unit, bmin, bmax, days, status, desc) in enumerate(PROCUREMENTS):
        exists = cur.execute("SELECT id FROM procurements WHERE title=?", (title,)).fetchone()
        if exists:
            skipped += 1
            continue
        bid, bname = buyers[i % len(buyers)]
        deadline = (now + timedelta(days=days)).strftime("%Y-%m-%d")
        cur.execute(
            "INSERT INTO procurements (exhibition_id, exhibition_title, purchaser_id, purchaser_name, "
            "title, description, category, quantity, unit, budget, budget_min, budget_max, "
            "deadline, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))",
            (None, None, bid, bname, title, desc, cat, qty, unit,
             (bmin + bmax) / 2, bmin, bmax, deadline, status),
        )
        added += 1

    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM procurements").fetchone()[0]
    cats = cur.execute("SELECT COUNT(DISTINCT category) FROM procurements").fetchone()[0]
    conn.close()
    print(f"新增采购需求: {added}, 跳过: {skipped}, 当前总数: {total}, 覆盖分类: {cats}")


if __name__ == "__main__":
    main()
