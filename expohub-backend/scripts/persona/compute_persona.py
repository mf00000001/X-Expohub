"""
把 expo 表里的原始字段算成画像（E1 + E4），写入 expo_persona。

这是画像层第一次真正出结果：在此之前 expo_persona 是空表，所有判断都还停在
"字段有没有抽到"这一层。这一层只做三件事——归一化、分档、落参，
不做加权求和（原因见 docs/展会画像-维度清单.md 10.1：约束和偏好不能放同一个天平）。

两个模式：
    python scripts/persona/compute_persona.py --calibrate   # 只算分布，看档位切得对不对
    python scripts/persona/compute_persona.py               # 落库

参数（档位、折算系数、E2 开关）统一写进 persona_param，带上版本号：
标定值散落在代码里，下次改的人根本不知道自己改的是"标定"还是"逻辑"。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.modules.persona import bands  # noqa: E402

DB = ROOT / "persona.db"
PARAMS_VERSION = bands.RATIO_CALIBRATION["version"]


def _pct(xs: list[float], p: float) -> float:
    k = (len(xs) - 1) * p
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def calibrate(con: sqlite3.Connection) -> None:
    rows = [dict(r) for r in con.execute(
        "SELECT slug, visitor_count v, visitor_caliber vc, exhibitor_count e"
        " FROM expo WHERE visitor_count>0 AND exhibitor_count>0")]
    print("可算观众/展商比的展：%d / %d" % (len(rows), con.execute(
        "SELECT COUNT(*) FROM expo").fetchone()[0]))
    if not rows:
        return

    def adj(r):
        v = r["v"] / bands.VISIT_TO_PERSON if (r["vc"] or "") == "visit" else r["v"]
        return v / r["e"]

    raw = sorted(r["v"] / r["e"] for r in rows)
    norm = sorted(adj(r) for r in rows)
    for name, xs in (("原始", raw), ("人次÷%.1f 归一" % bands.VISIT_TO_PERSON, norm)):
        print("\n%s  n=%d  P25=%.1f  P50=%.1f  P75=%.1f" % (
            name, len(xs), _pct(xs, .25), _pct(xs, .5), _pct(xs, .75)))
        for band, (th, _) in zip("ample normal thin severe".split(), bands.RATIO_BANDS):
            n = sum(1 for x in xs if x >= th)
            print("    ≥%-6.1f %-8s %2d 个" % (th, band, n))

    print("\n当前常量：P25=%.1f P50=%.1f P75=%.1f（版本 %s）" % (
        bands.RATIO_BANDS[2][0], bands.RATIO_BANDS[1][0], bands.RATIO_BANDS[0][0],
        bands.RATIO_CALIBRATION["version"]))
    drift = max(abs(_pct(norm, .25) - bands.RATIO_BANDS[2][0]),
                abs(_pct(norm, .5) - bands.RATIO_BANDS[1][0]),
                abs(_pct(norm, .75) - bands.RATIO_BANDS[0][0]))
    print("与常量的最大偏差：%.1f（>10 说明样本变了，该重新标定）" % drift)

    print("\n最低 6 个：")
    for r in sorted(rows, key=adj)[:6]:
        print("    %-18s %7d/%-5d = %5.1f  [%s]" % (
            r["slug"], r["v"], r["e"], adj(r), r["vc"]))


def _dates_status(start_iso, today: date, end_iso=None) -> str:
    """
    expo 表没存 dates_status，按开展日反推。和采集层的三态口径一致。

    **必须看 end_date**：只比 start_date 会把"正在办的展"判成 past。
    广交会 2026-10-15 开展、11-04 闭幕，11-03 去看时 start 已过 19 天，
    但它还在展期里——这恰恰是用户最需要看到的一个展，判成 past 会让它
    掉进"无本届可用日期"分支、E4 显示 unknown，等于把它从推荐里抹掉。

    没有 end_date 时才退回用 start_date 判断（偏保守：宁可少列，不要误列）。
    """
    if not start_iso:
        return "none"

    def _d(s):
        try:
            return date.fromisoformat(s[:10])
        except (ValueError, TypeError):
            return None

    start = _d(start_iso)
    if start is None:
        return "none"
    end = _d(end_iso) or start
    return "past" if end < today else "current"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--today", default="")
    args = ap.parse_args()

    today = date.fromisoformat(args.today) if args.today else date.today()
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    if args.calibrate:
        calibrate(con)
        return 0

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = list(con.execute("SELECT * FROM expo"))
    con.execute("DELETE FROM expo_persona")

    stat = {"ample": 0, "normal": 0, "thin": 0, "severe": 0, "unknown": 0}
    gate = 0
    for r in rows:
        ds = _dates_status(r["start_date"], today, r["end_date"])
        p = bands.compute_all(
            visitor_count=r["visitor_count"], exhibitor_count=r["exhibitor_count"],
            visitor_caliber=r["visitor_caliber"], deadline_iso=r["booth_deadline"],
            today=today, start_date_iso=r["start_date"], end_date_iso=r["end_date"],
            dates_status=ds,
            # 去展网等第三方来源的规模数，比值照算但要留痕：
            # 实测第三方观众数比官网低 20~25%，档位会跟着偏低。
            ratio_source="thirdparty" if (r["scale_source"] or "") == "qufair" else "official",
        )
        stat[p["ratio_band"]] = stat.get(p["ratio_band"], 0) + 1
        if p["e4_role"] == "gate":
            gate += 1
        note = " | ".join(x for x in (
            "ratio_basis=" + p["ratio_basis"],
            "ratio_source=" + p["ratio_source"],
            "e4_role=" + p["e4_role"],
            "e4_source=" + str(p["e4_source"]),
            "e4:" + (p["e4_note"] or p["e4_band"]),
            "e2 已暂停" if p["e2_discount"] is None else "e2=%.3f" % p["e2_discount"],
        ) if x)
        con.execute(
            "INSERT INTO expo_persona (expo_id, params_version, computed_at,"
            " visitor_exhibitor_ratio, ratio_band, e1_lo, e1_mid, e1_hi, e1_confidence,"
            " e4_band, e4_days_left, e4_deadline, note)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (r["id"], PARAMS_VERSION, now, p["visitor_exhibitor_ratio"], p["ratio_band"],
             p["e1_lo"], p["e1_mid"], p["e1_hi"], p["e1_confidence"],
             p["e4_band"], p["e4_days_left"], p["e4_deadline"], note))

    # 参数落表：标定值必须可查、可回滚，不能只活在代码常量里
    con.execute("DELETE FROM persona_param")
    params = [
        ("ratio_bands", RATIO := [{"min": t, "band": b} for t, b in bands.RATIO_BANDS],
         "E1 观众/展商比分档（v2 四分位 + 绝对下限 %.1f）" % bands.RATIO_ABS_FLOOR),
        ("ratio_calibration", bands.RATIO_CALIBRATION, "分位标定的样本与版本"),
        ("visit_to_person", {"value": bands.VISIT_TO_PERSON}, "人次→人数折算系数"),
        ("deadline_bands", [{"min": t, "band": b} for t, b in bands.DEADLINE_BANDS], "E4 截止日档位"),
        ("start_window_bands", [{"min": t, "band": b} for t, b in bands.START_WINDOW_BANDS],
         "E4 按距开展天数分档"),
        ("hard_stop_days", {"value": bands.HARD_STOP_DAYS}, "E4 唯一门限：≤N 天"),
        ("role_hit", {"low": bands.ROLE_HIT_LOW, "mid": bands.ROLE_HIT_MID,
                      "high": bands.ROLE_HIT_HIGH}, "E1 角色命中率三档（人工假设，未标定）"),
        ("e2_status", bands.E2_STATUS, "E2 竞争密度：暂停使用"),
    ]
    for k, v, note in params:
        con.execute("INSERT INTO persona_param (key, version, value_json, note, created_at)"
                    " VALUES (?,?,?,?,?)", (k, 2, json.dumps(v, ensure_ascii=False), note, now))
    con.commit()

    print("参数版本 %s ｜ 算了 %d 个展" % (PARAMS_VERSION, len(rows)))
    print("E1 比值分档：", dict(stat))
    print("E4 门限（会被否决的）：%d 个" % gate)
    for k in ("e1_mid", "ratio_band", "e4_band"):
        n = con.execute("SELECT COUNT(*) FROM expo_persona WHERE %s IS NOT NULL" % k).fetchone()[0]
        print("  %-12s 有值 %d" % (k, n))
    print("\n→ expo_persona %d 行｜persona_param %d 行" % (
        con.execute("SELECT COUNT(*) FROM expo_persona").fetchone()[0],
        con.execute("SELECT COUNT(*) FROM persona_param").fetchone()[0]))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
