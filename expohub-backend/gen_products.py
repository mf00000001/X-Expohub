#!/usr/bin/env python3
"""
批量生成10000个不雷同展品
用法: cd expohub-backend && python3 gen_products.py
"""

import sys, os, json, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.base import SessionLocal
from app.models.user import User
from app.models.exhibition import Exhibition
from app.models.booth import Booth
from app.models.product import Product
from sqlalchemy import func

random.seed(42)

db = SessionLocal()

# 获取现有数据
exhibitors = db.query(User).filter(User.role == "exhibitor").all()
exhibitions = db.query(Exhibition).filter(Exhibition.status == "published").all()
booths = db.query(Booth).all()

# 18个行业的产品模板
CATEGORIES = {
    "电子及家电": {
        "prefix": ["智能", "超薄", "节能", "变频", "AI", "物联网", "5G", "曲面", "量子点", "MiniLED",
                   "OLED", "激光", "纳米", "无线", "降噪", "环绕", "便携", "折叠", "透明", "全息"],
        "product": ["电视", "冰箱", "洗衣机", "空调", "微波炉", "电饭煲", "扫地机器人", "空气净化器",
                    "音箱", "耳机", "手机充电器", "数据线", "移动电源", "智能音箱", "投影仪",
                    "吸尘器", "电风扇", "热水器", "净水器", "洗碗机"],
        "suffix": ["Pro", "Max", "Ultra", "Lite", "Plus", "X", "S", "Elite", "Smart", "AI版"],
        "brands": ["华为", "小米", "海尔", "美的", "格力", "TCL", "海信", "创维", "长虹", "奥克斯"],
        "price_range": (199, 29999),
        "unit": "台",
    },
    "照明": {
        "prefix": ["LED", "太阳能", "感应", "RGB", "护眼", "无频闪", "可调色温", "超薄面板",
                   "线性", "轨道式", "嵌入式", "户外防水", "植物生长", "紫外线消毒", "氛围"],
        "product": ["筒灯", "射灯", "面板灯", "灯带", "工矿灯", "投光灯", "路灯", "台灯",
                    "壁灯", "吊灯", "吸顶灯", "地埋灯", "线条灯", "洗墙灯", "应急灯"],
        "suffix": ["COB", "SMD", "高显指", "IP65", "DALI调光", "0-10V", "Zigbee", "WiFi版"],
        "brands": ["欧普", "雷士", "佛山照明", "三雄极光", "阳光照明", "飞利浦", "松下", "欧司朗", "木林森", "得邦"],
        "price_range": (29, 8999),
        "unit": "套",
    },
    "车辆及配件": {
        "prefix": ["新能源", "纯电", "混动", "轻量化", "碳纤维", "锻造", "CNC", "高性能",
                   "越野", "城市", "折叠", "快充", "液冷", "固态电池", "氢燃料"],
        "product": ["电动自行车", "电动摩托车", "汽车大灯", "行车记录仪", "车载冰箱",
                    "轮胎", "刹车片", "减震器", "轮毂", "电池包", "电机控制器", "充电桩",
                    "车载逆变器", "车衣", "座椅套"],
        "suffix": ["长续航版", "性能版", "Pro", "运动型", "豪华版", "基础款", "增强型", "快充版"],
        "brands": ["比亚迪", "蔚来", "小鹏", "理想", "宁德时代", "博世", "大陆", "米其林", "固特异", "3M"],
        "price_range": (99, 299900),
        "unit": "件",
    },
    "五金工具": {
        "prefix": ["工业级", "家用", "锂电", "无刷", "气动", "液压", "数显", "激光",
                   "快换", "防爆", "绝缘", "高精度", "大扭矩", "静音", "迷你"],
        "product": ["电钻", "角磨机", "冲击扳手", "热风枪", "测距仪", "水平仪",
                    "螺丝刀套装", "套筒扳手", "钳子", "卷尺", "电烙铁", "热熔胶枪",
                    "万用表", "线缆剪", "压线钳"],
        "suffix": ["20V", "12V", "套装", "单机", "工业版", "家用版", "蓝牙款", "激光款"],
        "brands": ["博世", "得伟", "牧田", "东成", "大有", "史丹利", "世达", "长城精工", "鹰之印", "威力狮"],
        "price_range": (39, 8999),
        "unit": "把",
    },
    "机械": {
        "prefix": ["数控", "全自动", "高精度", "重型", "立式", "卧式", "龙门", "多轴",
                   "伺服", "高速", "精密", "经济型", "大型", "微型", "模块化"],
        "product": ["加工中心", "注塑机", "冲床", "折弯机", "激光切割机", "焊接机器人",
                    "包装机", "印刷机", "贴片机", "点胶机", "绕线机", "研磨机",
                    "铣床", "车床", "磨床"],
        "suffix": ["CNC", "五轴", "全自动", "精密型", "标准型", "重型", "高速型", "四轴"],
        "brands": ["沈阳机床", "大连机床", "海天", "伊之密", "大族激光", "新松", "埃斯顿", "华中数控", "广州数控", "亚威"],
        "price_range": (50000, 2000000),
        "unit": "台",
    },
    "建材": {
        "prefix": ["环保", "轻质", "高强度", "防水", "防火", "保温", "隔音", "抗菌",
                   "自清洁", "快干", "免烧", "预制", "装配式", "纤维增强", "纳米改性"],
        "product": ["石膏板", "水泥", "涂料", "防水卷材", "保温板", "瓷砖", "地板",
                    "玻璃幕墙", "铝单板", "PVC管材", "石塑板", "硅藻泥", "美缝剂",
                    "密封胶", "岩棉板"],
        "suffix": ["A级防火", "E0级环保", "高强度", "超白", "磨砂", "哑光", "亮面", "通体"],
        "brands": ["东方雨虹", "北新建材", "金螳螂", "兔宝宝", "三棵树", "立邦", "多乐士", "科顺", "伟星", "联塑"],
        "price_range": (18, 8999),
        "unit": "㎡",
    },
    "化工产品": {
        "prefix": ["环保型", "高纯度", "食品级", "电子级", "医药级", "纳米级", "水溶性",
                   "油溶性", "低VOC", "无苯", "生物基", "可降解", "耐高温", "抗紫外线", "阻燃"],
        "product": ["环氧树脂", "聚氨酯", "硅胶", "润滑油", "清洗剂", "胶粘剂", "涂料助剂",
                    "塑料粒子", "橡胶", "催化剂", "表面活性剂", "分散剂", "消泡剂",
                    "固化剂", "稀释剂"],
        "suffix": ["工业级", "电子级", "高纯", "快干型", "耐候型", "透明", "黑色", "弹性"],
        "brands": ["万华化学", "巴斯夫", "陶氏", "亨斯迈", "赢创", "科思创", "龙盛", "恒力", "荣盛", "东方盛虹"],
        "price_range": (50, 50000),
        "unit": "kg",
    },
    "能源": {
        "prefix": ["光伏", "储能", "锂电", "钠电", "液流", "固态", "氢能", "风能",
                   "光储一体", "微电网", "虚拟电厂", "V2G", "光热", "地热", "潮汐能"],
        "product": ["太阳能板", "逆变器", "储能柜", "充电桩", "风电叶片", "燃料电池",
                    "锂电池模组", "BMS管理", "光伏支架", "汇流箱", "并网柜", "变压器",
                    "电缆", "隔离开关", "智能电表"],
        "suffix": ["单晶", "多晶", "PERC", "TOPCon", "HJT", "工商业", "户用", "MW级"],
        "brands": ["隆基", "通威", "晶澳", "天合", "宁德时代", "比亚迪", "阳光电源", "华为数字能源", "远景", "中天"],
        "price_range": (500, 500000),
        "unit": "套",
    },
    "日用消费品": {
        "prefix": ["多功能", "便携", "折叠", "环保", "硅胶", "竹木", "不锈钢", "陶瓷",
                   "双层", "保温", "密封", "抗菌", "可降解", "可重复使用", "极简"],
        "product": ["保温杯", "收纳盒", "厨房置物架", "晾衣架", "拖把", "垃圾桶",
                    "保鲜盒", "瑜伽垫", "雨伞", "旅行收纳包", "洗漱包", "化妆镜",
                    "电子秤", "温湿度计", "桌面收纳"],
        "suffix": ["大容量", "迷你", "带盖", "可折叠", "加厚", "透明", "莫兰迪色", "北欧风"],
        "brands": ["名创优品", "网易严选", "京东京造", "小米有品", "妙洁", "茶花", "乐扣", "富光", "苏泊尔", "九阳"],
        "price_range": (9, 999),
        "unit": "个",
    },
    "礼品": {
        "prefix": ["定制", "商务", "节日", "创意", "高档", "伴手", "年会", "开业",
                   "庆典", "纪念", "3D打印", "激光雕刻", "烫金", "UV印刷", "手工"],
        "product": ["笔记本套装", "签字笔", "保温杯礼盒", "U盘", "充电宝", "保温壶",
                    "台历", "挂历", "奖杯", "奖牌", "钥匙扣", "冰箱贴", "书签",
                    "摆件", "茶具礼盒"],
        "suffix": ["定制Logo", "烫金版", "礼盒装", "企业定制", "高档版", "标准版", "迷你款", "尊享版"],
        "brands": ["晨光", "得力", "齐心", "英雄", "派克", "万宝龙", "LAMY", "ZIPPO", "膳魔师", "虎牌"],
        "price_range": (5, 2999),
        "unit": "套",
    },
    "纺织服装": {
        "prefix": ["速干", "防晒", "防风", "防水", "透气", "抗菌", "防静电", "阻燃",
                   "弹力", "纯棉", "冰丝", "摇粒绒", "石墨烯", "远红外", "凉感"],
        "product": ["T恤", "衬衫", "工装裤", "冲锋衣", "羽绒服", "卫衣", "POLO衫",
                    "西裤", "牛仔裤", "安全背心", "厨师服", "护士服", "围裙",
                    "手套", "帽子"],
        "suffix": ["男女同款", "加厚", "薄款", "高弹", "常规版", "修身版", "宽松版", "商务版"],
        "brands": ["波司登", "海澜之家", "安踏", "李宁", "优衣库", "探路者", "骆驼", "森马", "南极人", "恒源祥"],
        "price_range": (29, 2999),
        "unit": "件",
    },
    "鞋类": {
        "prefix": ["轻量", "防滑", "透气", "减震", "钢头", "绝缘", "防静电", "防水",
                   "增高", "矫正", "跑步", "登山", "溯溪", "骑行", "滑雪"],
        "product": ["运动鞋", "皮鞋", "安全鞋", "登山鞋", "凉鞋", "拖鞋", "布鞋",
                    "工装靴", "雨鞋", "护士鞋", "厨师鞋", "篮球鞋", "足球鞋",
                    "帆布鞋", "雪地靴"],
        "suffix": ["网面", "真皮", "气垫", "碳板", "防砸", "商务款", "休闲款", "户外款"],
        "brands": ["安踏", "李宁", "特步", "361°", "回力", "奥康", "红蜻蜓", "意尔康", "骆驼", "探路者"],
        "price_range": (39, 1999),
        "unit": "双",
    },
    "家居装饰品": {
        "prefix": ["北欧", "新中式", "轻奢", "ins风", "复古", "极简", "田园", "工业风",
                   "3D浮雕", "手绘", "烫金", "镂空", "渐变", "拼接", "大理石纹"],
        "product": ["装饰画", "花瓶", "摆件", "挂钟", "地毯", "抱枕", "桌布",
                    "窗帘", "壁纸", "香薰", "烛台", "收纳篮", "镜框", "花盆", "屏风"],
        "suffix": ["大号", "中号", "小号", "套装", "手工", "机制", "烫金款", "丝绒款"],
        "brands": ["宜家", "名创优品", "NOME", "ZARA HOME", "野兽派", "蕉下", "住逻辑", "吱音", "造作", "梵几"],
        "price_range": (9, 2999),
        "unit": "件",
    },
    "办公箱包及休闲用品": {
        "prefix": ["防水", "防盗", "大容量", "超轻", "可折叠", "多功能", "商务", "旅行",
                   "城市", "户外", "极简", "复古", "尼龙", "真皮", "帆布"],
        "product": ["双肩包", "拉杆箱", "公文包", "旅行袋", "洗漱包", "护照夹",
                    "登机箱", "电脑包", "腰包", "斜挎包", "运动包", "野餐垫",
                    "折叠椅", "帐篷", "睡袋"],
        "suffix": ["15.6寸", "14寸", "20寸", "24寸", "加大", "轻薄款", "商务款", "旅行款"],
        "brands": ["新秀丽", "外交官", "小米", "90分", "瑞士军刀", "探路者", "牧高笛", "骆驼", "Osprey", "Tumi"],
        "price_range": (49, 4999),
        "unit": "个",
    },
    "食品": {
        "prefix": ["有机", "冻干", "低糖", "高蛋白", "益生菌", "无添加", "非油炸",
                   "发酵", "FD冻干", "锁鲜", "冷萃", "原切", "慢烘", "蒸制", "酵素"],
        "product": ["坚果礼盒", "冻干咖啡", "燕窝", "蛋白粉", "代餐奶昔", "花茶",
                    "蜂蜜", "阿胶糕", "枸杞", "即食花胶", "巧克力", "曲奇饼干",
                    "牛肉干", "海苔", "黑芝麻丸"],
        "suffix": ["礼盒装", "便携装", "分享装", "独立小包", "无糖款", "原味", "混合口味", "家庭装"],
        "brands": ["三只松鼠", "良品铺子", "百草味", "来伊份", "沃隆", "小仙炖", "官栈", "老金磨方", "恰恰", "蒙牛"],
        "price_range": (19, 1999),
        "unit": "盒",
    },
    "医药及医疗保健": {
        "prefix": ["AI辅助", "便携", "家用", "可穿戴", "远程", "无创", "快速检测",
                   "高灵敏度", "全自动", "无菌", "一次性", "可重复使用", "智能", "蓝牙", "云端"],
        "product": ["血压计", "血糖仪", "血氧仪", "额温枪", "雾化器", "制氧机",
                    "心电监测", "助听器", "颈椎牵引器", "红外理疗灯", "按摩仪",
                    "足浴盆", "体检一体机", "试剂盒", "口罩"],
        "suffix": ["语音版", "蓝牙版", "充电款", "干电池款", "医用级", "家用版", "便携款", "大屏款"],
        "brands": ["迈瑞", "鱼跃", "欧姆龙", "三诺", "乐心", "九安", "康泰", "力康", "飞利浦医疗", "西门子医疗"],
        "price_range": (29, 19999),
        "unit": "台",
    },
    "AI/科技": {
        "prefix": ["AI", "大模型", "深度学习", "计算机视觉", "NLP", "边缘计算", "联邦学习",
                   "数字孪生", "元宇宙", "区块链", "量子", "脑机", "具身智能", "自动驾驶", "RPA"],
        "product": ["AI服务器", "GPU集群", "智能摄像头", "边缘计算盒子", "AI开发平台",
                    "数字人", "智能客服", "OCR识别", "语音合成", "机器翻译",
                    "人脸识别终端", "行为分析", "知识图谱", "向量数据库", "模型训练平台"],
        "suffix": ["企业版", "SaaS版", "私有部署", "API版", "一体机", "云端版", "旗舰版", "标准版"],
        "brands": ["华为", "百度", "阿里云", "腾讯云", "商汤", "旷视", "科大讯飞", "寒武纪", "壁仞", "地平线"],
        "price_range": (9999, 999999),
        "unit": "套",
    },
    "综合服务": {
        "prefix": ["一站式", "跨境", "数字化", "定制", "全流程", "快速", "专业", "国际",
                   "绿色", "智能", "远程", "O2O", "供应链", "品牌", "出海"],
        "product": ["展位搭建", "物流运输", "翻译服务", "展品保险", "签证服务",
                    "市场调研", "品牌设计", "短视频制作", "直播代运营", "海外仓",
                    "法律咨询", "报关清关", "展具租赁", "礼仪接待", "数字营销"],
        "suffix": ["基础包", "尊享包", "全程包", "按次", "包月", "定制方案", "标准版", "VIP版"],
        "brands": ["笔克", "汉诺威", "中展", "外运", "中外运", "嘉里", "中国电信国际", "中译", "蓝色光标", "分众"],
        "price_range": (500, 200000),
        "unit": "次",
    },
}

