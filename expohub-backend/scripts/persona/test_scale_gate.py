"""
批次 2（规模与属性）的防幻觉闸门离线自测（不需要 key、不联网）。

批次 1 的闸门判的是"依据里有没有这个字符串"，批次 2 判的是
"**这个数能不能从依据里算出来**"——模型给 300000，原文写"超30万人次"，
数字串对不上，必须先把"30万"折算成 300000 再比。所以这里测的核心是
parse_quantities()：它是整条口径判定的地基，它认不出的写法，
下游一律表现为"模型答错"，实际是自己没认出来。

用例全部取自真实页面写法（含英文站的"数字在前"语序），不是编的。

运行：python scripts/persona/test_scale_gate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_scale import (  # noqa: E402
    ADMISSION_STRONG, ADMISSION_WEAK, NATURE_STRONG, NATURE_WEAK,
    _cat_ok, _num_ok, parse_quantities, shape,
)
from llm_extract import _flat, _norm_sep  # noqa: E402


def _q(text: str) -> list[dict]:
    return parse_quantities(text)


def _one(text: str) -> dict | None:
    qs = _q(text)
    return qs[0] if qs else None


def run() -> int:
    fails: list[str] = []
    checks = 0

    def chk(cond: bool, msg: str):
        nonlocal checks
        checks += 1
        if not cond:
            fails.append(msg)

    # ================= 一、数量解析：中文量级 =================
    q = _one("超30万人次")
    chk(q is not None and q["value"] == 300000 and q["kind"] == "visitor"
        and q["caliber"] == "visit", f"超30万人次 → 300000/visit，实为 {q}")

    q = _one("吸引专业观众12.6万人")
    chk(q is not None and q["value"] == 126000 and q["kind"] == "visitor"
        and q["caliber"] == "person", f"12.6万人 → 126000/person，实为 {q}")

    q = _one("2500余家企业参展")
    chk(q is not None and q["value"] == 2500 and q["kind"] == "exhibitor"
        and q["caliber"] == "company", f"2500余家企业 → 2500/company，实为 {q}")

    q = _one("1.2万家企业")
    chk(q is not None and q["value"] == 12000, f"1.2万家企业 → 12000，实为 {q}")

    q = _one("展出面积达30万平方米")
    chk(q is not None and q["value"] == 300000 and q["kind"] == "area"
        and q["caliber"] == "gross", f"30万平方米 → 300000/gross，实为 {q}")

    # 空格分隔（页面排版常见）+ 万 + 平方米 三个成分分开
    q = _one("展览面积 12.6 万 平方米")
    chk(q is not None and q["value"] == 126000, f"空格分隔的 12.6 万 平方米 → 126000，实为 {q}")

    q = _one("净展出面积8万平方米")
    chk(q is not None and q["caliber"] == "net", f"净面积应标 net，实为 {q}")

    q = _one("展位总数5000个展位")
    chk(q is not None and q["kind"] == "booth" and q["value"] == 5000,
        f"5000个展位 → booth/5000，实为 {q}")

    q = _one("汇聚3000个品牌")
    chk(q is not None and q["caliber"] == "brand", f"3000个品牌 应标 brand，实为 {q}")

    # 通用量词陷阱：单看"个"推不出任何东西
    q = _one("共设30个展馆")
    chk(q is not None and q["kind"] == "unknown",
        f"'30个展馆' 不能当展位数（否则展商数 30 会被误放行），实为 {q}")

    # 千分位
    q = _one("参观人数达 120,000 人")
    chk(q is not None and q["value"] == 120000, f"120,000 人 → 120000，实为 {q}")

    # 口径写在单位后面的括号里
    q = _one("120000+专业观众(人次)")
    chk(q is not None and q["caliber"] == "visit", f"(人次) 应判 visit，实为 {q}")

    # 同一句里"人数"和"人次"并存时不能串味
    qs = {int(q["value"]): q["caliber"]
          for q in _q("专业观众总数211,993人，展会总参观人次达416,570人次")}
    chk(qs.get(211993) == "person", f"211,993人 应判 person，实为 {qs.get(211993)}")
    chk(qs.get(416570) == "visit", f"416,570人次 应判 visit，实为 {qs.get(416570)}")

    # ================= 二、数量解析：英文站（数字在前） =================
    q = _one("Exhibition Scale 79,026 Visitors")
    chk(q is not None and q["value"] == 79026 and q["kind"] == "visitor",
        f"79,026 Visitors → 79026/visitor，实为 {q}")

    q = _one("2,630 Exhibitors from 20 countries")
    chk(q is not None and q["value"] == 2630 and q["kind"] == "exhibitor",
        f"2,630 Exhibitors → 2630，实为 {q}")

    q = _one("an exhibition area of 120,000 square meters")
    chk(q is not None and q["value"] == 120000 and q["kind"] == "area",
        f"120,000 square meters → 120000/area，实为 {q}")

    q = _one("Booth Booking 200,000 ㎡")
    chk(q is not None and q["value"] == 200000 and q["kind"] == "area",
        f"200,000 ㎡ → 200000/area，实为 {q}")

    q = _one("over 12.5K visitors")
    chk(q is not None and q["value"] == 12500, f"12.5K visitors → 12500，实为 {q}")

    q = _one("2.5 million visitors")
    chk(q is not None and q["value"] == 2500000, f"2.5 million visitors → 2500000，实为 {q}")

    # 不能把"20 countries"当人数
    qs = _q("79,026 Visitors from 20 Countries")
    chk(len(qs) == 1, f"只应解析出 1 个数量（countries 不是单位），实为 {len(qs)} 个：{qs}")

    # ============ 二·五、真实页面原句回归（试点里实际踩到的句子） ============
    # 这几条是试点 6 个站得出的原文，改解析器时它们必须一直过。
    case = ("covered an exhibition area of 120,000 square meters, "
            "and attracted 79,026 professional visitors")
    qs = _q(case)
    chk(any(q["value"] == 79026 and q["kind"] == "visitor" for q in qs),
        f"形容词间隔的 79,026 professional visitors 必须能解析，实为 {qs}")
    chk(any(q["value"] == 120000 and q["kind"] == "area" for q in qs),
        f"同一句里的 120,000 square meters 也要解析，实为 {qs}")

    qs = _q("brought together 2,065 well-known domestic and international industry brands")
    chk(any(q["value"] == 2065 and q["kind"] == "exhibitor" for q in qs),
        f"5 个形容词间隔的 2,065 ... brands 必须能解析，实为 {qs}")

    qs = _q("20万+ 行业观众  5000+ 参展企业")
    chk(any(q["value"] == 200000 and q["kind"] == "visitor" for q in qs),
        f"20万+ 行业观众 必须能解析，实为 {qs}")
    chk(any(q["value"] == 5000 and q["kind"] == "exhibitor" for q in qs),
        f"5000+ 参展企业 必须能解析，实为 {qs}")

    qs = _q("2500 International standard booths")
    chk(any(q["value"] == 2500 and q["kind"] == "booth" for q in qs),
        f"2500 standard booths 应解析成展位数，实为 {qs}")

    qs = _q("attracted 66,517 trade professionals")
    chk(any(q["value"] == 66517 and q["kind"] == "visitor" for q in qs),
        f"66,517 trade professionals 必须能解析，实为 {qs}")

    # 干扰词不能把单位抢走："5000个展位" 曾经被解析成 5000 位观众
    q = _one("5000个展位")
    chk(q is not None and q["kind"] == "booth",
        f"5000个展位 必须判成展位数，实为 {q}")

    # 词界："standard" 不能因为包含 "stand" 就被当成展位单位
    qs = _q("25 standards compliant")
    chk(not any(q["kind"] == "booth" for q in qs),
        f"standards 不该被当成 stand，实为 {qs}")

    # 单位裹在括号里：括号不去掉就永远配不上
    qs = _q("170,000展览面积(平米)")
    chk(any(q["value"] == 170000 and q["kind"] == "area" for q in qs),
        f"170,000展览面积(平米) 必须解析成面积，实为 {qs}")

    # 反向语序：标签在前、数字在后（"展商数量5100+专业观众380000+"）
    qs = _q("展会规模850000㎡展商数量5100+专业观众380000+")
    chk(any(q["value"] == 850000 and q["kind"] == "area" for q in qs),
        f"850000㎡ 面积必须解析，实为 {qs}")
    chk(any(q["value"] == 5100 and q["kind"] == "exhibitor" for q in qs),
        f"展商数量5100 必须判成展商数（不是被后面的观众标签抢走），实为 {qs}")
    chk(any(q["value"] == 380000 and q["kind"] == "visitor" for q in qs),
        f"专业观众380000 必须解析成观众数，实为 {qs}")

    # 数字在前、标签在后连排（面积标签是前一个数的后缀）
    qs = _q("120,000展会面积800展商数量56,029观众数量")
    chk(any(q["value"] == 120000 and q["kind"] == "area" for q in qs),
        f"120,000展会面积 必须解析成面积，实为 {qs}")
    chk(any(q["value"] == 800 and q["kind"] == "exhibitor" for q in qs),
        f"800展商数量 必须解析成展商数，实为 {qs}")
    chk(any(q["value"] == 56029 and q["kind"] == "visitor" for q in qs),
        f"56,029观众数量 必须解析成观众数，实为 {qs}")

    # ================= 三、_num_ok：类型 + 数量级 =================
    qs = _q("79,026 Visitors")
    ok, why = _num_ok(79026, qs, ("visitor",))
    chk(ok, f"79026 应被 79,026 Visitors 支持（{why}）")

    ok, why = _num_ok(79026 * 1.5, qs, ("visitor",))
    chk(not ok, "数量级差 50% 不能放行")

    ok, why = _num_ok(2630, qs, ("exhibitor",))
    chk(not ok, f"观众数不能顶展商数（{why}）")

    # 圆整容差：原文"约8万"，模型给 80000
    ok, _ = _num_ok(80000, _q("约8万人"), ("visitor",))
    chk(ok, "8万 应支持 80000")

    # 展位数代替展商数：放行，但必须能看出这是展位数
    ok, _ = _num_ok(5000, _q("5000个展位"), ("exhibitor", "booth"))
    chk(ok, "展位数应可替代展商数（靠 caliber 标明）")

    # ================= 四、分类字段 =================
    ADM = (ADMISSION_STRONG, ADMISSION_WEAK)
    NAT = (NATURE_STRONG, NATURE_WEAK)

    ok, conf, why = _cat_ok("trade_only", "本展仅限专业人士参观，需提供营业执照", ADM)
    chk(ok and conf == "medium", f"仅限专业人士应判 trade_only/medium（{why}）")

    ok, conf, why = _cat_ok("public", "现场可购票入场，欢迎市民参观", ADM)
    chk(ok and conf == "medium", f"可购票应判 public/medium（{why}）")

    # 只有弱证据：保留，但必须降 confidence（真实页面上这类占多数）
    ok, conf, why = _cat_ok("trade_only", "观众登记", ADM)
    chk(ok and conf == "low", f"只有'观众登记'应保留但降为 low（{why}）")

    # 连弱证据都没有：拿口号证明准入类型，必须拦
    ok, conf, why = _cat_ok("trade_only", "本人承诺：严格遵守展会现场秩序", ADM)
    chk(not ok, f"口号句不能证明准入类型（{why}）")

    ok, conf, why = _cat_ok("trade_only", "欢迎广大市民前来参观", ADM)
    chk(not ok or conf == "low", "依据里没有 trade_only 的判别词，不能给 medium")

    ok, conf, why = _cat_ok("B2B", "面向专业买家与采购商的贸易平台", NAT)
    chk(ok and conf == "medium", f"面向专业买家应判 B2B/medium（{why}）")

    ok, conf, why = _cat_ok("B2B", "通过B2B和B2C融合办展模式", NAT)
    chk(not ok or conf == "low",
        f"同时出现 B2B/B2C 本应判 mixed，至少不能给 medium（实得 {ok},{conf}）")

    ok, conf, why = _cat_ok("D2C", "面向专业买家", NAT)
    chk(not ok, "不在允许集合内的取值必须拒绝")

    # ================= 五、shape()：整条链路的拦截 =================
    BODY = (
        "2027中国国际五金展\n"
        "展出面积达30万平方米，汇聚2500余家企业，吸引专业观众12.6万人次。\n"
        "本展仅限专业人士参观，需提供营业执照。\n"
        "上届共有2000家企业参展，观众10万人次。\n"
    )

    def call(payload: dict) -> dict:
        import json
        return shape("t", BODY, json.dumps(payload, ensure_ascii=False))

    good = {
        "visitor_count": {"value": 126000, "raw_text": "12.6万人次",
                          "unit": "人次", "caliber": "visit",
                          "evidence": "吸引专业观众12.6万人次"},
        "exhibitor_count": {"value": 2500, "raw_text": "2500余家企业",
                            "unit": "家", "caliber": "company",
                            "evidence": "汇聚2500余家企业"},
        "exhibition_area": {"value": 300000, "raw_text": "30万平方米",
                            "unit": "平方米", "caliber": "gross",
                            "evidence": "展出面积达30万平方米"},
        "admission": {"value": "trade_only", "raw_text": "", "unit": "", "caliber": "",
                      "evidence": "本展仅限专业人士参观，需提供营业执照"},
        "text_note": "",
    }
    r = call(good)
    chk(r["fields"].get("visitor_count", {}).get("value") == 126000, "12.6万人次应落库")
    chk(r["fields"].get("exhibitor_count", {}).get("caliber") == "company", "企业数口径应为 company")
    chk(r["fields"].get("exhibition_area", {}).get("value") == 300000, "30万平方米应落库")
    chk(r["fields"].get("admission", {}).get("value") == "trade_only", "准入类型应落库")

    # 编造的依据：正文里没有这句话
    fake = dict(good)
    fake["exhibition_area"] = {"value": 500000, "raw_text": "50万平方米", "unit": "平方米",
                               "caliber": "gross", "evidence": "展出面积达50万平方米"}
    r = call(fake)
    chk("exhibition_area" not in r["fields"], "依据不在正文里必须拦下")
    chk(r["dropped"].get("exhibition_area", {}).get("why") == "依据不在正文中",
        "拦截原因应为'依据不在正文中'")

    # 依据真、但数字对不上（模型把上届数据填成本届）
    wrong = dict(good)
    wrong["exhibitor_count"] = {"value": 2000, "raw_text": "2500余家企业", "unit": "家",
                                "caliber": "company", "evidence": "汇聚2500余家企业"}
    r = call(wrong)
    chk("exhibitor_count" not in r["fields"], "依据写 2500 却填 2000，必须拦下")
    chk("数值对不上" in r["dropped"].get("exhibitor_count", {}).get("why", ""),
        f"拦截原因应指出数值对不上，实为 {r['dropped'].get('exhibitor_count')}")

    # 依据是一句概括语，raw_text 才是含数字的短语 → 用 raw_text 兜底
    rescue = dict(good)
    rescue["visitor_count"] = {"value": 126000, "raw_text": "12.6万人次", "unit": "人次",
                               "caliber": "visit", "evidence": "吸引了大批专业观众到场"}
    # 先把这句概括语塞进正文，模拟真实页面
    BODY2 = BODY.replace("吸引专业观众12.6万人次", "吸引专业观众12.6万人次，吸引了大批专业观众到场")
    import json as _json
    r = shape("t2", BODY2, _json.dumps(rescue, ensure_ascii=False))
    chk(r["fields"].get("visitor_count", {}).get("evidence_span") == "raw_text",
        "概括语凑不出数时，应改用 raw_text 兜底并标注 evidence_span")

    # 模型自述口径与原文冲突 → 以原文为准并记冲突
    conflict = dict(good)
    conflict["visitor_count"] = {"value": 126000, "raw_text": "12.6万人次", "unit": "人次",
                                 "caliber": "person", "evidence": "吸引专业观众12.6万人次"}
    r = call(conflict)
    chk(r["fields"].get("visitor_count", {}).get("caliber") == "visit",
        "原文写人次，口径必须以 visit 为准")
    chk("visitor_count" in r.get("caliber_conflict", {}), "口径冲突必须留痕")

    # 上届数据：正文里有，应能抽到 prev_*
    prev = {
        "prev_exhibitor_count": {"value": 2000, "raw_text": "2000家企业", "unit": "家",
                                 "caliber": "company", "evidence": "上届共有2000家企业参展"},
        "prev_visitor_count": {"value": 100000, "raw_text": "10万人次", "unit": "人次",
                               "caliber": "visit", "evidence": "观众10万人次"},
        "text_note": "",
    }
    r = call(prev)
    chk(r["fields"].get("prev_exhibitor_count", {}).get("value") == 2000, "上届展商数应落库")
    chk(r["fields"].get("prev_visitor_count", {}).get("value") == 100000, "上届观众数应落库")

    # 空结果：什么都没抽到，ok 必须是 False（否则会被当成"已完成"跳过）
    r = call({"text_note": ""})
    chk(r["ok"] is False, "一个字段都没抽到，ok 必须为 False")

    if fails:
        print("FAIL %d / %d" % (len(fails), checks))
        for f in fails:
            print("  -", f)
        return 1
    print("OK %d 项全部通过" % checks)
    return 0


if __name__ == "__main__":
    sys.exit(run())
