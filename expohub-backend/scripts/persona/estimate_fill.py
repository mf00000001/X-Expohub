"""
数据体检 + 估算回填

一次跑完两件事，因为它们必须同步：体检标出不可信的规模数，
估算再把不可信的排除在基准之外。分开跑就会出现"按脏基准算完才体检"的顺序错误。

## 体检（不改数值，只标记）

实测到的问题：

| 现象 | 例子 | 判定 |
|---|---|---|
| 面积 > 50 万㎡ | 东莞名家具展 100 万㎡（广东现代国际展览中心室内约 13 万） | 超单馆容量 |
| 观众密度 > 2500 人/千㎡ | 北京新质汽车展 128 万观众 / 38 万㎡ = 3368 | 人次未折算或面积错 |
| 观众/展商比 > 1000 | 同上，1280000/1000 = 1280 | 分子分母不同源 |

**只标 `data_quality='suspect'`，不改数**。原因：这些值原样留在库里，
下游能看见"这条有问题"；如果直接改，就变成"我们悄悄改了一个我们不确定的数字"，
比脏数据更难追责。要改得走人工，改完 `data_quality='ok'` 并在 note 里写依据。

## 估算（写 expo_estimate，不碰 expo）

`expo` 表里的数**永远**是采到的，`expo_estimate` 里**永远**是算的。
读的时候由调用方显式选择。这条是结构性的，不靠字段标记约定。

估算前会把 suspect 条目从"实测集合"里剔除——它们不进基准。
否则东莞那个 100 万㎡ 会把全样本密度的中位数往下拽，
然后所有基于密度的估算一起偏。

## 用法

    python scripts/persona/estimate_fill.py --dry-run    # 只看报告
    python scripts/persona/estimate_fill.py              # 写库
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import delete, select  # noqa: E402

from app.modules.persona.db import PersonaSessionLocal  # noqa: E402
from app.modules.persona.estimate import (  # noqa: E402
    AREA_MIN_USABLE,
    AREA_SUSPECT_CEILING,
    build_benchmark,
    estimate_all,
)
from app.modules.persona.models import Expo, ExpoEstimate  # noqa: E402

# 体检阈值。每条都能指向一个具体的真实案例，不是拍的。
VDENS_SUSPECT = 2500.0     # 人/千㎡；北京新质汽车展 3368
RATIO_SUSPECT = 1000.0     # 人/家；同一条
AREA_MIN_SUSPECT = AREA_MIN_USABLE


def diagnose(expo: Expo) -> str | None:
    """返回问题描述；没问题返回 None。"""
    issues: list[str] = []
    area = expo.exhibit_area_sqm or 0
    exhib = expo.exhibitor_count or 0
    visitor = expo.visitor_count or 0

    if area > AREA_SUSPECT_CEILING:
        issues.append(
            f"展览面积 {area:,}㎡ 超出单体展馆容量上限（约 {AREA_SUSPECT_CEILING:,}㎡），"
            f"疑为总建筑面积或多馆累计面积"
        )
    elif 0 < area < AREA_MIN_SUSPECT:
        issues.append(f"展览面积仅 {area:,}㎡，疑为抓错页面（分论坛/单展区）")

    if area >= AREA_MIN_SUSPECT and visitor and not area > AREA_SUSPECT_CEILING:
        vdens = visitor * 1000 / area
        if vdens > VDENS_SUSPECT:
            issues.append(
                f"观众密度 {vdens:,.0f} 人/千㎡ 异常（正常 500~1000），"
                f"疑人次未折算或面积偏小"
            )

    if visitor and exhib and visitor / exhib > RATIO_SUSPECT:
        issues.append(f"观众/展商比 {visitor/exhib:,.0f} 异常，疑分子分母不同源")

    return "；".join(issues) if issues else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只报告，不写库")
    args = ap.parse_args()

    bench_version = f"v1-{date.today().isoformat()}"

    with PersonaSessionLocal() as db:
        expos = db.execute(
            select(Expo).where(Expo.data_status != "excluded").order_by(Expo.id)
        ).scalars().all()

        # ---------- 体检 ----------
        suspect: list[tuple[str, str]] = []
        for e in expos:
            issue = diagnose(e)
            if issue:
                suspect.append((e.slug, issue))
                if not args.dry_run:
                    e.data_quality = "suspect"
                    e.quality_note = issue
            elif not args.dry_run and e.data_quality is None:
                e.data_quality = "ok"

        suspect_slugs = {s for s, _ in suspect}

        # ---------- 估算 ----------
        rows = [
            {
                "id": e.id, "slug": e.slug, "category": e.primary_category,
                "city": e.city, "venue_name": e.venue_name,
                "visitor_count": e.visitor_count, "visitor_caliber": e.visitor_caliber,
                "exhibitor_count": e.exhibitor_count, "exhibitor_caliber": e.exhibitor_caliber,
                "exhibit_area_sqm": e.exhibit_area_sqm,
            }
            for e in expos
        ]
        # 体检标出的脏条目不进基准
        measured = [
            r for r in rows
            if r["slug"] not in suspect_slugs
            and r["visitor_count"] and r["exhibitor_count"] and r["exhibit_area_sqm"]
        ]
        est_map, bench = estimate_all(rows, measured)

        # ---------- 报告 ----------
        print(f"参与计算: {len(rows)} 个展（已排除 excluded 与 3 条重复）")
        print(f"基准: n={bench.n_samples} 密度={bench.density} 家/千㎡ "
              f"比值={bench.ratio} 人/家 观众密度={bench.vdens} 人/千㎡")
        print(f"  品类层 {len(bench.by_category)} 组 / 父组层 {len(bench.by_parent)} 组")
        for k, v in bench.by_parent.items():
            print(f"    {k}: n={v['n']} 密度={v['density']:.1f} 比值={v['ratio']:.0f}")

        print()
        print(f"=== 体检异常 {len(suspect)} 条（标记 suspect，不改数值）===")
        for slug, issue in suspect:
            print(f"  {slug[:22]:24s} {issue}")

        print()
        n_est = sum(len(v) for v in est_map.values())
        print(f"=== 估算 {len(est_map)} 个展 / {n_est} 个字段 ===")
        for field_name in ("visitor_count", "exhibitor_count", "exhibit_area_sqm"):
            filled = sum(1 for r in rows if r.get(field_name))
            added = sum(1 for v in est_map.values() if field_name in v)
            print(f"  {field_name:20s} 实测 {filled:2d} + 估算 {added:2d} "
                  f"= {filled + added:2d}/{len(rows)}  ({(filled+added)/len(rows)*100:.0f}%)")

        # 置信度分布 —— 只有一路证据的占多数是正常的，说明样本还不够肥，
        # 不说明算法有问题。要提升得靠继续采数，不是放宽判据。
        from collections import Counter
        conf = Counter(e.confidence for v in est_map.values() for e in v.values())
        print(f"  置信度: {dict(conf)}")

        print()
        print("=== 抽样 8 条（核对合理性）===")
        by_slug = {e.slug: e for e in expos}
        shown = 0
        for slug, d in est_map.items():
            if shown >= 8:
                break
            e = by_slug.get(slug)
            if not e:
                continue
            print(f"  {(e.name_cn or '')[:26]:28s} {e.city or '-':6s}")
            for f, est in d.items():
                label = {"visitor_count": "观众", "exhibitor_count": "展商", "exhibit_area_sqm": "面积"}[f]
                unit = "㎡" if f == "exhibit_area_sqm" else ""
                print(f"    {label}: ≈{est.value:,}{unit}  区间 {est.lo:,}~{est.hi:,}  [{est.confidence}]")
                for evi in est.evidence:
                    print(f"      · {evi.basis}")
            shown += 1

        if args.dry_run:
            db.rollback()
            print("\n[dry] 未写库")
            return 0

        # ---------- 落库 ----------
        db.execute(
            delete(ExpoEstimate).where(ExpoEstimate.bench_version == bench_version)
        )
        for e in expos:
            for field_name, est in est_map.get(e.slug, {}).items():
                db.add(ExpoEstimate(
                    expo_id=e.id,
                    field_key=field_name,
                    value=est.value,
                    lo=est.lo,
                    hi=est.hi,
                    confidence=est.confidence,
                    evidence_json=json.dumps(
                        [x.to_dict() for x in est.evidence], ensure_ascii=False
                    ),
                    note=est.note or None,
                    bench_version=bench_version,
                ))
        db.commit()

        # 复核：不靠 print 说成功，从库里读回来数
        n = db.execute(
            select(ExpoEstimate).where(ExpoEstimate.bench_version == bench_version)
        ).scalars().all()
        print(f"\n已写入 expo_estimate: {len(n)} 行（bench_version={bench_version}）")
        by_field: dict[str, int] = {}
        for x in n:
            by_field[x.field_key] = by_field.get(x.field_key, 0) + 1
        print(f"  按字段: {by_field}")
        assert len(n) == n_est, f"写入行数 {len(n)} 与预期 {n_est} 不符"
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