print(f"📦 生成10000个展品...")

products = []
count = 0
batch_size = 500

for cat_name, cfg in CATEGORIES.items():
    # 每个类别生成约 555 个（18×555≈10000）
    target = 556 if cat_name != "综合服务" else 548

    for i in range(target):
        prefix = random.choice(cfg["prefix"])
        prod = random.choice(cfg["product"])
        suffix = random.choice(cfg["suffix"])
        brand = random.choice(cfg["brands"])
        lo, hi = cfg["price_range"]
        price = round(random.uniform(lo, hi), 2)

        name = f"{brand} {prefix}{prod} {suffix}"
        desc = f"{brand}出品，{prefix}{prod}，适用于各类商业和工业场景"

        # 随机分配展商和展会
        exh = random.choice(exhibitors)
        ex = random.choice(exhibitions)

        # 分配展位(展商自己占用的展位)
        own_booths = [b for b in booths if b.exhibitor_id == exh.id and b.status == 'occupied']
        if own_booths:
            booth = random.choice(own_booths)
        else:
            ex_booths = [b for b in booths if b.exhibition_id == ex.id]
            booth = random.choice(ex_booths) if ex_booths else booths[0]

        # V2.4: 展品生成后批量分配微展位

        specs = json.dumps({
            "品牌": brand,
            "型号": f"{prefix[:2]}-{random.randint(100,999)}",
            "产地": random.choice(["深圳","东莞","苏州","宁波","青岛","佛山","温州","泉州"]),
        }, ensure_ascii=False)

        p = Product(
            booth_id=booth.id,
            micro_booth_id=None,  # 微展位商品由种子数据精选，不自动挂
            exhibition_id=ex.id,
            exhibitor_id=exh.id,
            exhibitor_name=exh.company or exh.nickname or exh.username,
            name=name,
            description=desc,
            category=cat_name,
            price=price,
            unit=cfg["unit"],
            specs=specs,
            images=json.dumps([f"https://picsum.photos/seed/{name.replace(' ','')[:20]}/{random.randint(350,450)}/{random.randint(250,350)}"]),
            stock=random.randint(10, 9999),
            model_number=f"{random.choice(['PRO','MAX','STD','ECO','ELITE'])}-{random.randint(100,999)}",
            material=random.choice(['ABS塑料','不锈钢','铝合金','碳纤维','硅胶','陶瓷','钢化玻璃','纯铜']),
            min_order=random.choice([10,50,100,500,1000]),
            supply_ability=f"{random.choice([1000,5000,10000,50000,100000])}{random.choice(['件','套','个','台'])}/月",
            delivery_time=f"{random.choice([7,10,15,20,30,45])}天",
            certifications=random.choice(['CE','FCC,CE','CE,ROHS','FCC,CE,ROHS','ISO9001,CE','CCC,CE','UL,CE,FCC']),
            target_market=random.choice(['欧美','东南亚','中东','非洲','南美','全球','日韩','一带一路']),
            status="published",
        )
        products.append(p)
        count += 1

        if len(products) >= batch_size:
            db.add_all(products)
            db.flush()
            print(f"  ⏳ {count}/10000 ...")
            products = []

# 最后一批
if products:
    db.add_all(products)
    db.flush()

db.commit()
# V2.8: 批量分配展品到微展位
from app.models.micro_booth import MicroBooth
from app.models.membership import TIER_PRODUCT_LIMITS
all_mbs = db.query(MicroBooth).all()
mb_assigned = 0
for mb in all_mbs:
    limit = TIER_PRODUCT_LIMITS.get(mb.membership_tier, 3)
    if limit == 0: limit = 50
    already = db.query(func.count(Product.id)).filter(Product.micro_booth_id == mb.id).scalar() or 0
    remaining = max(0, limit - already)
    if remaining > 0:
        prods = db.query(Product).filter(Product.exhibitor_id == mb.exhibitor_id, Product.micro_booth_id == None).order_by(func.random()).limit(remaining).all()
        for p in prods: p.micro_booth_id = mb.id
        mb_assigned += len(prods)
db.commit()
print(f"✅ 完成！共生成 {count} 个展品 (微展位分配 {mb_assigned} 件)")
db.close()
