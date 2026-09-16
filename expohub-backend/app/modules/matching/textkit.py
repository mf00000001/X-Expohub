"""
匹配工作流 · 文本工具箱 (textkit)

为「智能推荐工作流」的召回/打分阶段提供底层文本能力：

1. ``tokenize``            中文分词（jieba 优先；缺库自动降级为二元组，功能不缺失）
2. ``normalize_category``  非标准品类 → 18 个标准展区品类（修复跨体系品类断链）
3. ``synonyms_of``         行业同义词展开（数控 ↔ CNC ↔ 机床……），提升召回覆盖
4. ``IdfModel``            语料级 IDF 词权重（稀有词权重高、泛词权重低）
5. ``keyword_coverage``    带同义词回退与 IDF 加权的关键词覆盖率（0~1）

设计约束：纯本地、零云依赖、无新增数据库表；jieba 缺失时全功能可用。
"""
from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache
from typing import Iterable, Optional

from app.models.category import CATEGORY_PARENT_GROUPS, EXHIBITION_CATEGORIES

# ============================================================
# 1) 分词
# ============================================================

try:  # jieba 为可选依赖：可用则精度更高，不可用自动退化
    import jieba

    _JIEBA_OK = True
except Exception:  # pragma: no cover - 环境缺库路径
    jieba = None  # type: ignore[assignment]
    _JIEBA_OK = False

# 领域词表：避免 jieba 把行业词切碎（如「数据线」→「数据/线」）
DOMAIN_WORDS = [
    "数控机床", "加工中心", "数控", "五轴", "龙门加工中心", "激光切割",
    "焊接机器人", "工业机器人", "自动化产线", "生产线", "包装机", "灌装机",
    "数据线", "快充", "移动电源", "电源适配器", "扫地机器人", "清洁机器人",
    "会议平板", "智能门锁", "指纹锁", "咖啡机", "电饭煲", "电磁炉",
    "充电桩", "后视镜", "行车记录仪", "车载", "新能源车", "轮胎",
    "植物生长灯", "生长灯", "LED", "智慧路灯", "球泡灯", "太阳能板",
    "光伏组件", "储能柜", "储能系统", "风机", "海上风电",
    "铝单板", "幕墙", "镀锌钢管", "岩棉保温板", "保温板", "水性涂料",
    "环氧树脂", "螺丝刀", "棘轮扳手", "卫浴挂件", "陶瓷餐具",
    "医学影像", "影像中心", "医疗器械", "CT", "MRI",
    "红酒", "葡萄酒", "AI服务器", "GPU集群", "大模型", "计算机视觉", "无人机",
]

if _JIEBA_OK:
    for _w in DOMAIN_WORDS:
        jieba.add_word(_w)

# 停用词：意图词/量词/通用词，对匹配无区分度
STOPWORDS = {
    # 意图类
    "采购", "求购", "招标", "询价", "竞价", "需要", "需求", "要求", "提供", "报价",
    "包含", "包括", "支持", "适用", "用于", "应用", "以及", "关于", "相关", "进行",
    "合作", "定制", "生产", "制造", "销售", "售后", "维保", "质保", "交期", "交货",
    "出口", "进口", "目标", "场景", "用途", "功能", "配置", "参数", "规格", "型号",
    "项目", "方案", "服务", "系统", "产品", "厂家", "工厂", "公司", "企业", "品牌",
    "市场", "批量", "大量", "全年", "长期", "以上", "以下", "以内", "左右",
    # 量词/单位（含英文单位词与 jieba 合并量词）
    "台", "件", "套", "只", "条", "个", "批", "吨", "箱", "张", "把", "支", "块",
    "根", "份", "组", "部", "辆", "座", "栋", "家", "款", "项", "平方米", "平米",
    "万套", "万条", "万件", "万台", "万个", "万只", "万张", "万把", "万支", "万吨",
    "万箱", "万份", "万块", "万根", "千台", "千套", "公里", "千米", "立方",
}

_LATIN_RE = re.compile(r"[a-z0-9][a-z0-9+./#\-]*")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
_TOKEN_SCAN_RE = re.compile(r"[a-z0-9][a-z0-9+./#\-]*|[\u4e00-\u9fff]+")


def _clean_latin(tok: str) -> str:
    return tok.strip(".+-/#")


