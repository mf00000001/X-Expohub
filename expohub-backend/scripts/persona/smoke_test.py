"""
画像库冒烟测试（跑在临时库上，不污染 persona.db）

用法：
    python scripts/persona/smoke_test.py

验证四件事：
  1. bands 纯函数自检全部通过
  2. 一个展会能落库并算出 E1/E4
  3. 唯一约束能挡住重复观测（同一来源同一字段）
  4. 删展会时观测/名录级联删除
"""

from __future__ import annotations

import sys
import tempfile
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.modules.persona.bands import compute_all, self_check  # noqa: E402
from app.modules.persona.db import PersonaBase, enable_sqlite_fk  # noqa: E402
from app.modules.persona.models import (  # noqa: E402
    Expo,
    ExpoExhibitor,
    ExpoObservation,
    ExpoPersona,
)

FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("  [PASS] " if cond else "  [FAIL] ") + msg)
    if not cond:
        FAILS.append(msg)


def main() -> int:
    print("=" * 62)
    print("1) 纯函数自检")
    for f in self_check():
        FAILS.append(f)
        print(f"  [FAIL] {f}")
    if not FAILS:
        print("  [PASS] 全部档位/折算规则符合文档")

    tmp = Path(tempfile.mkdtemp()) / "persona_smoke.db"
    engine = create_engine(f"sqlite:///{tmp}", connect_args={"check_same_thread": False})
    enable_sqlite_fk(engine)
    PersonaBase.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    print("=" * 62)
    print(f"2) 落库与计算（临时库 {tmp.name}）")
    db = Session()
    try:
        expo = Expo(
            slug="smoke-2026-上海-家具",
            name_cn="冒烟测试家具展",
            city="上海",
            venue_name="国家会展中心",
            start_date="2026-09-01",
            end_date="2026-09-04",
            edition_no=28,
            biz_type="b2b",
            audience_access="trade_only",
            primary_category="家居装饰品",
            visitor_count=300000,          # 原文是"超 30 万人次"
            visitor_caliber="visit",       # 人次 → 应折算为 150000
            exhibitor_count=2000,
            exhibitor_caliber="company",
            booth_deadline="2026-06-30",
            has_listing=True,
            listing_completeness="partial",
            sample_group="core_head",
            data_status="pending_verify",
        )
        db.add(expo)
        db.commit()

        # 观众数两条来源：官网说 30 万人次，展后报告说 32 万人次 → 交叉验证用
        db.add_all([
            ExpoObservation(expo_id=expo.id, field_key="visitor_count",
                            raw_text="超 30 万人次参观", num_value=300000, unit="人次",
                            caliber="含公众开放日", source_url="https://example.com/",
                            source_type="official", confidence="mid",
                            fetched_at="2026-11-03T14:00:00+08:00"),
            ExpoObservation(expo_id=expo.id, field_key="visitor_count",
                            raw_text="320,000 人次", num_value=320000, unit="人次",
                            caliber="展后报告口径", source_url="https://example.com/report.pdf",
                            source_type="post_report", confidence="mid"),
            ExpoObservation(expo_id=expo.id, field_key="booth_price",
                            raw_text="标摊 12000 元/9㎡", num_value=12000, unit="元/9㎡",
                            source_url="https://example.com/price", source_type="official"),
        ])
        db.add_all([
            ExpoExhibitor(expo_id=expo.id, company_name="A 家具", booth_no="A-101", zone="1 号馆",
                          category_tag="家居装饰品"),
            ExpoExhibitor(expo_id=expo.id, company_name="B 家居", booth_no="A-102", zone="1 号馆",
                          category_tag="家居装饰品"),
        ])
        db.commit()

        r = compute_all(
            visitor_count=expo.visitor_count,
            exhibitor_count=expo.exhibitor_count,
            visitor_caliber=expo.visitor_caliber,
            deadline_iso=expo.booth_deadline,
            today=date(2026, 11, 3),
        )
        print(f"  折算后人数      : {r['visitor_count_normalized']}（原文 30 万人次）")
        print(f"  观众/展商比     : {r['visitor_exhibitor_ratio']} → {r['ratio_band']}")
        print(f"  E1 区间         : {r['e1_lo']} / {r['e1_mid']} / {r['e1_hi']} 人")
        print(f"  E4 档位         : {r['e4_band']}（剩余 {r['e4_days_left']} 天）")

        check(r["visitor_count_normalized"] == 150000, "人次按 ÷2 折算为 150000")
        check(r["visitor_exhibitor_ratio"] == 75.0, "观众/展商比 = 150000/2000 = 75.0")
        check(r["ratio_band"] == "ample", "比值 75 → ample（客源充裕）")
        check(r["e1_mid"] == 30000, "E1 中值 = 150000 × 0.20 = 30000")
        check(r["e4_band"] == "closed", "截止日 2026-06-30 已过 → closed")

        db.add(ExpoPersona(
            expo_id=expo.id, params_version="v1",
            visitor_exhibitor_ratio=r["visitor_exhibitor_ratio"],
            ratio_band=r["ratio_band"],
            e1_lo=r["e1_lo"], e1_mid=r["e1_mid"], e1_hi=r["e1_hi"],
            e1_confidence=r["e1_confidence"],
            e4_band=r["e4_band"], e4_days_left=r["e4_days_left"], e4_deadline=r["e4_deadline"],
        ))
        db.commit()

        persona = db.scalars(select(ExpoPersona).where(ExpoPersona.expo_id == expo.id)).one()
        check(persona.e1_mid == 30000, "计算结果可回读")

        print("=" * 62)
        print("3) 唯一约束")
        db.add(ExpoObservation(expo_id=expo.id, field_key="visitor_count",
                               raw_text="重复导入", num_value=1,
                               source_url="https://example.com/", source_type="official"))
        try:
            db.commit()
            check(False, "重复观测应被唯一约束拒绝")
        except IntegrityError:
            db.rollback()
            check(True, "同来源同字段重复观测被拒绝")

        print("=" * 62)
        print("4) 级联删除")
        n_obs = len(db.scalars(select(ExpoObservation)).all())
        n_exh = len(db.scalars(select(ExpoExhibitor)).all())
        db.delete(expo)
        db.commit()
        left_obs = len(db.scalars(select(ExpoObservation)).all())
        left_exh = len(db.scalars(select(ExpoExhibitor)).all())
        check(n_obs == 3 and left_obs == 0, f"观测 {n_obs} 条随展会删除（剩 {left_obs}）")
        check(n_exh == 2 and left_exh == 0, f"名录 {n_exh} 条随展会删除（剩 {left_exh}）")
    finally:
        db.close()
        engine.dispose()
        tmp.unlink(missing_ok=True)

    print("=" * 62)
    if FAILS:
        print(f"[FAILED] {len(FAILS)} 项未通过")
        return 1
    print("[ALL PASS] 画像库可用")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
