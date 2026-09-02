#!/usr/bin/env python3
"""
ExpoHub 种子数据生成脚本

生成内容：
- 用户（14个）：1 admin + 3 organizer + 5 exhibitor + 3 buyer + 2 visitor
- 展会（3个，published）：广交会、上海进博会、深圳高交会
- 展位（30个，每展会10个）
- 展品（15个样本展品）
- 采购需求（8条）
- 报名记录
- 评价
- 消息 / 会话

使用方法：
    cd expohub-backend && python3 seed.py
"""

import sys
import os
from datetime import datetime, timezone

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.base import Base, engine, SessionLocal
from app.models.user import User
from app.models.exhibition import Exhibition
from app.models.booth import Booth
from app.models.product import Product
from app.models.procurement import Procurement
from app.models.procurement_match import ProcurementMatch
from app.models.registration import Registration
from app.models.review import Review
from app.models.message import Message, Conversation
from app.models.micro_booth import MicroBooth
from app.models.membership import Membership
from app.models.analytics import AnalyticsEvent
from app.models.points import PointsLedger
from app.models.checkin import CheckIn
# 全模型注册（与 app.main 保持一致）：Exhibition.venue_id 等外键需要对应表在元数据中，
# 否则空库 create_all 报 NoReferencedTableError（本地旧库因表已存在而未暴露此缺陷）
import app.models.venue  # noqa: F401
import app.models.category  # noqa: F401
import app.models.notification  # noqa: F401
import app.models.favorite  # noqa: F401
import app.models.appointment  # noqa: F401
import app.core.audit  # noqa: F401  (audit_logs)
import app.modules.ticketing.models  # noqa: F401  (票务)
import app.modules.onsite.models  # noqa: F401  (现场)
import app.modules.ai.models  # noqa: F401  (AI 用量)
import app.modules.platform.models  # noqa: F401  (平台计费)
from app.core.security import hash_password
from sqlalchemy import func

# ============================================================
# 重置数据库（创建所有表）
# ============================================================
print("🔄 重置数据库...")
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
print("✅ 数据库表已重建")

db = SessionLocal()