def tokenize(text: Optional[str]) -> list[str]:
    """分词：中文词 + 拉丁词（小写），过滤停用词/纯数字；保持原文顺序。

    jieba 可用 → 词级切分；否则 → 中文二元组（bigram）兜底。
    保持顺序是为让调用方识别"最后一个词"（中文商品名的中心语通常在后）。
    """
    if not text:
        return []
    t = str(text).lower()
    tokens: list[str] = []

    for m in _TOKEN_SCAN_RE.finditer(t):
        seg = m.group(0)
        if seg[0].isascii():  # 拉丁/数字段
            tok = _clean_latin(seg)
            if len(tok) >= 2 and tok not in STOPWORDS and not tok.isdigit():
                tokens.append(tok)
            continue
        # 中文段
        if _JIEBA_OK:
            for w in jieba.lcut(seg):
                w = w.strip()
                if len(w) >= 2 and w not in STOPWORDS:
                    tokens.append(w)
        else:  # pragma: no cover - 缺 jieba 的降级路径
            if len(seg) < 2:
                continue
            for i in range(len(seg) - 1):
                bg = seg[i : i + 2]
                if bg not in STOPWORDS:
                    tokens.append(bg)
    return tokens


# 规格词中的保留词：含数字但业务含义强（5G/4K 等），保留参与匹配
DIGIT_KEEP = {"5g", "4k", "8k", "3d"}


def is_spec_token(tok: str) -> bool:
    """规格/数量类 token（含数字，如 200mw、550w、182/210、ip65）——查询侧过滤。"""
    return any(c.isdigit() for c in tok) and tok not in DIGIT_KEEP


def build_query(parts: Iterable[tuple[Optional[str], int]]) -> dict[str, int]:
    """构造加权查询词袋：``[(文本, 字段权重), ...]`` → ``{词: 权重}``（权重封顶 4）。

    过滤规格/数量词（如 200MW、550W、45天），它们常出现在需求但不出现在展品名，
    留在分母会稀释可匹配的核心词覆盖率。
    """
    q: Counter[str] = Counter()
    for text, weight in parts:
        for tok in tokenize(text):
            if is_spec_token(tok):
                continue
            q[tok] += weight
    return {t: min(c, 4) for t, c in q.items()}


def build_title_query(title: Optional[str], weight: int = 3) -> dict[str, int]:
    """标题查询词袋：末词（中文中心语，如「…LED智慧路灯」的"智慧路灯"）加权。

    中文商品名中心语后置，末词是"到底要买什么"的最强信号。
    """
    toks = [t for t in (tokenize(title) or []) if not is_spec_token(t)]
    q: Counter[str] = Counter()
    for i, t in enumerate(toks):
        q[t] += weight + (2 if i == len(toks) - 1 else 0)
    return {t: min(c, 6) for t, c in q.items()}


# ============================================================
# 2) 品类归一化
# ============================================================

