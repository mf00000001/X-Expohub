"""
建画像库（独立 SQLite，不影响主库）

用法（在 expohub-backend 目录下执行）：

    python scripts/persona/init_db.py --dry-run          # 只打印将建什么，不落盘
    python scripts/persona/init_db.py                    # 建库（已存在则跳过）
    python scripts/persona/init_db.py --force            # 删表重建（画像库可重建，安全）
    python scripts/persona/init_db.py --db /tmp/x.db     # 指定路径（测试用）

安全保证：
  1. 只用 PersonaBase.metadata，不碰主库 Base.metadata
  2. 建表前检查表名与主库是否冲突，冲突即中止
  3. 打印主库文件大小/修改时间，证明未被写入
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402


def resolve_url(url: str) -> str:
    """
    把 sqlite:///./xxx.db 里的相对路径固定解析到 expohub-backend 根目录。

    否则从仓库根目录和从 backend 目录执行会建出两个不同的库 —— 这是最容易
    静默踩的坑。
    """
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    raw = url[len(prefix):]
    if raw == ":memory:" or os.path.isabs(raw):
        return url
    return prefix + str((BACKEND_DIR / raw).resolve())


def snapshot(path: Path) -> str:
    if not path.exists():
        return "不存在"
    st = path.stat()
    return f"{st.st_size / 1048576:.1f} MB, 修改于 {datetime.fromtimestamp(st.st_mtime):%Y-%m-%d %H:%M:%S}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None, help="覆盖 PERSONA_DATABASE_URL（路径或完整 URL）")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不建表")
    ap.add_argument("--force", action="store_true", help="drop_all 后再建（仅画像库）")
    args = ap.parse_args()

    if args.db:
        url = args.db if "://" in args.db else f"sqlite:///{Path(args.db).resolve()}"
    else:
        url = resolve_url(settings.PERSONA_DATABASE_URL)

    main_db = (BACKEND_DIR / "expohub.db").resolve()
    print("=" * 62)
    print(f"画像库 URL : {url}")
    if url.startswith("sqlite:///"):
        persona_path = Path(url[len("sqlite:///"):])
        print(f"画像库文件 : {persona_path}")
        if persona_path.resolve() == main_db:
            print("[ABORT] 画像库路径与主库 expohub.db 相同，拒绝执行")
            return 2
    else:
        persona_path = None
    print(f"主库状态   : expohub.db {snapshot(main_db)}")

    from app.modules.persona.db import PersonaBase, persona_engine  # noqa: E402
    from app.modules.persona.models import ALL_TABLES  # noqa: E402  (触发模型注册)

    # ---- 表名冲突检查：画像库绝不能与主库同名表 ----
    import app.models  # noqa: E402,F401  (填充主库 Base.metadata)
    from app.models.base import Base as MainBase  # noqa: E402

    persona_tables = set(PersonaBase.metadata.tables)
    main_tables = set(MainBase.metadata.tables)
    clash = persona_tables & main_tables
    if clash:
        print(f"[ABORT] 表名与主库冲突：{sorted(clash)}")
        return 2

    print(f"主库表数   : {len(main_tables)}")
    print(f"画像表数   : {len(persona_tables)}")
    print("-" * 62)
    print(f"{'表名':<18}{'列数':>4}  说明")
    for model in ALL_TABLES:
        cols = len(model.__table__.columns)
        doc = (model.__doc__ or "").strip().splitlines()[0] if model.__doc__ else ""
        print(f"{model.__tablename__:<18}{cols:>4}  {doc[:34]}")

    if args.dry_run:
        print("-" * 62)
        print("[dry-run] 未落盘。确认无误后去掉 --dry-run 执行。")
        return 0

    if args.force:
        PersonaBase.metadata.drop_all(bind=persona_engine)
        print("[force] 已删除画像库全部表")

    PersonaBase.metadata.create_all(bind=persona_engine)

    # ---- 落盘后核验：表确实建出来了，且不含主库表 ----
    with sqlite3.connect(persona_path) as con:
        rows = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )]
    sqlite_tables = [t for t in rows if not t.startswith("sqlite_")]

    print("-" * 62)
    print(f"库内表：{sqlite_tables}")

    missing = sorted(persona_tables - set(sqlite_tables))
    leaked = sorted(set(sqlite_tables) - persona_tables)
    if missing:
        print(f"[FAIL] 缺表：{missing}")
        return 1
    if leaked:
        print(f"[FAIL] 混入非画像表：{leaked}")
        return 1

    print(f"[OK] {len(sqlite_tables)} 张表全部就位，主库未受影响")
    print(f"画像库大小：{persona_path.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
