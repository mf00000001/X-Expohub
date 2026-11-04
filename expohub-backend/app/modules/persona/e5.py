"""
E5 交付可行性：三态核查清单（**不打分、不加权**）

## 为什么这一项长得跟 E1/E4 完全不一样

E1/E4 是"从公开数据算出结论"，E5 是"**把该问的问题问对，然后把答案拼成 go/no-go**"。

层高、地面承重、货运通道尺寸、供电容量、消防与吊点规定——这几项在 94 个展会里
**一个数都拿不到**。主办方不公开，会场方要你打电话问。所以 E5 的正确实现不是
"再抓一批数据"，是给用户一张**问对问题**的清单。

维度清单原话：

> 这一项最不该有权重：它是约束不是偏好。一旦加权，就会出现"其他项都不错所以
> 消防不过也能去"这种荒谬结论。任一不满足 → 直接输出额外成本或不可行。

所以 `evaluate()` 里没有求和、没有加权、没有分数。只有：任一条 `short` 且后果是
`block` → 整单 `blocked`。

## 四态结论

| verdict | 含义 | 用户该做什么 |
|---|---|---|
| `blocked` | 至少一条物理上做不到 | 换展，或换展具方案 |
| `incomplete` | 还有该问的没问到 | 按清单去问主办方，别猜 |
| `pass_with_cost` | 都能做，但有钱要花 | 把额外成本计入 E3 |
| `pass` | 八条都满足 | 正常推进 |

**优先级是 blocked > incomplete > pass_with_cost > pass。**
`incomplete` 排在 `pass_with_cost` 前面，是因为"不知道"不等于"没问题"——
7 条 ok + 1 条未知，不能说"通过但有成本"，只能说"还没问完"。
这是个**请求补信息**的状态，不是否决，所以不违反"假否决比漏判更贵"。

## 三态输入

每条只收三种值：

- `ok`     —— 满足（问过了，够用）
- `short`  —— 不满足（问过了，不够）。后果由该条自带 `short_consequence` 决定
- `unknown`（默认）—— 没问 / 没问到

**不给"大概差不多"这种中间态。** 物理约束没有"差不多"：4 米限高装不下 4.5 米的展具，
差 50 公分就是装不下。允许模糊值只会让用户在真该放弃的时候凑合过去。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

VALID_STATES = ("ok", "short", "unknown", "na")


@dataclass(frozen=True)
class E5Item:
    """
    一条核查项。

    `ask` 是这一项的**全部价值所在**：把"你要注意层高"翻译成
    "问主办方：标准展位限高多少？特装限高多少？展馆净高多少？"
    ——第一次参展的人根本不知道要问这个。

    `na_allowed` 标记这一条能否填"不适用"。**只有特装专属的条目允许**：
    标准展位是主办方统一搭建的，跟展商问层高、承重、吊点毫无意义。
    但不允许把"进场时间窗 / 供电 / 消防"标 na——这三条任何参展方都躲不开，
    开放 na 等于给了一条"全标不适用就拿到通过"的捷径。
    """

    id: str
    name: str
    kind: str                      # numeric（可量）/ policy（规定）
    ask: str                       # 该向主办方问什么（原话级别，可直接照念）
    why: str                       # 不满足会怎样
    short_consequence: str         # block（做不到）/ cost（能做到但要加钱）
    unit: str = ""
    requirement_label: str = ""    # 用户侧：我的展具/设备需要多少
    capability_label: str = ""     # 场地侧：展馆能给多少
    typical: str = ""              # 常见值，帮用户判断对方报的数是否离谱
    fallback: str = ""             # 不满足时的替代方案（short_consequence=cost 时必填）
    na_allowed: bool = False       # 能否填"不适用"（仅特装专属项）


# 顺序按"最容易把人拦下来的排前面"——先问层高承重，因为这两条一票否决且不可变通
E5_CHECKLIST: tuple[E5Item, ...] = (
    E5Item(
        id="height",
        name="展馆限高 / 特装高度",
        kind="numeric",
        unit="米",
        requirement_label="我的展具或设备最高处",
        capability_label="特装允许的最大高度",
        ask="问主办方：标准展位限高多少？光地特装限高多少？展馆净高（到屋顶桁架）多少？"
            "有吊顶或消防喷淋的地方会不会再压低？",
        why="超过特装限高必须降高或改结构；超过净高直接搭不进去。"
            "这一条没有变通空间，是纯物理约束。",
        short_consequence="block",
        na_allowed=True,
        typical="多数展馆净高 8~12 米，但特装限高常只有 4~6 米（受喷淋和消防分区限制）。"
                "别拿净高当限高，这两个数差一倍。",
    ),
    E5Item(
        id="floor_load",
        name="地面承重",
        kind="numeric",
        unit="kg/㎡",
        requirement_label="我的设备总重 ÷ 占地",
        capability_label="展馆地面允许承重",
        ask="问主办方：一层展厅地面承重多少 kg/㎡？二层呢？"
            "重型设备是否需要铺设钢板分散荷载、是否要报审？",
        why="超载会压坏地坪，展馆有权当场叫停。重型机械、大型储罐、注塑机类展品"
            "几乎一定会撞到这一条。",
        short_consequence="block",
        na_allowed=True,
        typical="普通展厅 500~1000 kg/㎡，二层通常只有 300~500。"
                "一台 5 吨的设备放在 2㎡ 底座上就是 2500 kg/㎡，直接超一倍。",
    ),
    E5Item(
        id="freight",
        name="货运通道 / 货梯尺寸",
        kind="numeric",
        unit="米",
        requirement_label="我的展具或设备最大外形尺寸",
        capability_label="货运门 / 货梯的最小通过尺寸",
        ask="问主办方：货运通道门宽高多少？货梯门宽高和轿厢尺寸？"
            "有单件重量上限吗？展馆限高多少（车顶到地面）？",
        why="设备进不去就只能拆件运输、现场组装，工期和成本都会翻。"
            "大件展品最常见的翻车点不是展位，是进门那一下。",
        short_consequence="block",
        na_allowed=True,
        typical="货梯门宽常见 1.5~2 米，能进标准托盘却进不了整机木箱。"
                "问的时候一定要问「最小通过尺寸」，不是「最大载重」。",
    ),
    E5Item(
        id="setup_window",
        name="进场搭建时间窗",
        kind="numeric",
        unit="小时",
        requirement_label="我的搭建需要工时",
        capability_label="官方给的布展时长",
        ask="问主办方：布展从几号几点到几号几点？每天允许施工的时间段？"
            "加班布展要不要申请、怎么收费？撤展窗口多长？",
        why="工时不够只能加人加班，加班费按小时计且常常要提前审批。"
            "特装展位这一项几乎必然要吃钱。",
        short_consequence="cost",
        fallback="加派搭建人手、申请加班时段（通常按小时加收），或改预制化结构缩短现场工时。",
        typical="标准展位一般给 1~2 天，特装 2~3 天。听起来够，实际扣掉进场排队、"
                "卸货等待、消防验收，有效工时往往只剩六成。",
    ),
    E5Item(
        id="power",
        name="供电容量",
        kind="numeric",
        unit="kW",
        requirement_label="我的设备总功率",
        capability_label="展位可申请的最大供电",
        ask="问主办方：标准展位配多少电（通常是 220V/500W 或 1kW）？"
            "光地可申请到多少 kW？380V 三相电能不能接？超容量怎么收费？",
        why="功率不够设备跑不起来，或者一开机就跳闸。大功率设备还要单独报电、"
            "加装配电箱，这笔钱不在展位费里。",
        short_consequence="cost",
        fallback="申请增容（按 kW 收费）、租发电机、或错峰运行设备。",
        typical="标准展位常只配 500W，连一台商用咖啡机都带不动。凡是有电机的展品，"
                "这一项必须提前单独确认。",
    ),
    E5Item(
        id="contractor",
        name="是否强制指定搭建商",
        kind="policy",
        ask="问主办方：特装搭建是否必须用官方指定搭建商？自建需要什么资质"
            "（营业执照/施工资质/保险/押金）？报图审要多长时间？",
        why="强制指定等于失去比价空间，通常比自建贵 30%~100%；"
            "自建则要额外准备资质、保险、押金和报图周期。两条路都要算钱，"
            "但都不至于去不了。",
        short_consequence="cost",
        na_allowed=True,
        fallback="走官方指定搭建商（省事但贵），或补齐自建资质提前报图。",
    ),
    E5Item(
        id="fire",
        name="消防要求（明火 / 材料等级）",
        kind="policy",
        ask="问主办方：展具材料要什么阻燃等级（B1/B2）？有明火或高温设备要怎么办"
            "（是否需要单独报批、配灭火器、加装防火板）？现场有没有消防验收环节？",
        why="材料不达标会被要求现场更换或刷阻燃漆；明火/高温设备通常要额外交材料"
            "和现场看护。这一条不会让你去不成，但会让你现场花钱。",
        short_consequence="cost",
        fallback="改用阻燃材料、现场做阻燃处理、为明火设备单独报批并配看护。",
    ),
    E5Item(
        id="rigging",
        name="吊点使用",
        kind="policy",
        ask="问主办方：展馆是否允许吊装？吊点怎么申请、按点位还是按重量收费？"
            "是否必须由展馆指定人员操作？",
        why="不能吊装就得改自立式结构，桁架、灯架、大屏的支撑成本会明显上升。",
        short_consequence="cost",
        na_allowed=True,
        fallback="改自立式桁架或落地支架，牺牲部分视觉高度换取可行性。",
    ),
)

CHECKLIST_BY_ID: dict[str, E5Item] = {it.id: it for it in E5_CHECKLIST}


def evaluate(states: Optional[dict[str, str]] = None) -> dict:
    """
    把三态答案拼成结论。**没有分数，没有加权。**

    states 里没出现的项一律当 `unknown`——漏填不等于满足。
    这是刻意的：默认值必须是最保守的那个，否则用户填了一半就拿到"通过"。

    `na`（不适用）只对 `na_allowed=True` 的条目生效。标在其余条目上会被降级为
    `unknown`——否则用户可以全标"不适用"直接拿到 pass，清单就失效了。
    """
    states = states or {}
    resolved: dict[str, str] = {}
    blocked: list[str] = []
    costs: list[str] = []
    unknown: list[str] = []
    skipped: list[str] = []

    for it in E5_CHECKLIST:
        raw = states.get(it.id)
        st = raw if raw in VALID_STATES else "unknown"
        # na 只在允许的条目上有效；不允许的降级为 unknown（不能靠"不适用"绕过）
        if st == "na" and not it.na_allowed:
            st = "unknown"
        resolved[it.id] = st

        if st == "na":
            skipped.append(it.id)
            continue
        if st == "unknown":
            unknown.append(it.id)
            continue
        if st == "short":
            (blocked if it.short_consequence == "block" else costs).append(it.id)

    # 优先级 blocked > incomplete > pass_with_cost > pass：
    # 已知做不到就直接判死，不必等未知项；未知项未清零就不能说"通过"。
    if blocked:
        verdict = "blocked"
    elif unknown:
        verdict = "incomplete"
    elif costs:
        verdict = "pass_with_cost"
    else:
        verdict = "pass"

    return {
        "verdict": verdict,
        "blocked": blocked,
        "extra_cost": costs,
        "unresolved": unknown,
        "not_applicable": skipped,
        "answered": [k for k, v in resolved.items() if v in ("ok", "short")],
        "states": resolved,
    }


VERDICT_TEXT: dict[str, tuple[str, str]] = {
    "blocked": (
        "不可行",
        "至少一条物理约束做不到。换展，或换展具/展品方案——这不是加钱能解决的。",
    ),
    "incomplete": (
        "还没问完",
        "还有该向主办方确认的项没有答案。**别猜**：拿清单去问，问完再判断。",
    ),
    "pass_with_cost": (
        "可做，但要加钱",
        "物理约束都过得去，只是有几项要额外花钱。把这笔钱算进 E3 的成本里再决定。",
    ),
    "pass": (
        "可行",
        "八条都满足，交付层面没有拦路的。",
    ),
}


def self_check() -> list[str]:
    """内置自检，返回失败项（空列表 = 全通过）"""
    fails: list[str] = []

    # 条数与 id 唯一性
    if len(E5_CHECKLIST) != 8:
        fails.append(f"应为 8 条，实为 {len(E5_CHECKLIST)}")
    ids = [it.id for it in E5_CHECKLIST]
    if len(set(ids)) != len(ids):
        fails.append("存在重复 id")

    for it in E5_CHECKLIST:
        if not it.ask or not it.why:
            fails.append(f"{it.id} 缺 ask/why")
        if it.short_consequence not in ("block", "cost"):
            fails.append(f"{it.id} short_consequence 非法：{it.short_consequence}")
        if it.short_consequence == "cost" and not it.fallback:
            fails.append(f"{it.id} 判为 cost 却没给替代方案")

    # ---- 核心：任一条 block 就直接 blocked，不受其他项影响（不能加权稀释）----
    r = evaluate({it.id: "ok" for it in E5_CHECKLIST})
    if r["verdict"] != "pass":
        fails.append(f"全 ok 应为 pass，实为 {r['verdict']}")
    r = evaluate({**{it.id: "ok" for it in E5_CHECKLIST}, "height": "short"})
    if r["verdict"] != "blocked":
        fails.append(f"7 项 ok + 层高不满足应为 blocked（不得被加权稀释），实为 {r['verdict']}")
    if r["blocked"] != ["height"]:
        fails.append(f"blocked 应只含 height，实为 {r['blocked']}")

    # cost 类不满足不能判死
    r = evaluate({**{it.id: "ok" for it in E5_CHECKLIST}, "fire": "short"})
    if r["verdict"] != "pass_with_cost":
        fails.append(f"仅消防不满足应为 pass_with_cost，实为 {r['verdict']}")

    # 未知未清零不能说通过，哪怕其余全 ok 且只有 cost
    r = evaluate({**{it.id: "ok" for it in E5_CHECKLIST}, "fire": "short", "rigging": "unknown"})
    if r["verdict"] != "incomplete":
        fails.append(f"有未知项时应为 incomplete（优先于 pass_with_cost），实为 {r['verdict']}")

    # blocked 优先于 incomplete：已知做不到就不必等未知项
    r = evaluate({"height": "short"})
    if r["verdict"] != "blocked":
        fails.append(f"1 条 block + 7 条未知应为 blocked，实为 {r['verdict']}")

    # 空输入 = 全未知 = 不给结论（漏填不等于满足）
    r = evaluate({})
    if r["verdict"] != "incomplete" or len(r["unresolved"]) != 8:
        fails.append(f"空输入应为 incomplete/8 未知，实为 {r['verdict']}/{len(r['unresolved'])}")

    # 非法状态值按 unknown 处理，不能当成 ok
    r = evaluate({"height": "大概吧"})
    if r["states"]["height"] != "unknown":
        fails.append("非法状态值应归一为 unknown")

    # ---- na（不适用）只在特装专属项上有效 ----
    # 标摊展商不用管层高/承重/货运/搭建商/吊点，但躲不开进场时间/供电/消防
    na_items = {it.id for it in E5_CHECKLIST if it.na_allowed}
    if na_items != {"height", "floor_load", "freight", "contractor", "rigging"}:
        fails.append(f"na_allowed 应恰好是五项特装专属项，实为 {sorted(na_items)}")

    r = evaluate({**{it.id: "na" if it.na_allowed else "ok" for it in E5_CHECKLIST}})
    if r["verdict"] != "pass":
        fails.append(f"标摊展商（特装项标 na，其余 ok）应为 pass，实为 {r['verdict']}")
    if len(r["not_applicable"]) != 5:
        fails.append(f"应有 5 项不适用，实为 {len(r['not_applicable'])}")

    # 关键：把 na 标在不可 na 的条目上不能生效，否则「全标不适用」就能拿到通过
    r = evaluate({it.id: "na" for it in E5_CHECKLIST})
    if r["verdict"] != "incomplete":
        fails.append(f"全部标 na 应为 incomplete（只有 5 项允许），实为 {r['verdict']}")
    if len(r["unresolved"]) != 3:
        fails.append(f"全标 na 应剩 3 项仍未解决，实为 {len(r['unresolved'])}")

    return fails