# 非标准品类 → 标准展区品类（历史/补录数据常见跨体系写法）
CATEGORY_ALIASES: dict[str, str] = {
    # 电子及家电
    "家用电器": "电子及家电", "小家电": "电子及家电", "消费电子": "电子及家电",
    "智能家居": "电子及家电", "智能手机": "电子及家电", "手机": "电子及家电",
    "笔记本电脑": "电子及家电", "电脑": "电子及家电", "空调": "电子及家电",
    "电子产品": "电子及家电", "家电": "电子及家电", "办公设备": "电子及家电",
    "企业存储": "电子及家电", "音视频": "电子及家电",
    # 照明
    "灯具": "照明", "光源": "照明",
    # 机械
    "工业自动化": "机械", "自动化": "机械", "机床": "机械", "机械装备": "机械",
    "工业机器人": "机械", "机器人": "机械", "重型机械": "机械",
    # 建材
    "建筑材料": "建材", "幕墙": "建材", "保温材料": "建材",
    # 化工产品
    "化工": "化工产品", "精细化工": "化工产品", "涂料": "化工产品",
    # 能源
    "新能源": "能源", "光伏": "能源", "储能": "能源", "风电": "能源", "电力": "能源",
    # 食品 / 医药
    "食品饮料": "食品", "饮料": "食品", "酒类": "食品",
    "医疗器械": "医药及医疗保健", "医疗健康": "医药及医疗保健", "医药": "医药及医疗保健",
    "医疗设备": "医药及医疗保健", "影像设备": "医药及医疗保健", "生物医药": "医药及医疗保健",
    # AI/科技
    "AI基础设施": "AI/科技", "人工智能": "AI/科技", "大模型": "AI/科技", "AI": "AI/科技",
    "信息技术": "AI/科技", "软件": "AI/科技", "无人机": "AI/科技", "无人机/巡检": "AI/科技",
    "数字孪生": "AI/科技", "工业物联网": "AI/科技", "教育机器人": "AI/科技",
    # 车辆及配件
    "汽车": "车辆及配件", "汽车配件": "车辆及配件", "新能源车": "车辆及配件",
    "电动汽车": "车辆及配件", "整车": "车辆及配件",
    # 五金工具
    "五金": "五金工具", "工具": "五金工具",
    # 日用消费品
    "日用": "日用消费品", "消费品": "日用消费品", "日用品": "日用消费品",
    # 纺织服装 / 鞋类 / 家居 / 箱包 / 综合服务
    "纺织": "纺织服装", "服装": "纺织服装", "面料": "纺织服装",
    "鞋": "鞋类", "家居": "家居装饰品", "装饰": "家居装饰品",
    "箱包": "办公箱包及休闲用品", "办公": "办公箱包及休闲用品",
    "综合服务": "综合服务",
    # 扩展数据集常见品类（seed_demo_extra 等）
    "物流与仓储": "机械", "物流": "机械", "仓储": "机械",
    "新材料": "化工产品", "材料": "化工产品",
    "软件与SaaS": "AI/科技", "软件与saas": "AI/科技",
    "视听设备": "电子及家电", "智能硬件": "电子及家电", "通信设备": "电子及家电",
    "包装印刷": "办公箱包及休闲用品", "包装": "办公箱包及休闲用品",
    "仪器仪表": "机械",
    "会展服务": "综合服务",
}

_SUFFIXES = ("类", "行业", "领域")


def normalize_category(cat: Optional[str]) -> str:
    """把任意品类字符串映射到标准展区品类；无法识别时原样返回（供模糊规则兜底）。"""
    if not cat:
        return ""
    c = str(cat).strip()
    if not c:
        return ""
    if c in EXHIBITION_CATEGORIES:
        return c
    if c in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[c]
    for suf in _SUFFIXES:  # 「机械类」→「机械」
        if c.endswith(suf) and c[: -len(suf)] in EXHIBITION_CATEGORIES:
            return c[: -len(suf)]
    for key, val in CATEGORY_ALIASES.items():  # 包含匹配（如「工业自动化产线」）
        if key in c:
            return val
    return c


def category_affinity(cat_a: Optional[str], cat_b: Optional[str]) -> Optional[float]:
    """品类相似度：精确 1.0 / 同父组 0.6 / 无法识别 0.0 / 数据缺失 None（信号不可用）。"""
    a, b = normalize_category(cat_a), normalize_category(cat_b)
    if not a or not b:
        return None
    if a == b:
        return 1.0
    pa, pb = CATEGORY_PARENT_GROUPS.get(a), CATEGORY_PARENT_GROUPS.get(b)
    if pa is not None and pa == pb:
        return 0.6
    return 0.0


# ============================================================
# 3) 行业同义词
# ============================================================

