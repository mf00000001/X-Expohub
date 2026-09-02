#!/usr/bin/env python3
"""
演示虚拟数据补充（幂等，可重复执行）

- 采购需求：+24 条（覆盖电子/机械/软件/物流等更多分类，未来截止日期，多买家）
- 微展位：+36 个（挂靠现有展商/展会，三级会员档位）

运行:
    cd expohub-backend && python seed_demo_extra.py      # 本地
    docker cp seed_demo_extra.py expohub-api:/app/ && docker exec expohub-api python seed_demo_extra.py
"""
import sys, os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.base import Base, engine, SessionLocal
import app.models.venue  # noqa: F401
import app.models.category  # noqa: F401
import app.models.notification  # noqa: F401
import app.models.favorite  # noqa: F401
import app.models.appointment  # noqa: F401
import app.models.analytics  # noqa: F401
import app.models.points  # noqa: F401
import app.models.checkin  # noqa: F401
import app.models.micro_booth  # noqa: F401
import app.models.membership  # noqa: F401
import app.core.audit  # noqa: F401
import app.modules.ticketing.models  # noqa: F401
import app.modules.onsite.models  # noqa: F401
import app.modules.ai.models  # noqa: F401
import app.modules.platform.models  # noqa: F401
from app.models.procurement import Procurement
from app.models.micro_booth import MicroBooth
from app.models.exhibition import Exhibition
from app.models.user import User

Base.metadata.create_all(bind=engine)
db = SessionLocal()

now = datetime.now(timezone.utc)

# ---------------- 采购需求（title 去重） ----------------
# (标题, 分类, 数量, 单位, 预算下限万, 预算上限万, 截止, 状态, 买家用户名)
PROC_SPECS = [
    ("采购3000套智能门锁模组", "电子及家电", 3000, "套", 120, 180, "2026-10-15T23:59:59+08:00", "pending", "buyer_li"),
    ("采购10万只Type-C连接器", "电子及家电", 100000, "只", 30, 50, "2026-10-20T23:59:59+08:00", "pending", "buyer_li"),
    ("采购800台工业平板电脑", "工业自动化", 800, "台", 240, 320, "2026-10-30T23:59:59+08:00", "pending", "buyer_li"),
    ("采购柔性电路板FPC 5万片", "电子及家电", 50000, "片", 60, 90, "2026-11-05T23:59:59+08:00", "pending", "buyer_wang"),
    ("采购3套AGV智能仓储系统", "物流与仓储", 3, "套", 450, 700, "2026-11-10T23:59:59+08:00", "pending", "buyer_wang"),
    ("采购200台六轴协作机器人", "工业自动化", 200, "台", 600, 900, "2026-11-15T23:59:59+08:00", "pending", "buyer_wang"),
    ("采购5000吨再生铜材", "新材料", 5000, "吨", 3200, 3800, "2026-10-25T23:59:59+08:00", "pending", "buyer_zhang"),
    ("采购2套锂电池储能系统(10MWh)", "新能源", 2, "套", 1200, 1600, "2026-11-20T23:59:59+08:00", "pending", "buyer_zhang"),
    ("采购1000套光伏逆变器", "新能源", 1000, "套", 350, 500, "2026-12-01T23:59:59+08:00", "pending", "buyer_zhang"),
    ("采购数字孪生工厂平台License", "软件与SaaS", 1, "套", 150, 250, "2026-10-31T23:59:59+08:00", "pending", "visitor_chen"),
    ("采购会展扫码核销一体机80台", "智能硬件", 80, "台", 40, 60, "2026-10-12T23:59:59+08:00", "pending", "visitor_chen"),
    ("采购全息投影展示设备15套", "视听设备", 15, "套", 90, 130, "2026-10-18T23:59:59+08:00", "pending", "visitor_chen"),
    ("采购参展商CRM系统定制开发", "软件与SaaS", 1, "项", 60, 100, "2026-11-08T23:59:59+08:00", "pending", "visitor_liu"),
    ("采购展台搭建环保材料一批", "建材", 1, "批", 80, 120, "2026-10-22T23:59:59+08:00", "pending", "visitor_liu"),
    ("采购会议同传耳机500副", "视听设备", 500, "副", 25, 40, "2026-10-28T23:59:59+08:00", "pending", "visitor_liu"),
    ("采购智能温控包装箱2000个", "包装印刷", 2000, "个", 60, 90, "2026-11-12T23:59:59+08:00", "pending", "buyer_li"),
    ("采购高精度压力传感器1万只", "仪器仪表", 10000, "只", 150, 220, "2026-11-18T23:59:59+08:00", "pending", "buyer_wang"),
    ("采购5G工业网关1000台", "通信设备", 1000, "台", 100, 150, "2026-11-25T23:59:59+08:00", "pending", "buyer_wang"),
    ("采购无人机巡检服务(1年期)", "无人机/巡检", 1, "项", 90, 140, "2026-11-30T23:59:59+08:00", "pending", "buyer_zhang"),
    ("采购AI质检视觉相机300套", "AI基础设施", 300, "套", 200, 280, "2026-12-05T23:59:59+08:00", "pending", "buyer_zhang"),
    ("采购健康检测一体机1200台", "医疗器械", 1200, "台", 300, 420, "2026-12-10T23:59:59+08:00", "pending", "buyer_li"),
    ("采购冷链物流车改装30辆", "物流与仓储", 30, "辆", 900, 1200, "2026-12-15T23:59:59+08:00", "pending", "buyer_wang"),
    ("采购展会双语翻译服务(3天)", "会展服务", 1, "项", 15, 25, "2026-10-09T23:59:59+08:00", "pending", "visitor_chen"),
    ("采购定制企业礼品套装5000份", "礼品", 5000, "份", 50, 80, "2026-11-22T23:59:59+08:00", "pending", "visitor_liu"),
]

