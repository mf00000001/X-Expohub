"""
批次 1 抽取器的离线自测（不联网）。

重点不是"能抽出正常格式"，而是**不该抽的时候不抽**：
把展位价格、电话号码、无关数字当成日期，会让 E4 的门限判断全错，
而且错了不会报错、只会在下游变成一个看起来合理的分数。

运行：python scripts/persona/test_extractors.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from datetime import date  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_skeleton import (  # noqa: E402
    classify_dates, dates_sane, extract_dates, extract_deadline, extract_edition,
    extract_organizer, extract_venue,
)

CASES_DATE = [
    ("2027年3月17-20日在上海举办", ("2027-03-17", "2027-03-20")),
    ("时间：2026年11月10日至12日", ("2026-11-10", "2026-11-12")),
    ("2026年11月10日-11月12日", ("2026-11-10", "2026-11-12")),
    ("2026年12月30日-2027年1月2日", ("2026-12-30", "2027-01-02")),
    ("2026-11-10 ~ 2026-11-12 国家会展中心", ("2026-11-10", "2026-11-12")),
    ("2026.11.10-12", ("2026-11-10", "2026-11-12")),
    ("March 17-20, 2027 · Shanghai", ("2027-03-17", "2027-03-20")),
    ("Nov 10 - 12, 2026", ("2026-11-10", "2026-11-12")),
    ("Apr. 14—16, 2027", ("2027-04-14", "2027-04-16")),
    ("1-3 September 2027", ("2027-09-01", "2027-09-03")),
    ("深圳 2026. 7. 24 ~ 26", ("2026-07-24", "2026-07-26")),
    ("2027·4·13 - 16", ("2027-04-13", "2027-04-16")),
    ("2027 年 3 月 17 日 开幕", ("2027-03-17", "2027-03-17")),
    ("2027年3月17日 开幕", ("2027-03-17", "2027-03-17")),
]

# 这些都不该被当成展期
CASES_DATE_NEG = [
    "展位价格：2026元/平方米",
    "联系电话 400-630-8600",
    "第 25 届中国国际展览",
    "Copyright 2026 版权所有",
    "已有 300000 人次参观",
]

CASES_VENUE = [
    ("上海新国际博览中心 N1 馆", ("上海新国际博览中心", "上海")),
    ("广州·广交会展馆 A 区", ("广交会展馆", "广州")),
    ("深圳国际会展中心（宝安）", ("深圳国际会展中心", "深圳")),
    ("地点：上海", (None, "上海")),
]

CASES_OTHER = [
    ("edition", "第二十五届中国国际五金展", 25),
    ("edition_none", "中国国际五金展", None),
    ("organizer", "主办单位：中国五金制品协会 承办单位：某展览", "中国五金制品协会"),
    ("organizer_none", "欢迎参观", None),
]


def run() -> int:
    fails: list[str] = []

    for txt, want in CASES_DATE:
        s, e, _ = extract_dates(txt)
        if (s, e) != want:
            fails.append(f"日期  {txt!r} → ({s},{e})，期望 {want}")

    for txt in CASES_DATE_NEG:
        s, e, _ = extract_dates(txt)
        if s:
            fails.append(f"日期误抽 {txt!r} → ({s},{e})，应全部为 None")

    for txt, want in CASES_VENUE:
        v, c, _ = extract_venue(txt)
        if (v, c) != want:
            fails.append(f"场馆  {txt!r} → ({v},{c})，期望 {want}")

    for kind, txt, want in CASES_OTHER:
        if kind.startswith("edition"):
            got = extract_edition(txt)[0]
        else:
            got = extract_organizer(txt)[0]
        if got != want:
            fails.append(f"{kind}  {txt!r} → {got!r}，期望 {want!r}")

    # 截止日：只在"截止"附近认日期
    d, _ = extract_deadline("展位申请截止日期：2026年6月30日")
    if d != "2026-06-30":
        fails.append(f"截止日 → {d!r}，期望 2026-06-30")
    d2, _ = extract_deadline("2026年6月30日 开展，额满即止")
    if d2 is not None:
        fails.append(f"截止日误抽 → {d2!r}，无'截止'字样应为 None")

    # 日期合理性：防的是把往届回顾日期当本届
    today = date(2026, 11, 3)
    sane = [
        ("2027-03-17", "2027-03-20", True, "正常"),
        ("2019-05-01", "2019-05-03", False, "往届/过旧"),
        ("2025-04-21", "2025-04-26", False, "已结束约19个月的往届（CIMT 真实情形）"),
        ("2026-11-12", "2026-11-10", False, "结束早于开始"),
        ("2026-01-01", "2026-12-31", False, "跨度超60天"),
        ("2032-01-01", "2032-01-03", False, "超远期"),
    ]
    for s, e, want, why in sane:
        got, _ = dates_sane(s, e, today)
        if got != want:
            fails.append(f"合理性 {s}~{e}（{why}）→ {got}，期望 {want}")

    # 三态分类：往届必须保留（能推出"通常几月办"），但状态不能是 current
    three = [
        ("2027-03-17", "2027-03-20", "current", 3, "本届"),
        ("2026-11-12", "2026-11-14", "current", 11, "本月开展"),
        ("2025-04-21", "2025-04-26", "past", 4, "CIMT 往届 19 个月"),
        ("2026-10-21", "2026-10-24", "past", 10, "刚结束 13 天，不得冒充本届"),
        ("2026-11-03", "2026-11-05", "current", 11, "今天开展：日期仍是本届，由 E4 判 closed"),
        ("2019-05-01", "2019-05-03", "past", 5, "很久以前的往届"),
    ]
    for s, e, want_st, want_m, why in three:
        st, _, m = classify_dates(s, e, today)
        if st != want_st or m != want_m:
            fails.append(f"三态 {s}（{why}）→ {st}/{m}，期望 {want_st}/{want_m}")

    # 往届记录必须留得下来：prev_start_date 而不是 start_date
    for s, e in (("2025-04-21", "2025-04-26"), ("2026-10-21", "2026-10-24")):
        st, _, _ = classify_dates(s, e, today)
        if st != "past":
            fails.append(f"{s} 应为 past，实为 {st}")

    total = (len(CASES_DATE) + len(CASES_DATE_NEG) + len(CASES_VENUE)
             + len(CASES_OTHER) + 2 + len(sane) + len(three) + 0)
    if fails:
        print("FAIL %d / %d" % (len(fails), total))
        for f in fails:
            print("  -", f)
        return 1
    print("OK %d 项全部通过" % total)
    return 0


if __name__ == "__main__":
    sys.exit(run())