# 真同义词族（双向，命中强度 0.4）：组内词视为"同一件东西的不同叫法/粒度"
SYNONYM_GROUPS: list[set[str]] = [
    # —— 机械 / 工业 ——
    {"数控", "cnc"},
    {"机床", "加工中心", "车床", "铣床", "磨床", "钻床"},
    {"机器人", "机械臂", "机械手", "工业机器人", "协作机器人"},
    {"自动化", "产线", "流水线", "自动化产线"},
    {"plc", "scada", "mes", "工控"},
    {"注塑机", "挤出机", "成型机", "吹塑机"},
    {"包装机", "灌装机", "封口机", "贴标机", "包装线", "包装设备"},
    {"激光", "激光器", "激光切割", "激光设备"},
    {"焊接", "焊机", "焊接设备"},
    {"减速机", "减速器", "关节模组"},
    {"agv", "仓储机器人", "搬运机器人"},
    # —— 电子 / 家电（共下位词请在 HYPERNYM_MAP 中单向表达）——
    {"数据线", "充电线", "type-c", "usb", "连接器", "连接线"},
    {"充电器", "电源适配器"},
    {"移动电源", "充电宝"},
    {"扫地机器人", "清洁机器人", "洗地机"},
    {"显示屏", "显示器", "屏幕", "智慧屏", "会议平板", "led屏"},
    {"投影仪", "投影机", "投屏"},
    {"智能门锁", "门锁", "指纹锁", "密码锁", "电子锁"},
    {"耳机", "耳麦"},
    {"音箱", "音响", "扬声器"},
    {"服务器", "gpu", "算力", "集群", "数据中心", "ai服务器"},
    {"摄像头", "摄像机", "云台相机", "监控"},
    {"平板电脑", "平板"},
    {"智能手机", "手机", "移动终端"},
    # —— 照明 ——
    {"灯具", "照明", "灯光", "光源", "led"},
    {"生长灯", "植物生长灯", "补光灯", "植物灯"},
    # —— 能源 ——
    {"光伏", "太阳能", "光伏组件", "太阳能板", "光伏板"},
    {"储能", "储能柜", "储能系统", "储能电站"},
    {"电池", "电芯"},
    {"风电", "风力发电", "海上风电", "风机", "叶片"},
    {"逆变器", "变流器"},
    # —— 车辆 ——
    {"轮胎", "车胎"},
    {"充电桩", "充电站", "超充", "快充桩"},
    {"电动汽车", "新能源车", "电动车", "整车"},
    {"后视镜", "倒车镜"},
    {"行车记录仪", "记录仪"},
    # —— 五金 / 建材 ——
    {"五金", "五金工具", "工具"},
    {"卫浴", "卫浴挂件", "花洒", "水龙头", "毛巾架", "置物架"},
    {"铝单板", "铝板", "铝材", "幕墙"},
    {"钢管", "镀锌管", "管材", "管道", "无缝管"},
    {"岩棉", "保温板", "保温材料", "防火板", "保温"},
    {"陶瓷", "餐具", "陶瓷餐具"},
    {"瓷砖", "地砖", "墙砖"},
    # —— 化工 / 材料 ——
    {"涂料", "油漆", "水性漆", "乳胶漆"},
    {"环氧树脂", "树脂"},
    {"胶粘剂", "胶水", "粘合剂"},
    {"塑料", "pp", "pe", "pvc", "abs"},
    {"铜材", "再生铜", "硅片", "靶材", "新材料"},
    # —— 医药 ——
    {"医学影像", "影像设备", "影像中心", "影像系统"},
    {"ct", "mri", "x光"},
    {"医疗器械", "医疗设备", "诊断设备"},
    {"监护仪", "健康检测一体机"},
    # —— 食品 ——
    {"红酒", "葡萄酒", "红葡萄酒"},
    {"白酒", "烈酒"},
    {"饮料", "饮品", "果汁"},
    {"咖啡", "咖啡豆"},
    # —— 纺织 / 鞋 / 礼品 / 日用 ——
    {"面料", "布料", "棉布", "纱线", "纺织"},
    {"成衣", "服装", "t恤", "衬衫", "女装", "男装"},
    {"运动鞋", "皮鞋", "靴子", "鞋"},
    {"礼品", "赠品", "纪念品"},
    {"玩具", "模型", "积木"},
    {"家居用品", "家居", "收纳", "日用品"},
    # —— 科技 / 服务 ——
    {"人工智能", "ai", "大模型", "aigc"},
    {"机器学习", "深度学习", "计算机视觉", "视觉算法", "算法", "训练", "推理"},
    {"软件", "saas", "信息化", "数字化", "系统集成"},
    {"翻译", "同传", "口译"},
    {"冷链", "温控", "冷藏"},
]