try:
    # ============================================================
    # 1. 创建用户（14 个）
    # ============================================================
    print("\n👤 创建用户...")

    users = [
        # --- Admin ---
        User(
            username="admin",
            email="admin@expohub.com",
            password_hash=hash_password("admin123"),
            role="admin",
            status="active",
            nickname="平台管理员",
            phone="13800000000",
            gender="male",
        ),
        # --- Organizers（3个，已通过审核） ---
        User(
            username="organizer_canton",
            email="canton@cantonfair.org.cn",
            password_hash=hash_password("org123"),
            role="organizer",
            status="active",
            organizer_status="approved",
            company_name="中国对外贸易中心",
            business_license="https://images.unsplash.com/photo-1450101499163-c8848c66ca85?w=600&h=400&fit=crop",
            nickname="广交会主办方",
            phone="13800010001",
            gender="male",
        ),
        User(
            username="organizer_ciie",
            email="ciie@ciie.org",
            password_hash=hash_password("org123"),
            role="organizer",
            status="active",
            organizer_status="approved",
            company_name="中国国际进口博览局",
            business_license="https://images.unsplash.com/photo-1450101499163-c8848c66ca85?w=600&h=400&fit=crop",
            nickname="进博会主办方",
            phone="13800010002",
            gender="female",
        ),
        User(
            username="organizer_chtf",
            email="chtf@szonline.net",
            password_hash=hash_password("org123"),
            role="organizer",
            status="active",
            organizer_status="approved",
            company_name="深圳会展中心管理有限公司",
            business_license="https://images.unsplash.com/photo-1450101499163-c8848c66ca85?w=600&h=400&fit=crop",
            nickname="高交会主办方",
            phone="13800010003",
            gender="male",
        ),
        # --- Exhibitors（5个展商） ---
        User(
            username="exhibitor_huawei",
            email="huawei@huawei.com",
            password_hash=hash_password("exh123"),
            role="exhibitor",
            status="active",
            nickname="华为技术",
            company="华为技术有限公司",
            position="市场总监",
            phone="13900020001",
            gender="male",
            industry_domain="电子及家电",
        ),
        User(
            username="exhibitor_dji",
            email="dji@dji.com",
            password_hash=hash_password("exh123"),
            role="exhibitor",
            status="active",
            nickname="大疆创新",
            company="深圳市大疆创新科技有限公司",
            position="展会负责人",
            phone="13900020002",
            gender="male",
            industry_domain="AI/科技",
        ),
        User(
            username="exhibitor_haier",
            email="haier@haier.com",
            password_hash=hash_password("exh123"),
            role="exhibitor",
            status="active",
            nickname="海尔集团",
            company="海尔智家股份有限公司",
            position="海外市场经理",
            phone="13900020003",
            gender="female",
            industry_domain="电子及家电",
        ),
        User(
            username="exhibitor_xiaomi",
            email="xiaomi@xiaomi.com",
            password_hash=hash_password("exh123"),
            role="exhibitor",
            status="active",
            nickname="小米科技",
            company="小米科技有限责任公司",
            position="产品经理",
            phone="13900020004",
            gender="male",
            industry_domain="电子及家电",
        ),
        User(
            username="exhibitor_siemens",
            email="siemens@siemens.com",
            password_hash=hash_password("exh123"),
            role="exhibitor",
            status="active",
            nickname="西门子",
            company="西门子（中国）有限公司",
            position="工业自动化总监",
            phone="13900020005",
            gender="male",
            industry_domain="机械",
        ),
        # --- Buyers（3个买家） ---
        User(
            username="buyer_li",
            email="buyer_li@example.com",
            password_hash=hash_password("buyer123"),
            role="buyer",
            status="active",
            nickname="采购经理李总",
            company="上海鑫达贸易有限公司",
            position="采购经理",
            phone="13800030001",
            gender="male",
        ),
        User(
            username="buyer_wang",
            email="buyer_wang@example.com",
            password_hash=hash_password("buyer123"),
            role="buyer",
            status="active",
            nickname="王采购",
            company="广州万通商贸有限公司",
            position="采购专员",
            phone="13800030002",
            gender="female",
        ),
        User(
            username="buyer_zhang",
            email="buyer_zhang@example.com",
            password_hash=hash_password("buyer123"),
            role="buyer",
            status="active",
            nickname="张总",
            company="深圳创新投资集团",
            position="供应链总监",
            phone="13800030003",
            gender="male",
        ),
        # --- Visitors（2个游客） ---
        User(
            username="visitor_chen",
            email="visitor_chen@example.com",
            password_hash=hash_password("visitor123"),
            role="visitor",
            status="active",
            nickname="小陈",
            phone="13800040001",
            gender="male",
        ),
        User(
            username="visitor_liu",
            email="visitor_liu@example.com",
            password_hash=hash_password("visitor123"),
            role="visitor",
            status="active",
            nickname="刘女士",
            phone="13800040002",
            gender="female",
        ),
    ]

    db.add_all(users)
    db.flush()
    print(f"  ✅ 创建了 {len(users)} 个用户")

    # 方便引用
    admin = users[0]
    org_canton = users[1]
    org_ciie = users[2]
    org_chtf = users[3]
    exh_huawei = users[4]
    exh_dji = users[5]
    exh_haier = users[6]
    exh_xiaomi = users[7]
    exh_siemens = users[8]
    buyer_li = users[9]
    buyer_wang = users[10]
    buyer_zhang = users[11]
    visitor_chen = users[12]
    visitor_liu = users[13]

    # ============================================================
    # 2. 创建展会（3个，published）
    # ============================================================
    print("\n🎪 创建展会...")

    exhibitions = [
        Exhibition(
            title="2026全球人工智能产业交流会",
            description="汇聚全球AI领军企业，覆盖大模型、智能机器人、自动驾驶、AI芯片等前沿领域。已确认参展企业包括华为、百度、商汤、寒武纪等200+企业。、到会采购商最多且分布国别地区最广的综合性国际贸易盛会。本届广交会设电子消费品、家用电器、建材五金、日用消费品、纺织服装等展区，汇聚全球优质供应商。",
            cover_image="https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=800&h=400&fit=crop",
            start_date="2026-09-15T09:00:00+08:00",
            end_date="2026-09-18T18:00:00+08:00",
            location="北京国家会议中心（朝阳区天辰东路7号）",
            status="published",
            organizer_id=org_canton.id,
            organizer_name=org_canton.company_name,
            # V2.0
            is_featured=True,
            hot_score=980,
            visitor_count=25000,
        ),
        Exhibition(
            title="2026国际智能制造与工业互联网交流会",
            description="聚焦工业4.0、数字孪生、5G+工业互联网。西门子、博世、ABB等国际巨头已确认参展，展示最新智能制造解决方案。，是国际贸易发展史上的重大创举。本届进博会设食品及农产品、汽车、技术装备、消费品、医疗器械及医药保健、服务贸易六大展区。",
            cover_image="https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=800&h=400&fit=crop",
            start_date="2026-10-20T09:00:00+08:00",
            end_date="2026-10-23T18:00:00+08:00",
            location="上海世博中心（浦东新区世博大道1500号）",
            status="published",
            organizer_id=org_ciie.id,
            organizer_name=org_ciie.company_name,
            # V2.0
            is_featured=True,
            hot_score=850,
            visitor_count=18000,
        ),
        Exhibition(
            title="2026全球新能源与碳中和产业交流会",
            description="聚焦光伏、储能、氢能、碳交易等绿色科技。宁德时代、比亚迪、隆基绿能等300+企业参展，预计5000+采购商到场。。本届高交会聚焦新一代信息技术、人工智能、新能源、新材料、生物医药等领域，集中展示全球前沿科技成果。",
            cover_image="https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=800&h=400&fit=crop",
            start_date="2026-11-10T09:00:00+08:00",
            end_date="2026-11-13T18:00:00+08:00",
            location="深圳国际会展中心（宝安区福海街道展城路1号）",
            status="published",
            organizer_id=org_chtf.id,
            organizer_name=org_chtf.company_name,
            # V2.0
            is_featured=True,
            hot_score=720,
            visitor_count=12000,
        ),
    ]

    db.add_all(exhibitions)
    db.flush()
    print(f"  ✅ 创建了 {len(exhibitions)} 个展会")

    canton_fair = exhibitions[0]
    ciie = exhibitions[1]
    chtf = exhibitions[2]

    # ============================================================
    # 3. 创建展位（每展会10个，共30个）
    # ============================================================
    print("\n🏢 创建展位...")

    booth_count = 0

    # ---- 广交会展位 ----
    canton_booths = [
        Booth(exhibition_id=canton_fair.id, booth_number="A-001", exhibitor_id=exh_huawei.id, exhibitor_name=exh_huawei.company, company_name=exh_huawei.company, size="9x9m", location_area="A区主厅", price=28000.00, status="occupied", description="主厅黄金展位，三面开放"),
        Booth(exhibition_id=canton_fair.id, booth_number="A-002", exhibitor_id=exh_haier.id, exhibitor_name=exh_haier.company, company_name=exh_haier.company, size="9x6m", location_area="A区主厅", price=22000.00, status="occupied", description="家电展区核心展位，双面开放"),
        Booth(exhibition_id=canton_fair.id, booth_number="A-003", exhibitor_id=None, exhibitor_name=None, company_name=None, size="6x6m", location_area="A区主厅", price=16000.00, status="available", description="标准展位，单面开放"),
        Booth(exhibition_id=canton_fair.id, booth_number="A-004", exhibitor_id=None, exhibitor_name=None, company_name=None, size="6x6m", location_area="A区主厅", price=16000.00, status="available", description="标准展位，单面开放"),
        Booth(exhibition_id=canton_fair.id, booth_number="A-005", exhibitor_id=exh_xiaomi.id, exhibitor_name=exh_xiaomi.company, company_name=exh_xiaomi.company, size="9x9m", location_area="A区主厅", price=28000.00, status="occupied", description="电子消费品展区，三面开放"),
        Booth(exhibition_id=canton_fair.id, booth_number="B-001", exhibitor_id=None, exhibitor_name=None, company_name=None, size="6x3m", location_area="B区侧厅", price=8000.00, status="available", description="经济展位，单面开放"),
        Booth(exhibition_id=canton_fair.id, booth_number="B-002", exhibitor_id=None, exhibitor_name=None, company_name=None, size="6x3m", location_area="B区侧厅", price=8000.00, status="reserved", description="经济展位，单面开放"),
        Booth(exhibition_id=canton_fair.id, booth_number="B-003", exhibitor_id=None, exhibitor_name=None, company_name=None, size="6x3m", location_area="B区侧厅", price=8000.00, status="available", description="经济展位"),
        Booth(exhibition_id=canton_fair.id, booth_number="C-001", exhibitor_id=None, exhibitor_name=None, company_name=None, size="12x12m", location_area="C区户外广场", price=35000.00, status="available", description="大型户外展位，适合机械装备展示"),
        Booth(exhibition_id=canton_fair.id, booth_number="C-002", exhibitor_id=None, exhibitor_name=None, company_name=None, size="12x9m", location_area="C区户外广场", price=30000.00, status="maintenance", description="大型户外展位"),
    ]

    # ---- 进博会展位 ----
    ciie_booths = [
        Booth(exhibition_id=ciie.id, booth_number="TECH-01", exhibitor_id=exh_siemens.id, exhibitor_name=exh_siemens.company, company_name=exh_siemens.company, size="12x12m", location_area="技术装备馆", price=50000.00, status="occupied", description="技术装备馆旗舰展位，四面开放"),
        Booth(exhibition_id=ciie.id, booth_number="TECH-02", exhibitor_id=exh_huawei.id, exhibitor_name=exh_huawei.company, company_name=exh_huawei.company, size="9x9m", location_area="技术装备馆", price=38000.00, status="occupied", description="ICT技术展区核心展位"),
        Booth(exhibition_id=ciie.id, booth_number="TECH-03", exhibitor_id=None, exhibitor_name=None, company_name=None, size="9x6m", location_area="技术装备馆", price=28000.00, status="available", description="工业自动化展区"),
        Booth(exhibition_id=ciie.id, booth_number="TECH-04", exhibitor_id=None, exhibitor_name=None, company_name=None, size="6x6m", location_area="技术装备馆", price=18000.00, status="available", description="标准展位"),
        Booth(exhibition_id=ciie.id, booth_number="CONSUMER-01", exhibitor_id=exh_xiaomi.id, exhibitor_name=exh_xiaomi.company, company_name=exh_xiaomi.company, size="9x9m", location_area="消费品馆", price=35000.00, status="occupied", description="智能消费电子展区"),
        Booth(exhibition_id=ciie.id, booth_number="CONSUMER-02", exhibitor_id=None, exhibitor_name=None, company_name=None, size="9x6m", location_area="消费品馆", price=25000.00, status="available", description="日用品展区"),
        Booth(exhibition_id=ciie.id, booth_number="CONSUMER-03", exhibitor_id=None, exhibitor_name=None, company_name=None, size="6x6m", location_area="消费品馆", price=16000.00, status="available", description="标准展位"),
        Booth(exhibition_id=ciie.id, booth_number="FOOD-01", exhibitor_id=None, exhibitor_name=None, company_name=None, size="9x9m", location_area="食品及农产品馆", price=30000.00, status="available", description="食品展区核心展位"),
        Booth(exhibition_id=ciie.id, booth_number="FOOD-02", exhibitor_id=None, exhibitor_name=None, company_name=None, size="6x6m", location_area="食品及农产品馆", price=18000.00, status="reserved", description="标准展位"),
        Booth(exhibition_id=ciie.id, booth_number="MEDICAL-01", exhibitor_id=None, exhibitor_name=None, company_name=None, size="9x9m", location_area="医疗器械馆", price=42000.00, status="available", description="医疗器械创新展区"),
    ]

    # ---- 高交会展位 ----
    chtf_booths = [
        Booth(exhibition_id=chtf.id, booth_number="AI-01", exhibitor_id=exh_huawei.id, exhibitor_name=exh_huawei.company, company_name=exh_huawei.company, size="9x9m", location_area="人工智能馆", price=32000.00, status="occupied", description="AI大模型展区核心展位"),
        Booth(exhibition_id=chtf.id, booth_number="AI-02", exhibitor_id=exh_dji.id, exhibitor_name=exh_dji.company, company_name=exh_dji.company, size="9x6m", location_area="人工智能馆", price=26000.00, status="occupied", description="智能机器人展区"),
        Booth(exhibition_id=chtf.id, booth_number="AI-03", exhibitor_id=None, exhibitor_name=None, company_name=None, size="6x6m", location_area="人工智能馆", price=15000.00, status="available", description="AI应用展区"),
        Booth(exhibition_id=chtf.id, booth_number="AI-04", exhibitor_id=None, exhibitor_name=None, company_name=None, size="6x6m", location_area="人工智能馆", price=15000.00, status="available", description="标准展位"),
        Booth(exhibition_id=chtf.id, booth_number="NEW-ENERGY-01", exhibitor_id=None, exhibitor_name=None, company_name=None, size="9x9m", location_area="新能源馆", price=30000.00, status="available", description="新能源技术展区"),
        Booth(exhibition_id=chtf.id, booth_number="NEW-ENERGY-02", exhibitor_id=None, exhibitor_name=None, company_name=None, size="9x6m", location_area="新能源馆", price=24000.00, status="available", description="储能技术展区"),
        Booth(exhibition_id=chtf.id, booth_number="BIO-01", exhibitor_id=None, exhibitor_name=None, company_name=None, size="9x9m", location_area="生物医药馆", price=35000.00, status="available", description="生物医药创新展区"),
        Booth(exhibition_id=chtf.id, booth_number="BIO-02", exhibitor_id=None, exhibitor_name=None, company_name=None, size="6x6m", location_area="生物医药馆", price=18000.00, status="reserved", description="标准展位"),
        Booth(exhibition_id=chtf.id, booth_number="5G-01", exhibitor_id=exh_xiaomi.id, exhibitor_name=exh_xiaomi.company, company_name=exh_xiaomi.company, size="9x9m", location_area="5G/物联网馆", price=28000.00, status="occupied", description="5G应用展区"),
        Booth(exhibition_id=chtf.id, booth_number="5G-02", exhibitor_id=exh_siemens.id, exhibitor_name=exh_siemens.company, company_name=exh_siemens.company, size="9x6m", location_area="5G/物联网馆", price=22000.00, status="occupied", description="工业物联网展区"),
    ]

    all_booths = canton_booths + ciie_booths + chtf_booths
    db.add_all(all_booths)
    db.flush()
    print(f"  ✅ 创建了 {len(all_booths)} 个展位（广交会 {len(canton_booths)} + 进博会 {len(ciie_booths)} + 高交会 {len(chtf_booths)}）")

    # ============================================================
    # 4. 创建展品（15个）
    # ============================================================
    print("\n📦 创建展品...")

    products = [
        # --- 华为展品 ---
        Product(booth_id=canton_booths[0].id, exhibition_id=canton_fair.id, exhibitor_id=exh_huawei.id, exhibitor_name=exh_huawei.company, name="华为 Mate 70 Pro", description="搭载麒麟9100芯片，支持卫星通信，XMAGE影像系统", category="智能手机", price=6999.00, unit="台", specs='{"屏幕":"6.82英寸OLED","芯片":"麒麟9100","内存":"12GB+512GB","颜色":["曜金黑","冰霜银"]}', images='["https://picsum.photos/seed/product/600/400","https://picsum.photos/seed/product/600/400"]', stock=500, status="published"),
        Product(booth_id=canton_booths[0].id, exhibition_id=canton_fair.id, exhibitor_id=exh_huawei.id, exhibitor_name=exh_huawei.company, name="华为 MateBook X Pro 2025", description="14.2英寸OLED原色屏，3.1K高分辨率，仅重980g", category="笔记本电脑", price=9999.00, unit="台", specs='{"屏幕":"14.2英寸 OLED 3.1K","CPU":"Intel Ultra 9","内存":"32GB+2TB","重量":"980g"}', images='["https://picsum.photos/seed/product/600/400"]', stock=200, status="published"),
        Product(booth_id=ciie_booths[1].id, exhibition_id=ciie.id, exhibitor_id=exh_huawei.id, exhibitor_name=exh_huawei.company, name="华为 OceanStor 全闪存存储", description="企业级全闪存存储系统，支持NVMe over Fabrics", category="企业存储", price=250000.00, unit="套", specs='{"容量":"500TB","接口":"NVMe-oF 100GbE","IOPS":"100万+","可用性":"99.9999%"}', images='["https://picsum.photos/seed/product/600/400"]', stock=20, status="published"),
        Product(booth_id=chtf_booths[0].id, exhibition_id=chtf.id, exhibitor_id=exh_huawei.id, exhibitor_name=exh_huawei.company, name="华为 Pangu 大模型解决方案", description="盘古大模型5.0，支持千亿参数，覆盖NLP/CV/多模态", category="AI/大模型", price=500000.00, unit="套", specs='{"参数规模":"千亿级","支持模态":"文本/图像/语音/视频","部署方式":"公有云/私有化"}', images='["https://picsum.photos/seed/product/600/400"]', stock=10, status="published"),

        # --- 大疆展品 ---
        Product(booth_id=chtf_booths[1].id, exhibition_id=chtf.id, exhibitor_id=exh_dji.id, exhibitor_name=exh_dji.company, name="大疆 Mavic 4 Pro", description="4/3 CMOS 哈苏相机，全向避障，45分钟续航", category="无人机", price=12888.00, unit="台", specs='{"相机":"4/3 CMOS Hasselblad","续航":"45分钟","图传":"O4 20km","避障":"全向双目"}', images='["https://picsum.photos/seed/product/600/400"]', stock=300, status="published"),
        Product(booth_id=chtf_booths[1].id, exhibition_id=chtf.id, exhibitor_id=exh_dji.id, exhibitor_name=exh_dji.company, name="大疆 RoboMaster EP Core", description="教育机器人，支持Python编程与AI扩展", category="教育机器人", price=5999.00, unit="台", specs='{"控制方式":"Python/Scratch","传感器":"红外/陀螺仪/视觉","扩展":"AI模块兼容"}', images='["https://picsum.photos/seed/product/600/400"]', stock=150, status="published"),

        # --- 海尔展品 ---
        Product(booth_id=canton_booths[1].id, exhibition_id=canton_fair.id, exhibitor_id=exh_haier.id, exhibitor_name=exh_haier.company, name="海尔智慧家庭套装", description="全屋智能家电套装：冰箱+洗衣机+空调+热水器，支持U+互联", category="智能家居", price=25999.00, unit="套", specs='{"包含":"冰箱/洗衣机/空调/热水器","互联":"U+智慧平台","能效":"一级能效"}', images='["https://picsum.photos/seed/product/600/400"]', stock=100, status="published"),
        Product(booth_id=canton_booths[1].id, exhibition_id=canton_fair.id, exhibitor_id=exh_haier.id, exhibitor_name=exh_haier.company, name="海尔鲜风机", description="3D环绕送风，56°C高温自清洁，一级变频节能", category="空调", price=3699.00, unit="台", specs='{"匹数":"1.5匹","能效":"一级变频","自清洁":"56°C高温","送风":"3D环绕"}', images='["https://picsum.photos/seed/product/600/400"]', stock=500, status="published"),

        # --- 小米展品 ---
        Product(booth_id=canton_booths[4].id, exhibition_id=canton_fair.id, exhibitor_id=exh_xiaomi.id, exhibitor_name=exh_xiaomi.company, name="小米 15 Ultra", description="徕卡光学Summilux镜头，骁龙8 Gen 4，小米HyperOS", category="智能手机", price=6499.00, unit="台", specs='{"屏幕":"6.73英寸 LTPO 2K","芯片":"骁龙8 Gen 4","相机":"徕卡1英寸主摄","电池":"5500mAh"}', images='["https://picsum.photos/seed/product/600/400"]', stock=800, status="published"),
        Product(booth_id=ciie_booths[4].id, exhibition_id=ciie.id, exhibitor_id=exh_xiaomi.id, exhibitor_name=exh_xiaomi.company, name="小米 SU7 Ultra", description="纯电轿跑，零百加速2.78秒，800V高压平台", category="智能电动汽车", price=299900.00, unit="辆", specs='{"零百加速":"2.78秒","续航":"830km CLTC","平台":"800V高压","智驾":"Xiaomi Pilot Max"}', images='["https://picsum.photos/seed/product/600/400"]', stock=50, status="published"),

        # --- 西门子展品 ---
        Product(booth_id=ciie_booths[0].id, exhibition_id=ciie.id, exhibitor_id=exh_siemens.id, exhibitor_name=exh_siemens.company, name="西门子 SIMATIC S7-1500", description="高级PLC控制器，支持工业物联网和边缘计算", category="工业自动化", price=15000.00, unit="台", specs='{"CPU":"1518-4 PN/DP","通信":"PROFINET/OPC UA","编程":"TIA Portal V19","冗余":"支持"}', images='["https://picsum.photos/seed/product/600/400"]', stock=80, status="published"),
        Product(booth_id=ciie_booths[0].id, exhibition_id=ciie.id, exhibitor_id=exh_siemens.id, exhibitor_name=exh_siemens.company, name="西门子 MindSphere", description="工业物联网即服务(IoTaaS)平台，数据驱动的数字化解决方案", category="工业物联网", price=200000.00, unit="年/许可", specs='{"部署":"SaaS/私有化","协议":"MQTT/OPC UA/HTTP","分析":"AI/ML内置","安全":"端到端加密"}', images='["https://picsum.photos/seed/product/600/400"]', stock=30, status="published"),
        Product(booth_id=chtf_booths[9].id, exhibition_id=chtf.id, exhibitor_id=exh_siemens.id, exhibitor_name=exh_siemens.company, name="西门子 Xcelerator 数字孪生平台", description="端到端数字孪生解决方案，覆盖产品设计到运维全生命周期", category="数字孪生", price=350000.00, unit="年/许可", specs='{"覆盖":"设计/仿真/制造/运维","集成":"PLM/MES/IoT","协同":"云端多用户","格式":"支持30+CAD"}', images='["https://picsum.photos/seed/product/600/400"]', stock=15, status="published"),

        # V2.3: 多行业展品补充
        Product(booth_id=canton_booths[2].id, exhibition_id=canton_fair.id, exhibitor_id=exh_haier.id, exhibitor_name=exh_haier.company, name="LED智慧路灯", description="智能调光+光伏供电+5G微基站一体化路灯", category="照明", price=8800.00, unit="套", specs='{"功率":"200W LED","供电":"光伏+市电双模","控制":"NB-IoT远程","高度":"8米"}', images='["https://picsum.photos/seed/product/600/400"]', stock=200, status="published"),
        Product(booth_id=canton_booths[3].id, exhibition_id=canton_fair.id, exhibitor_id=exh_xiaomi.id, exhibitor_name=exh_xiaomi.company, name="电动自行车电池包", description="48V20Ah锂电包，适用新国标电动自行车", category="车辆及配件", price=1299.00, unit="组", specs='{"电压":"48V","容量":"20Ah","电芯":"21700三元锂","循环":"800次+"}', images='["https://picsum.photos/seed/product/600/400"]', stock=1000, status="published"),
        Product(booth_id=ciie_booths[2].id, exhibition_id=ciie.id, exhibitor_id=exh_siemens.id, exhibitor_name=exh_siemens.company, name="工业级电动扳手", description="无刷电机+扭矩精准控制，适用于汽车装配线", category="五金工具", price=3200.00, unit="把", specs='{"扭矩":"500-3000Nm","精度":"±3%","电池":"20V/5Ah锂电","重量":"3.8kg"}', images='["https://picsum.photos/seed/product/600/400"]', stock=150, status="published"),
        Product(booth_id=ciie_booths[3].id, exhibition_id=ciie.id, exhibitor_id=exh_dji.id, exhibitor_name=exh_dji.company, name="CNC五轴加工中心", description="高精度五轴联动，适用航空航天精密零件加工", category="机械", price=850000.00, unit="台", specs='{"轴数":"5轴联动","精度":"±0.005mm","转速":"24000rpm","工作台":"Φ800mm"}', images='["https://picsum.photos/seed/product/600/400"]', stock=5, status="published"),
        Product(booth_id=ciie_booths[5].id, exhibition_id=ciie.id, exhibitor_id=exh_haier.id, exhibitor_name=exh_haier.company, name="环保隔热墙体板", description="聚氨酯+岩棉复合板，A级防火，适用于装配式建筑", category="建材", price=168.00, unit="㎡", specs='{"厚度":"75mm","防火":"A级","导热系数":"≤0.022","规格":"1200×3000mm"}', images='["https://picsum.photos/seed/product/600/400"]', stock=5000, status="published"),
        Product(booth_id=chtf_booths[2].id, exhibition_id=chtf.id, exhibitor_id=exh_huawei.id, exhibitor_name=exh_huawei.company, name="碳中和碳管理SaaS平台", description="企业碳排放核算+碳足迹追踪+碳交易辅助决策", category="能源", price=98000.00, unit="年/许可", specs='{"标准":"ISO 14064/GHG Protocol","覆盖":"Scope 1/2/3","功能":"核算/报告/交易","部署":"公有云SaaS"}', images='["https://picsum.photos/seed/product/600/400"]', stock=50, status="published"),
        Product(booth_id=canton_booths[6].id, exhibition_id=canton_fair.id, exhibitor_id=exh_xiaomi.id, exhibitor_name=exh_xiaomi.company, name="智能保温杯", description="OLED温度显示+APP饮水提醒+12小时保温", category="日用消费品", price=199.00, unit="个", specs='{"容量":"450ml","材质":"316不锈钢","保温":"12小时","连接":"蓝牙5.3"}', images='["https://picsum.photos/seed/product/600/400"]', stock=3000, status="published"),
        Product(booth_id=canton_booths[7].id, exhibition_id=canton_fair.id, exhibitor_id=exh_haier.id, exhibitor_name=exh_haier.company, name="定制企业礼品套装", description="笔记本+保温杯+充电宝+U盘 商务四件套定制", category="礼品", price=128.00, unit="套", specs='{"包含":"笔记本/保温杯/充电宝/U盘","定制":"激光Logo","起订":"100套","交货":"7天"}', images='["https://picsum.photos/seed/product/600/400"]', stock=500, status="published"),
        Product(booth_id=ciie_booths[6].id, exhibition_id=ciie.id, exhibitor_id=exh_dji.id, exhibitor_name=exh_dji.company, name="远红外加热背心", description="石墨烯发热膜+5档温控，冬季户外工作保暖", category="纺织服装", price=499.00, unit="件", specs='{"面料":"防风防水牛津布","发热":"石墨烯3区","温控":"5档","电池":"10000mAh USB"}', images='["https://picsum.photos/seed/product/600/400"]', stock=800, status="published"),
        Product(booth_id=ciie_booths[7].id, exhibition_id=ciie.id, exhibitor_id=exh_xiaomi.id, exhibitor_name=exh_xiaomi.company, name="碳纤维安全鞋", description="轻量化碳纤维包头+防刺穿中底+防滑大底", category="鞋类", price=369.00, unit="双", specs='{"标准":"EN ISO 20345 S3","包头":"碳纤维","中底":"凯夫拉防刺","重量":"480g/只"}', images='["https://picsum.photos/seed/product/600/400"]', stock=2000, status="published"),
        Product(booth_id=canton_booths[8].id, exhibition_id=canton_fair.id, exhibitor_id=exh_haier.id, exhibitor_name=exh_haier.company, name="3D浮雕装饰画", description="UV打印+手工上色，现代简约/新中式风格", category="家居装饰品", price=299.00, unit="幅", specs='{"工艺":"UV打印+手工上色","尺寸":"60×80cm","风格":"现代/新中式","材质":"油画布+松木框"}', images='["https://picsum.photos/seed/product/600/400"]', stock=400, status="published"),
        Product(booth_id=ciie_booths[8].id, exhibition_id=ciie.id, exhibitor_id=exh_siemens.id, exhibitor_name=exh_siemens.company, name="冻干即食燕窝", description="马来西亚溯源燕窝，FD航天冻干技术，银碗即食", category="食品", price=598.00, unit="盒/6碗", specs='{"原料":"马来西亚溯源燕窝","工艺":"FD冻干","规格":"6碗/盒","保质期":"18个月"}', images='["https://picsum.photos/seed/product/600/400"]', stock=600, status="published"),
        Product(booth_id=chtf_booths[3].id, exhibition_id=chtf.id, exhibitor_id=exh_huawei.id, exhibitor_name=exh_huawei.company, name="AI辅助诊断系统", description="基于深度学习的CT/MRI影像辅助诊断，已获NMPA三类证", category="医药及医疗保健", price=500000.00, unit="套", specs='{"认证":"NMPA三类/CE MDR","模态":"CT/MRI/X-Ray","病种":"肺结节/骨折/脑出血","准确率":">95%"}', images='["https://picsum.photos/seed/product/600/400"]', stock=8, status="published"),
        Product(booth_id=chtf_booths[4].id, exhibition_id=chtf.id, exhibitor_id=exh_dji.id, exhibitor_name=exh_dji.company, name="展位搭建一站式服务", description="设计+搭建+拆除全包，100+套方案可选", category="综合服务", price=15000.00, unit="次", specs='{"服务":"设计/搭建/拆除","方案":"100+模板","面积":"9-36㎡","周期":"布展前3天"}', images='["https://picsum.photos/seed/product/600/400"]', stock=50, status="published"),
    ]

    db.add_all(products)
    db.flush()
    print(f"  ✅ 创建了 {len(products)} 个展品")

    # ============================================================
    # V2.3: 创建微展位（每个展商一个）
    # ============================================================
    print("\n🏪 创建微展位...")

    micro_booths = [
        MicroBooth(exhibitor_id=exh_huawei.id, name="华为技术微展厅", description="华为技术有限公司官方微展位，展示消费电子和企业级产品", industry_domain="电子及家电", membership_tier="flagship", view_count=1250, search_appearances=89, favorite_count=42),
        MicroBooth(exhibitor_id=exh_dji.id, name="大疆创新微展厅", description="大疆创新科技有限公司微展位，无人机和机器人产品展示", industry_domain="AI/科技", membership_tier="regular", view_count=680, search_appearances=45, favorite_count=18),
        MicroBooth(exhibitor_id=exh_haier.id, name="海尔智慧家庭微展厅", description="海尔集团官方微展位，智能家居和家电产品展示", industry_domain="电子及家电", membership_tier="regular", view_count=920, search_appearances=56, favorite_count=31),
        MicroBooth(exhibitor_id=exh_xiaomi.id, name="小米生态链微展厅", description="小米科技微展位，手机和智能生态产品展示", industry_domain="电子及家电", membership_tier="flagship", view_count=1580, search_appearances=102, favorite_count=67),
        MicroBooth(exhibitor_id=exh_siemens.id, name="西门子工业微展厅", description="西门子数字化工业集团微展位，工业自动化和数字化解决方案", industry_domain="机械", membership_tier="regular", view_count=430, search_appearances=28, favorite_count=12),
    ]
    # ============================================================
    # V2.8: 1000+微展位，分18类，大量展品分流到微展位
    # ============================================================
    print("Creating 1000+ micro-booths...")
    from app.models.micro_booth import MicroBooth
    from app.models.membership import Membership, TIER_PRODUCT_LIMITS
    import random; random.seed(42)

    all_domains = [
        "电子及家电","照明","车辆及配件","五金工具","机械","建材",
        "化工产品","能源","日用消费品","礼品","纺织服装","鞋类",
        "家居装饰品","办公箱包及休闲用品","食品","医药及医疗保健","AI/科技","综合服务"
    ]
    # 生成虚拟展商名称
    fake_companies = [
        "明达","鑫源","华创","天工","瑞丰","博远","中科","鼎新","恒通","万联",
        "嘉和","永泰","正大","兰德","创智","领航","先锋","卓越","经纬","腾飞",
        "国光","东方","新视界","云帆","星辰","银河","极光","曙光","昆仑","长城",
    ]
    
    all_exhs = db.query(User).filter(User.role == "exhibitor").all()
    batch = []
    mb_count = 0
    
    # 1000+微展位: 700 free + 250 regular + 50 flagship
    tiers_plan = ["free"] * 700 + ["regular"] * 250 + ["flagship"] * 50
    
    for i, tier in enumerate(tiers_plan):
        domain = all_domains[i % len(all_domains)]
        company = random.choice(fake_companies)
        name = f"{company}{random.choice(['科技','电子','实业','制造','贸易','智能'])}-{domain}"
        mb = MicroBooth(
            exhibitor_id=random.choice(all_exhs).id,
            name=name,
            description=f"{domain}领域·{tier}级微展位",
            industry_domain=domain,
            membership_tier=tier,
            view_count=random.randint(0, 500),
            favorite_count=random.randint(0, 30),
        )
        db.add(mb)
        batch.append(mb)
        mb_count += 1
        if len(batch) >= 200:
            db.flush()
            batch = []
    db.flush()
    
    # 给种子微展位分配展品（按等级限额）
    all_mbs = db.query(MicroBooth).all()
    print(f"  ✅ 创建了 {len(all_mbs)} 个微展位")
    
    assigned = 0
    for mb in all_mbs:
        limit = TIER_PRODUCT_LIMITS.get(mb.membership_tier, 3)
        if limit == 0: limit = 50
        prods = db.query(Product).filter(
            Product.exhibitor_id == mb.exhibitor_id,
            Product.micro_booth_id == None,
        ).order_by(func.random()).limit(limit).all()
        for p in prods:
            p.micro_booth_id = mb.id
            assigned += 1
    db.flush()
    print(f"  ✅ {assigned}展品分配到{len(all_mbs)}微展位")
    
    # 会员记录
    for exh in all_exhs:
        if not db.query(Membership).filter(Membership.user_id == exh.id).first():
            db.add(Membership(user_id=exh.id, tier="regular", product_limit=8))
    db.flush()

    # ============================================================
    # 5. 创建采购需求（8条）
    # ============================================================
    print("\n📋 创建采购需求...")

    procurements = [
        Procurement(
            exhibition_id=canton_fair.id,
            exhibition_title=canton_fair.title,
            purchaser_id=buyer_li.id,
            purchaser_name=buyer_li.company,
            title="采购1000台智能空调",
            description="需要一级能效变频空调，适用于东南亚市场，电压220V/50Hz，需有CE或CB认证",
            category="家用电器",
            quantity=1000,
            unit="台",
            budget=3000000.00,
            budget_min=2500000.00,
            budget_max=3500000.00,
            deadline="2025-05-15T23:59:59+08:00",
            status="pending",
        ),
        Procurement(
            exhibition_id=canton_fair.id,
            exhibition_title=canton_fair.title,
            purchaser_id=buyer_wang.id,
            purchaser_name=buyer_wang.company,
            title="采购5000件厨房小家电套装",
            description="套装包含：电饭煲+电磁炉+电热水壶+榨汁机，需提供多色可选方案，目标市场：中东地区",
            category="小家电",
            quantity=5000,
            unit="套",
            budget=5000000.00,
            deadline="2025-05-20T23:59:59+08:00",
            status="pending",
        ),
        Procurement(
            exhibition_id=ciie.id,
            exhibition_title=ciie.title,
            purchaser_id=buyer_zhang.id,
            purchaser_name=buyer_zhang.company,
            title="采购工业自动化产线解决方案",
            description="需要完整的PLC+SCADA+MES系统集成方案，适用于汽车零部件制造业，年产100万件",
            category="工业自动化",
            quantity=1,
            unit="套",
            budget=5000000.00,
            budget_min=3000000.00,
            budget_max=8000000.00,
            deadline="2025-11-30T23:59:59+08:00",
            status="pending",
        ),
        Procurement(
            exhibition_id=ciie.id,
            exhibition_title=ciie.title,
            purchaser_id=buyer_li.id,
            purchaser_name=buyer_li.company,
            title="采购进口红酒全年供应",
            description="法国波尔多产区AOC级红酒，年供应量50000瓶，需提供原产地证明及中国进口资质",
            category="食品饮料",
            quantity=50000,
            unit="瓶",
            budget=8000000.00,
            deadline="2025-12-31T23:59:59+08:00",
            status="pending",
        ),
        Procurement(
            exhibition_id=ciie.id,
            exhibition_title=ciie.title,
            purchaser_id=buyer_wang.id,
            purchaser_name=buyer_wang.company,
            title="采购医疗影像设备",
            description="需要CT/MRI/X光三合一影像中心方案，适用于二级甲等医院，预算含安装调试及3年维保",
            category="医疗器械",
            quantity=1,
            unit="套",
            budget=15000000.00,
            budget_min=10000000.00,
            budget_max=20000000.00,
            deadline="2025-11-25T23:59:59+08:00",
            status="pending",
        ),
        Procurement(
            exhibition_id=chtf.id,
            exhibition_title=chtf.title,
            purchaser_id=buyer_zhang.id,
            purchaser_name=buyer_zhang.company,
            title="采购AI训练服务器集群",
            description="需要10节点GPU计算集群，单节点8xH100，支持NVLink，需包含RoCE网络互联方案",
            category="AI基础设施",
            quantity=10,
            unit="节点",
            budget=20000000.00,
            budget_min=15000000.00,
            budget_max=25000000.00,
            deadline="2025-11-25T23:59:59+08:00",
            status="pending",
        ),
        Procurement(
            exhibition_id=chtf.id,
            exhibition_title=chtf.title,
            purchaser_id=buyer_li.id,
            purchaser_name=buyer_li.company,
            title="采购商用光伏储能系统",
            description="100kW光伏+200kWh储能，适用于工业园区峰谷套利，需提供EMC合同能源管理模式",
            category="新能源",
            quantity=1,
            unit="套",
            budget=3000000.00,
            deadline="2025-12-15T23:59:59+08:00",
            status="pending",
        ),
        Procurement(
            exhibition_id=chtf.id,
            exhibition_title=chtf.title,
            purchaser_id=buyer_wang.id,
            purchaser_name=buyer_wang.company,
            title="采购无人机巡检系统",
            description="工业级无人机+AI缺陷识别+自动航线规划，用于电力线路巡检，覆盖100km线路",
            category="无人机/巡检",
            quantity=3,
            unit="套",
            budget=1500000.00,
            budget_min=1000000.00,
            budget_max=2000000.00,
            deadline="2025-12-01T23:59:59+08:00",
            status="matched",
        ),
    ]

    db.add_all(procurements)
    db.flush()
    print(f"  ✅ 创建了 {len(procurements)} 条采购需求")

    # ============================================================
    # 6. 创建采购匹配记录
    # ============================================================
    print("\n🔗 创建采购匹配记录...")

    matches = [
        ProcurementMatch(
            procurement_id=procurements[7].id,  # 无人机巡检
            exhibitor_id=exh_dji.id,
            product_id=products[4].id,  # Mavic 4 Pro
            message="大疆行业版无人机解决方案，可提供定制化巡检套装，包含Matrice 350 RTK + H20T相机 + 航线规划软件",
            quoted_price=1200000.00,
            is_accepted=False,
        ),
        ProcurementMatch(
            procurement_id=procurements[2].id,  # 工业自动化
            exhibitor_id=exh_siemens.id,
            product_id=products[11].id,  # SIMATIC S7-1500
            message="西门子提供完整的TIA Portal + SIMATIC + WinCC方案，支持OPC UA与上层MES无缝集成",
            quoted_price=4500000.00,
            is_accepted=False,
        ),
        ProcurementMatch(
            procurement_id=procurements[6].id,  # 光伏储能
            exhibitor_id=exh_huawei.id,
            product_id=None,
            message="华为数字能源FusionSolar智能光伏解决方案，支持AI发电预测与智能运维",
            quoted_price=2800000.00,
            is_accepted=False,
        ),
    ]

    db.add_all(matches)
    db.flush()
    print(f"  ✅ 创建了 {len(matches)} 条采购匹配")

    # ============================================================
    # 7. 创建报名记录
    # ============================================================
    print("\n🎫 创建报名记录...")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+08:00")

    registrations = [
        Registration(visitor_id=visitor_chen.id, exhibition_id=canton_fair.id, is_favorite=True, is_registered=True, ticket_code="CF2025-00001"),
        Registration(visitor_id=visitor_chen.id, exhibition_id=chtf.id, is_favorite=True, is_registered=True, ticket_code="CHTF2025-00001"),
        Registration(visitor_id=visitor_liu.id, exhibition_id=ciie.id, is_favorite=True, is_registered=True, ticket_code="CIIE2025-00001"),
        Registration(visitor_id=buyer_li.id, exhibition_id=canton_fair.id, is_favorite=True, is_registered=True, ticket_code="CF2025-B00001"),
        Registration(visitor_id=buyer_li.id, exhibition_id=ciie.id, is_favorite=False, is_registered=True, ticket_code="CIIE2025-B00001"),
        Registration(visitor_id=buyer_wang.id, exhibition_id=canton_fair.id, is_favorite=True, is_registered=True, ticket_code="CF2025-B00002"),
        Registration(visitor_id=buyer_wang.id, exhibition_id=chtf.id, is_favorite=False, is_registered=True, ticket_code="CHTF2025-B00002"),
        Registration(visitor_id=buyer_zhang.id, exhibition_id=chtf.id, is_favorite=True, is_registered=True, ticket_code="CHTF2025-B00003"),
        Registration(visitor_id=buyer_zhang.id, exhibition_id=ciie.id, is_favorite=True, is_registered=True, ticket_code="CIIE2025-B00003"),
    ]

    db.add_all(registrations)
    db.flush()
    print(f"  ✅ 创建了 {len(registrations)} 条报名记录")

    # ============================================================
    # 8. 创建评价
    # ============================================================
    print("\n⭐ 创建评价...")

    reviews = [
        Review(exhibition_id=canton_fair.id, booth_id=canton_booths[0].id, reviewer_id=buyer_li.id, reviewer_name=buyer_li.company, target_type="booth", target_id=canton_booths[0].id, rating=5, content="华为展位产品线丰富，工作人员专业热情，合作洽谈顺利！", created_at="2025-04-20T14:30:00+08:00"),
        Review(exhibition_id=canton_fair.id, booth_id=canton_booths[1].id, reviewer_id=buyer_wang.id, reviewer_name=buyer_wang.company, target_type="booth", target_id=canton_booths[1].id, rating=4, content="海尔智慧家庭体验区很棒，产品展示清晰，希望增加更多海外适配型号", created_at="2025-04-21T10:00:00+08:00"),
        Review(exhibition_id=canton_fair.id, booth_id=None, reviewer_id=visitor_chen.id, reviewer_name="小陈", target_type="exhibition", target_id=canton_fair.id, rating=5, content="广交会一如既往的规模宏大！参展商质量很高，找到了很多潜在合作方", created_at="2025-04-25T16:00:00+08:00"),
        Review(exhibition_id=ciie.id, booth_id=ciie_booths[0].id, reviewer_id=buyer_zhang.id, reviewer_name=buyer_zhang.company, target_type="booth", target_id=ciie_booths[0].id, rating=5, content="西门子工业4.0方案非常先进，对我们工厂数字化升级很有启发", created_at="2025-11-07T11:00:00+08:00"),
        Review(exhibition_id=chtf.id, booth_id=chtf_booths[1].id, reviewer_id=buyer_zhang.id, reviewer_name=buyer_zhang.company, target_type="booth", target_id=chtf_booths[1].id, rating=5, content="大疆的行业无人机系列非常出色，已预约进一步技术交流", created_at="2025-11-17T09:30:00+08:00"),
        Review(exhibition_id=chtf.id, booth_id=chtf_booths[0].id, reviewer_id=visitor_liu.id, reviewer_name="刘女士", target_type="booth", target_id=chtf_booths[0].id, rating=4, content="华为盘古大模型演示很震撼，希望对外开放更多API试用", created_at="2025-11-18T14:00:00+08:00"),
    ]

    db.add_all(reviews)
    db.flush()
    print(f"  ✅ 创建了 {len(reviews)} 条评价")

    # ============================================================
    # 9. 创建消息和会话
    # ============================================================
    print("\n💬 创建消息/会话...")

    conversations = [
        Conversation(user1_id=buyer_zhang.id, user2_id=exh_dji.id, unread_count=2, updated_at="2025-11-17T10:00:00+08:00"),
        Conversation(user1_id=buyer_li.id, user2_id=exh_huawei.id, unread_count=0, updated_at="2025-04-20T15:00:00+08:00"),
        Conversation(user1_id=buyer_wang.id, user2_id=exh_haier.id, unread_count=1, updated_at="2025-04-21T11:00:00+08:00"),
    ]

    db.add_all(conversations)
    db.flush()

    messages = [
        Message(conversation_id=conversations[0].id, sender_id=buyer_zhang.id, sender_name=buyer_zhang.company, receiver_id=exh_dji.id, title="关于无人机巡检方案", content="您好，我们看了贵司在高交会的无人机展品，想了解行业巡检的定制方案", is_read=True, read_at="2025-11-17T10:05:00+08:00", created_at="2025-11-17T09:50:00+08:00"),
        Message(conversation_id=conversations[0].id, sender_id=exh_dji.id, sender_name=exh_dji.company, receiver_id=buyer_zhang.id, title="回复：关于无人机巡检方案", content="您好张总！我们的Matrice 350 RTK配合H20T相机非常适合电力巡检场景，可以安排演示飞行。请问您主要巡检什么类型的线路？", is_read=False, created_at="2025-11-17T10:00:00+08:00"),
        Message(conversation_id=conversations[1].id, sender_id=buyer_li.id, sender_name=buyer_li.company, receiver_id=exh_huawei.id, title="华为企业存储询价", content="您好，我们对OceanStor全闪存存储很感兴趣，能否提供针对500TB场景的详细报价和技术方案？", is_read=True, read_at="2025-04-20T14:45:00+08:00", created_at="2025-04-20T14:30:00+08:00"),
        Message(conversation_id=conversations[1].id, sender_id=exh_huawei.id, sender_name=exh_huawei.company, receiver_id=buyer_li.id, title="回复：华为企业存储询价", content="李总您好！感谢关注。500TB全闪方案我们推荐OceanStor Dorado 8000 V6，已发送详细方案到您邮箱，请查收", is_read=True, read_at="2025-04-20T15:00:00+08:00", created_at="2025-04-20T14:50:00+08:00"),
        Message(conversation_id=conversations[2].id, sender_id=buyer_wang.id, sender_name=buyer_wang.company, receiver_id=exh_haier.id, title="空调大单询价", content="您好，我们计划采购1000台智能空调出口东南亚，需要了解你们的海外支持能力", is_read=True, read_at="2025-04-21T10:30:00+08:00", created_at="2025-04-21T10:15:00+08:00"),
        Message(conversation_id=conversations[2].id, sender_id=exh_haier.id, sender_name=exh_haier.company, receiver_id=buyer_wang.id, title="回复：空调大单询价", content="王经理您好！海尔在东南亚有完整的售后服务体系，我们可以提供220V/50Hz适配版本及CE认证，期待进一步沟通！", is_read=False, created_at="2025-04-21T11:00:00+08:00"),
    ]

    db.add_all(messages)
    db.flush()
    print(f"  ✅ 创建了 {len(conversations)} 个会话 + {len(messages)} 条消息")

    # ============================================================
    # 提交
    # ============================================================
    db.commit()
    print("\n" + "=" * 60)
    print("🎉 种子数据生成完毕！")
    print("=" * 60)
    print(f"""
📊 数据统计：
  👤 用户:       {len(users)} 个（admin×1, organizer×3, exhibitor×5, buyer×3, visitor×2）
  🎪 展会:       {len(exhibitions)} 个（广交会、进博会、高交会）
  🏢 展位:       {len(all_booths)} 个（每展会10个）
  📦 展品:       {len(products)} 个
  📋 采购需求:   {len(procurements)} 条
  🔗 采购匹配:   {len(matches)} 条
  🎫 报名:       {len(registrations)} 条
  ⭐ 评价:       {len(reviews)} 条
  💬 会话:       {len(conversations)} 个
  ✉️  消息:       {len(messages)} 条

🔑 测试账号（密码统一为对应后缀）：
  admin   → admin / admin123
  organizer_canton / org123
  exhibitor_huawei / exh123
  buyer_li / buyer123
  visitor_chen / visitor123
""")

except Exception as e:
    db.rollback()
    print(f"\n❌ 错误: {e}")
    raise
finally:
    db.close()