existing_proc = {p.title for p in db.query(Procurement).all()}
added_p = 0
users = {u.username: u for u in db.query(User).filter(User.username.in_([s[8] for s in PROC_SPECS])).all()}
for title, cat, qty, unit, bmin_w, bmax_w, deadline, status, buyer in PROC_SPECS:
    if title in existing_proc:
        continue
    u = users.get(buyer)
    db.add(Procurement(
        exhibition_id=None, exhibition_title=None,
        purchaser_id=u.id if u else None,
        purchaser_name=(u.company or u.nickname or u.username) if u else buyer,
        title=title, description=f"演示需求：{title}，欢迎相关展商应标报价。",
        category=cat, quantity=qty, unit=unit,
        budget_min=bmin_w * 10000, budget_max=bmax_w * 10000,
        deadline=deadline, status=status,
        created_at=now, updated_at=now,
    ))
    added_p += 1
db.commit()
print(f"✅ 采购需求新增 {added_p} 条（去重后）")

# ---------------- 微展位（name 去重） ----------------
MB_SPECS = [
    # (名称, 行业域, 展位说明, tier, 展会id)
    ("深圳蓝海智造", "机械", "专注精密减速机与机器人关节模组", "regular", 2),
    ("苏州晶圆材料", "新材料", "半导体级硅片与靶材供应商", "flagship", 2),
    ("杭州云枢软件", "软件与SaaS", "会展数字化SaaS一站式平台", "regular", 1),
    ("东莞芯连电子", "电子及家电", "高速连接器与线束方案商", "regular", 2),
    ("广州智巡无人机", "无人机/巡检", "工业巡检无人机及机巢", "flagship", 3),
    ("佛山储能绿能", "新能源", "工商业储能与光伏配套", "flagship", 3),
    ("宁波精密仪器", "仪器仪表", "压力/流量传感器制造商", "regular", 2),
    ("青岛冷链装备", "物流与仓储", "疫苗级冷链箱与温控物流", "regular", 3),
    ("上海数模视效", "视听设备", "全息投影与LED屏整体方案", "regular", 1),
    ("北京极简会展", "会展服务", "大型会展主场运营服务商", "flagship", 1),
    ("深圳智联网关", "通信设备", "5G工业网关与边缘计算", "flagship", 2),
    ("成都健康物联", "医疗器械", "家用健康检测一体机", "regular", 1),
    ("厦门绿色包装", "包装印刷", "可降解缓冲包装与智能温控箱", "free", 3),
    ("无锡激光智造", "机械", "光纤激光切割与焊接设备", "regular", 2),
    ("上海礼遇文创", "礼品", "企业定制礼赠与伴手礼", "free", 1),
    ("深圳视觉鹰眼", "AI基础设施", "工业AI质检相机与算法平台", "flagship", 2),
    ("常州工控魔方", "工业自动化", "PLC与运动控制解决方案", "regular", 2),
    ("武汉北斗时空", "AI/科技", "北斗高精度定位模组", "regular", 1),
    ("天津海工防腐", "化工产品", "海洋工程重防腐涂料", "free", 3),
    ("重庆商用车电", "新能源", "新能源商用车三电系统", "flagship", 3),
    ("金华日用优选", "日用消费品", "智能家居日用百货供应链", "free", 3),
    ("合肥屏显未来", "电子及家电", "Mini-LED显示模组", "regular", 1),
    ("汕头玩具出海", "礼品", "潮玩与IP衍生品出海供应链", "free", 1),
    ("大连重工轴承", "机械", "风电与工程机械大型轴承", "regular", 3),
    ("南昌医药包装", "医药及医疗保健", "药用包装材料与泡罩", "free", 3),
    ("石家庄节能水泵", "机械", "高效节能工业水泵", "free", 2),
    ("西安军工电子", "电子及家电", "高可靠军工级连接器", "regular", 2),
    ("长沙智能厨电", "小家电", "全自动炒菜机与厨房电器", "free", 3),
    ("南京数据中台", "软件与SaaS", "企业数据中台与BI服务", "regular", 1),
    ("洛阳轴承检测", "仪器仪表", "轴承振动检测成套设备", "free", 2),
    ("济南医疗影像", "医疗器械", "便携式超声与影像设备", "regular", 1),
    ("福州光伏支架", "新能源", "光伏跟踪支架系统", "free", 3),
    ("贵阳大数据云", "AI/科技", "行业大模型微调与推理服务", "flagship", 1),
    ("哈尔滨寒地装备", "机械", "寒地工程机械与除雪装备", "free", 3),
    ("嘉兴新材料膜", "新材料", "光学功能膜材料", "regular", 1),
    ("柳州工程机械", "机械", "装载机与挖掘机整机出口", "regular", 3),
]

existing_mb = {m.name for m in db.query(MicroBooth).all()}
exhibitor_ids = [u.id for u in db.query(User).filter(User.role == "exhibitor").order_by(User.id).all()]
exh_ids = [e.id for e in db.query(Exhibition).all()]
added_m = 0
import random
random.seed(42)
for i, (name, domain, desc, tier, exid) in enumerate(MB_SPECS):
    if name in existing_mb:
        continue
    ex_id = exid if exid in exh_ids else (exh_ids[i % len(exh_ids)] if exh_ids else None)
    owner = exhibitor_ids[i % len(exhibitor_ids)] if exhibitor_ids else None
    db.add(MicroBooth(
        exhibitor_id=owner, exhibition_id=ex_id, name=name,
        description=desc, logo_url="",
        industry_domain=domain, membership_tier=tier,
        view_count=random.randint(60, 900), search_appearances=random.randint(10, 300),
        favorite_count=random.randint(0, 80), status="active",
        created_at=now, updated_at=now,
    ))
    added_m += 1
db.commit()
print(f"✅ 微展位新增 {added_m} 个（去重后）")
print(f"\n当前总量: 微展位 {db.query(MicroBooth).count()} | 采购需求 {db.query(Procurement).count()}")
db.close()