# 上位词 → 下位词（单向，命中强度 0.5）：查询"家电"可命中"空调"，反之不成立。
# 用于表达"共下位词"关系，避免把 空调/冰箱 这类并列词误当同义词。
HYPERNYM_MAP: dict[str, set[str]] = {
    "家电": {"空调", "冰箱", "洗衣机", "电视", "热水器", "电饭煲", "电磁炉", "榨汁机",
             "电热水壶", "微波炉", "小家电", "厨房电器", "扫地机器人", "吸尘器"},
    "小家电": {"电饭煲", "电磁炉", "榨汁机", "电热水壶", "咖啡机", "微波炉", "饮水机"},
    "灯具": {"路灯", "球泡灯", "灯管", "吊灯", "台灯", "地埋灯", "吸顶灯", "射灯", "应急灯", "灯带"},
    "工具": {"螺丝刀", "电钻", "扳手", "量具", "刃具", "手动工具", "电动工具", "棘轮扳手"},
    "五金": {"螺丝刀", "电钻", "扳手", "卫浴挂件", "水龙头", "花洒", "铰链", "锁具"},
    "零部件": {"刹车", "轴承", "滤清器", "齿轮", "传动轴"},
    "汽配": {"刹车", "轴承", "滤清器", "保险杠", "车灯"},
    "医疗设备": {"监护仪", "超声", "ct", "mri", "手术器械", "检测仪"},
    "酒类": {"红酒", "白酒", "啤酒", "葡萄酒", "米酒"},
    "食品": {"零食", "罐头", "饮料", "粮油", "大米", "食用油", "面粉", "糖果", "咖啡豆"},
    "服装": {"t恤", "衬衫", "女装", "男装", "连衣裙", "裤装", "外套"},
    "鞋": {"运动鞋", "皮鞋", "靴子", "凉鞋"},
    "仪器仪表": {"传感器", "压力传感器", "流量传感器", "仪表", "变送器"},
    "传感器": {"压力传感器", "流量传感器", "温湿度传感器"},
    "包装": {"包装机", "包装箱", "包装盒", "包装材料", "灌装机"},
    "物流": {"agv", "仓储", "分拣", "输送线", "立体库"},
    "视听设备": {"投影仪", "显示屏", "led屏", "音响", "全息投影"},
}

_SYNONYM_MAP: dict[str, set[str]] = {}
for _g in SYNONYM_GROUPS:
    for _t in _g:
        _SYNONYM_MAP.setdefault(_t, set()).update(_g - {_t})

# 命中强度：精确 1.0 / 复合词拆分 0.7 / 上位词→下位词 0.5 / 同义词族 0.4
SYNONYM_HIT_WEIGHT = 0.4
HYPERNYM_HIT_WEIGHT = 0.5
COMPOUND_HIT_WEIGHT = 0.7

# 复合词分解索引：查询词内含的已知术语（如「汽车轮胎」⊃「轮胎」、「智慧路灯」⊃「路灯」）
_TERM_INDEX: tuple[str, ...] = tuple(sorted(
    {t for g in SYNONYM_GROUPS for t in g}
    | set(HYPERNYM_MAP)
    | {m for s in HYPERNYM_MAP.values() for m in s},
    key=len, reverse=True,
))


@lru_cache(maxsize=8192)
def _compound_siblings(tok: str) -> tuple[str, ...]:
    """拆出查询词中蕴含的已知术语（长词优先，最多 6 个）。"""
    if tok.isascii() or len(tok) < 3:
        return ()
    return tuple(s for s in _TERM_INDEX if len(s) >= 2 and s != tok and s in tok)[:6]


def expand_recall_tokens(tokens: Iterable[str]) -> dict[str, float]:
    """召回用词展开：``{词: 权重系数}``。

    原词 1.0 / 复合词拆分 0.7 / 上位词 0.6 / 同义词族 0.6。
    用于倒排召回，保证「同义词/复合词才命中的文档」也进入候选集（与打分层一致）。
    """
    out: dict[str, float] = {}

    def put(t: str, f: float) -> None:
        out[t] = max(out.get(t, 0.0), f)

    for t in tokens:
        put(t, 1.0)
        for c in _compound_siblings(t):
            put(c, 0.7)
        for m in HYPERNYM_MAP.get(t, ()):
            put(m, 0.6)
        for s in _SYNONYM_MAP.get(t, ()):
            put(s, 0.6)
    return out


def synonyms_of(token: str) -> set[str]:
    """返回词的行业同义词（不含自身）。"""
    return _SYNONYM_MAP.get(token, set())


# ============================================================
# 4) IDF 词权重 + 命中判定
# ============================================================

