"""
LLM 抽取的防幻觉闸门离线自测（不需要 key、不联网）。

这套测试针对的不是"LLM 抽得准不准"，而是**它编的时候会不会被放进来**。
llm_extract.py 里唯一的防线是 _verify()：evidence 必须是正文里逐字出现的原文，
且数值要能在 evidence 里找到。少了这一步，模型会稳定产出格式完美、
日期合理、但页面上根本不存在的展期——而这类错误在下游看起来毫无破绽。

运行：python scripts/persona/test_llm_gate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_extract import _cn, _flat, _json_of, _norm_date, _norm_sep, _slices, _verify  # noqa: E402

BODY = """
2027中国国际五金展
第二十五届中国国际五金展（CIHS 2027）将于2027年3月17-20日
在国家会展中心（上海）举办，主办单位：中国五金制品协会。
展位申请截止日期：2027年1月31日。
"""
BODY_FLAT = _flat(_norm_sep(BODY))   # 与 _verify 内部口径一致：去空白 + 统一破折号/括号


def run() -> int:
    fails: list[str] = []

    def chk(cond: bool, msg: str):
        if not cond:
            fails.append(msg)

    # ---- 应该保留：原文有据 ----
    ok, why = _verify("2027-03-17", "2027年3月17-20日", BODY_FLAT, "date")
    chk(ok, f"原文含 2027年3月17-20日，应通过（{why}）")
    ok, why = _verify("国家会展中心（上海）", "在国家会展中心（上海）举办", BODY_FLAT, "text")
    chk(ok, f"场馆原文有据，应通过（{why}）")
    ok, why = _verify("2027-01-31", "展位申请截止日期：2027年1月31日", BODY_FLAT, "date")
    chk(ok, f"截止日原文有据，应通过（{why}）")
    ok, why = _verify("中国五金制品协会", "主办单位：中国五金制品协会", BODY_FLAT, "text")
    chk(ok, f"主办方原文有据，应通过（{why}）")

    # ---- 应该拦下：原文没有 / 日期对不上 / 依据太短 ----
    ok, why = _verify("2027-05-08", "将于2027年5月8日举办", BODY_FLAT, "date")
    chk(not ok and "不在正文" in why, f"编造的展期应被拦下，实际：{ok}/{why}")
    ok, why = _verify("2027-03-18", "2027年3月17-20日", BODY_FLAT, "date")
    chk(not ok, f"依据是区间、取值在区间外，应拦下（{why}）")
    ok, why = _verify("2027-03-17", "举办", BODY_FLAT, "date")
    chk(not ok and "过短" in why, f"依据过短应拦下（{why}）")
    ok, why = _verify("北京", "在国家会展中心（上海）举办", BODY_FLAT, "text")
    chk(not ok and "不在依据" in why, f"取值不在依据里，应拦下（{why}）")

    # ---- 回归：日期必须走 date 口径，不能当文本做子串比对 ----
    # 这是实测踩到的 bug：ISO 值 "2027-03-27" 永远不是 "2027年3月27日-4月5日" 的子串，
    # 47 个 start_date 全被误杀。
    ok, why = _verify("2027-03-17", "2027年3月17 - 20日", BODY_FLAT, "date")
    chk(ok, f"ISO 取值 + 中文区间依据，应通过（{why}）")
    ok, why = _verify("2027-01-31", "2027年1月31日", BODY_FLAT, "date")
    chk(ok, f"单日依据应通过（{why}）")

    # ---- 回归：顿号连接的多机构，逐段核验 ----
    seg_body = _flat(_norm_sep("主办单位 上海市国际贸易促进委员会 中国汽车工业协会 承办单位 某公司"))
    ok, why = _verify("上海市国际贸易促进委员会、中国汽车工业协会",
                      "主办单位 上海市国际贸易促进委员会 中国汽车工业协会", seg_body, "text")
    chk(ok, f"多机构用顿号连接、原文空格分隔，应通过（{why}）")
    ok, why = _verify("上海市国际贸易促进委员会、不存在的协会",
                      "主办单位 上海市国际贸易促进委员会 中国汽车工业协会", seg_body, "text")
    chk(not ok, f"其中一段不在依据里，应拦下（{why}）")

    # ---- 回归：展馆名的括号差异 ----
    vb = _flat(_norm_sep("将于2027年7月14-16日在上海国家会展中心（NECC）举行"))
    ok, why = _verify("国家会展中心（上海）", "在上海国家会展中心（NECC）举行", vb, "text")
    chk(ok, f"括号内城市/缩写不同、核心名一致，应通过（{why}）")
    ok, why = _verify("深圳国际会展中心", "在上海国家会展中心（NECC）举行", vb, "text")
    chk(not ok, f"核心名不同，应拦下（{why}）")

    # ---- 回归：全角/半角括号混用（进博会实测：同一页面两种写法并存） ----
    pb = _flat(_norm_sep("国家会展中心(上海)开启“夜景模式”"))
    ok, why = _verify("国家会展中心（上海）", "国家会展中心(上海)开启“夜景模式”", pb, "text")
    chk(ok, f"全角括号取值 vs 半角括号依据，应通过（{why}）")
    ok, why = _verify("国家会展中心(上海)", "国家会展中心（上海）", _flat(_norm_sep("国家会展中心（上海）")), "text")
    chk(ok, f"半角括号取值 vs 全角括号依据，应通过（{why}）")

    # ---- 回归：各种真实日期写法（这些曾经全被判"抽不到日期"） ----
    date_cases = [
        ("2027-04-13", "2027·4·13 - 16", "间隔号写法"),
        ("2027-09-01", "1-3 September 2027", "英文日在前"),
        ("2027-04-14", "Apr. 14—16, 2027", "英文月在前 + em dash"),
        ("2027-10-12", "10月12日—14日，CWP2027 将在北京", "中文无年份、年份在展名里"),
        ("2027-06-30", "2027年06月27日 -- 2027年06月30日", "双连字符区间"),
    ]
    for iso, ev, why_txt in date_cases:
        ok, why = _verify(iso, ev, _flat(_norm_sep(ev)), "date")
        chk(ok, f"{why_txt} {ev!r} → {iso} 应通过（{why}）")

    # 依据里的年份与取值冲突，必须拦下（防止"2026 年的日期配 2027 年的展名"混进来）
    yb = _flat(_norm_sep("10月12日—14日，CWP2027 将在北京"))
    ok, why = _verify("2026-10-12", "10月12日—14日，CWP2027 将在北京", yb, "date")
    chk(not ok and "年份" in why, f"依据年份不符应拦下（{why}）")
    ok, why = _verify(None, "2027年3月17-20日", BODY_FLAT, "date")
    chk(not ok, "null 不应产生字段")

    # ---- 日期归一化 ----
    chk(_norm_date("2027/3/17") == "2027-03-17", "斜杠日期应归一")
    chk(_norm_date("2027.3.17") == "2027-03-17", "点分日期应归一")
    chk(_norm_date("2027年3月17日") is None, "中文日期应判非法（prompt 要求 ISO）")
    chk(_norm_date("2027-02-30") is None, "不存在的日期应判非法")
    chk(_norm_date("") is None, "空串应判非法")

    # ---- 中文届次 ----
    chk(_cn("第二十五届中国国际五金展") == 25, "第二十五届 → 25")
    chk(_cn("第七届XX论坛") == 7, "第七届 → 7")
    chk(_cn("第一百零二届") == 102, "第一百零二届 → 102")
    chk(_cn("中国国际五金展") is None, "无届次 → None")

    # ---- JSON 解析容错 ----
    chk(_json_of('{"a":1}') == {"a": 1}, "纯 JSON 应解析")
    chk(_json_of('```json\n{"a":1}\n```') == {"a": 1}, "代码块包裹应剥离")
    chk(_json_of('好的，结果如下：{"a":1} 以上。') == {"a": 1}, "前后有废话应取最外层花括号")
    chk(_json_of("完全不是 JSON") == {}, "非 JSON 应返回空 dict 而不是抛异常")

    # ---- 正文切片 ----
    long_body = "A" * 6000 + "……展位申请截止日期：2027年1月31日……" + "B" * 10000
    s = _slices(long_body)
    chk(len(s) <= 11000, f"切片应不超过 11000 字，实为 {len(s)}")
    chk("截止日期" in s, "切片应把含'截止'的段落捞进来")
    chk(s.startswith("A" * 100), "切片应保留开头")

    total = 39
    if fails:
        print("FAIL %d / %d" % (len(fails), total))
        for f in fails:
            print("  -", f)
        return 1
    print("OK %d 项全部通过" % total)
    return 0


if __name__ == "__main__":
    sys.exit(run())