class IdfModel:
    """语料级 IDF 词权重。

    - 拉丁/数字词：按 token 频次统计
    - 中文词：按**原文子串命中**统计（df 与匹配方式一致，避免分词差异导致
      稀有词权重虚高，例如「新能源车」在大量「新能源车衣」标题中被切碎而 df 偏低）
    """

    def __init__(self, doc_tokens: Iterable[list[str]],
                 doc_texts: Optional[Iterable[str]] = None):
        df: Counter[str] = Counter()
        n = 0
        for toks in doc_tokens:
            n += 1
            df.update(set(toks))
        self.n = n
        self._df = df
        self._texts: Optional[list[str]] = list(doc_texts) if doc_texts is not None else None
        self._text_df: dict[str, int] = {}

    @staticmethod
    def _score(n: int, df: int) -> float:
        return math.log((n + 1) / (df + 1)) + 1.0

    def _text_doc_freq(self, token: str) -> int:
        cached = self._text_df.get(token)
        if cached is not None:
            return cached
        df = 0
        for t in self._texts or ():
            if token in t:
                df += 1
        self._text_df[token] = df
        return df

    def idf(self, token: str) -> float:
        if self._texts is not None and not token.isascii() and len(token) >= 2:
            return self._score(self.n, self._text_doc_freq(token))
        return self._score(self.n, self._df.get(token, 0))


def token_hit(query_token: str, doc_text: str, doc_tokens: set[str]) -> float:
    """查询词在文档中的命中强度。

    精确 1.0 / 复合词拆分 0.7 / 上位词→下位 0.5 / 同义词族 0.4 / 未命中 0。

    拉丁词按 token 精确匹配（避免 'ce' 命中 'oceanstor' 的子串误判）；
    中文词允许原文子串匹配（'加工中心' ⊂ '龙门加工中心'）。
    """
    if query_token in doc_tokens:
        return 1.0
    if not query_token.isascii() and query_token in doc_text:
        return 1.0
    for sub in _compound_siblings(query_token):  # 复合词分解：'汽车轮胎' → '轮胎'
        if sub in doc_tokens:
            return COMPOUND_HIT_WEIGHT
        if not sub.isascii() and sub in doc_text:
            return COMPOUND_HIT_WEIGHT
    for member in HYPERNYM_MAP.get(query_token, ()):  # 上位词查询 → 下位词文档（单向）
        if member in doc_tokens:
            return HYPERNYM_HIT_WEIGHT
        if not member.isascii() and member in doc_text:
            return HYPERNYM_HIT_WEIGHT
    for sib in _SYNONYM_MAP.get(query_token, ()):  # 同义词族弱命中
        if sib in doc_tokens:
            return SYNONYM_HIT_WEIGHT
        if not sib.isascii() and sib in doc_text:
            return SYNONYM_HIT_WEIGHT
    return 0.0


def keyword_coverage(
    query: dict[str, int],
    doc_text: str,
    doc_tokens: set[str],
    idf: IdfModel,
    top_k: int = 3,
) -> tuple[float, list[str]]:
    """IDF 加权关键词覆盖率（0~1）+ 命中词列表（按 IDF 降序，最多 top_k 个）。"""
    if not query:
        return 0.0, []
    num = den = 0.0
    hits: list[tuple[float, str]] = []
    for tok, weight in query.items():
        idw = idf.idf(tok) * weight
        den += idw
        h = token_hit(tok, doc_text, doc_tokens)
        if h > 0:
            num += idw * h
            hits.append((idf.idf(tok), tok))
    if den <= 0:
        return 0.0, []
    hits.sort(key=lambda x: (-x[0], x[1]))
    return min(1.0, num / den), [t for _, t in hits[:top_k]]


def keyword_coverage_tiered(
    core_query: dict[str, int],
    extra_query: dict[str, int],
    doc_text: str,
    doc_tokens: set[str],
    idf: IdfModel,
    core_weight: float = 0.7,
    top_k: int = 3,
) -> tuple[float, list[str]]:
    """两层关键词覆盖：核心词（标题等）权重 ``core_weight``，全量（含描述）其余。

    避免长描述中大量不可命中的细节词（认证/电压/市场……）稀释核心匹配度。
    """
    core_cov, core_hits = keyword_coverage(core_query, doc_text, doc_tokens, idf)
    merged = dict(core_query)
    for t, w in extra_query.items():
        merged[t] = max(merged.get(t, 0), w)
    full_cov, full_hits = keyword_coverage(merged, doc_text, doc_tokens, idf)
    hits = core_hits if len(core_hits) >= top_k else list(dict.fromkeys(core_hits + full_hits))[:top_k]
    return min(1.0, core_weight * core_cov + (1.0 - core_weight) * full_cov), hits
