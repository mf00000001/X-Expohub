#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""demo_exhibitions.py — 生成「近期即将举办」与「历史」展会的演示数据 + 展商展位关联

背景
====
真实数据接入（scripts/realdata/）之后，业务库里只剩 4 个展会骨架、30 个展位，
且展位还挂在旧的合成展商账号上。本脚本：

1. 新建 5 场「近期即将举办」的展会（2026-10 ~ 2027-04），并为其中 2 场已存在的
   骨架展会补展位；
2. 补齐 / 重建 3 场「历史展会」的展位（含 2026-09 已结束的 AI 交流会）；
3. 用真实中标供应商（users.source LIKE 'realdata%'，id>=10001）按行业主题
   填充展位 —— 每场展会把「参展展商」按 booths.exhibitor_id 关联出来，
   供「历史展会 → 查看展商都有谁」功能使用。

约定
====
- 幂等：以展会标题为键，已存在则复用（不覆盖既有日期/简介/主办方），只重建展位；
  反复执行结果一致（随机数用固定种子）。
- 安全：运行前自动备份业务库到 expohub.db.bak-before-exhibitions-<时间戳>；
  写入包在单个事务里；只动受管标题对应的数据，其余展会（含人工条目）一律不碰。

用法
====
    python scripts/demo_exhibitions.py                # 默认 expohub-backend/expohub.db
    python scripts/demo_exhibitions.py --db <path>    # 指定库
"""
from __future__ import annotations

import argparse
import datetime as dt
import random
import shutil
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO / "expohub-backend" / "expohub.db"

# ---------------------------------------------------------------- 展会定义
# theme: 参与供应商的行业领域优先池；target/vacant: 占用/待预订展位数
UPCOMING = [
    dict(
        title="2026国际智能制造与工业互联网交流会",
        start="2026-10-20T09:00:00+08:00", end="2026-10-23T18:00:00+08:00",
        venue_id=23, organizer_id=3, organizer_name="中国国际进口博览局",
        theme=["机械", "AI/科技"], target=34, vacant=6,
        hot_score=1500, is_featured=1, visitor_count=18200,
        hall_a="A馆·智能制造展区", hall_b="B馆·工业互联展区",
        desc="聚焦智能制造装备、工业互联网平台与柔性产线集成，汇聚全国中标供应商，"
             "覆盖数控机床、工业机器人、检测仪器与工业软件全产业链。",
        title_en="2026 International Intelligent Manufacturing & Industrial Internet Expo",
        desc_en="Intelligent manufacturing equipment, industrial internet platforms and flexible production lines, powered by nationwide award-winning suppliers.",
    ),
    dict(
        title="2026全球新能源与碳中和产业交流会",
        start="2026-11-10T09:00:00+08:00", end="2026-11-13T18:00:00+08:00",
        venue_id=4, organizer_id=4, organizer_name="深圳会展中心管理有限公司",
        theme=["能源", "建材", "化工产品", "机械"], target=30, vacant=6,
        hot_score=1280, is_featured=1, visitor_count=16400,
        hall_a="A馆·新能源展区", hall_b="B馆·绿色建材展区",
        desc="围绕光伏、储能、碳中和与绿色建材的中标供应商交流会展，"
             "展示新能源装备、节能建材与低碳解决方案。",
        title_en="2026 Global New Energy & Carbon Neutrality Expo",
        desc_en="PV, energy storage, carbon neutrality and green building materials from award-winning suppliers.",
    ),
    dict(
        title="2026全球智慧医疗与健康产业交流会",
        start="2026-12-01T09:00:00+08:00", end="2026-12-04T18:00:00+08:00",
        venue_id=2, organizer_id=3, organizer_name="中国国际进口博览局",
        theme=["医药及医疗保健"], target=28, vacant=6,
        hot_score=1050, is_featured=0, visitor_count=9800,
        hall_a="A馆·医疗设备展区", hall_b="B馆·康复健康展区",
        desc="医疗设备、体外诊断、康复器械与数字医疗中标供应商专业会展，"
             "覆盖影像、检验、手术与康复全场景。",
        title_en="2026 Global Smart Healthcare Expo",
        desc_en="Medical devices, IVD, rehabilitation equipment and digital healthcare from award-winning suppliers.",
    ),
    dict(
        title="2026全球消费电子与智能生活交流会",
        start="2026-12-18T09:00:00+08:00", end="2026-12-21T18:00:00+08:00",
        venue_id=1, organizer_id=2, organizer_name="中国对外贸易中心",
        theme=["电子及家电", "AI/科技"], target=30, vacant=6,
        hot_score=1320, is_featured=1, visitor_count=14200,
        hall_a="A馆·消费电子展区", hall_b="B馆·智能家居展区",
        desc="消费电子、智能家居与人工智能终端展区，聚合电子信息类中标供应商的最新产品。",
        title_en="2026 Global Consumer Electronics & Smart Living Expo",
        desc_en="Consumer electronics, smart home and AI terminals from award-winning suppliers.",
    ),
    dict(
        title="2027全球AI与数字经济交流会",
        start="2027-04-08T09:00:00+08:00", end="2027-04-11T18:00:00+08:00",
        venue_id=5, organizer_id=3, organizer_name="中国国际进口博览局",
        theme=["AI/科技", "综合服务"], target=32, vacant=6,
        hot_score=880, is_featured=0, visitor_count=7600,
        hall_a="A馆·人工智能展区", hall_b="B馆·数字服务展区",
        desc="人工智能、大数据与数字经济服务展区，覆盖算力、算法、行业大模型与数字服务。",
        title_en="2027 Global AI & Digital Economy Expo",
        desc_en="AI, big data and digital economy services — compute, algorithms and industry LLMs.",
    ),
]

PAST = [
    dict(
        title="2026全球人工智能产业交流会",
        start="2026-09-15T09:00:00+08:00", end="2026-09-18T18:00:00+08:00",
        venue_id=5, organizer_id=2, organizer_name="中国对外贸易中心",
        theme=["AI/科技", "电子及家电", "机械"], target=32, vacant=0,
        hot_score=960, is_featured=0, visitor_count=12600,
        hall_a="A馆·人工智能展区", hall_b="B馆·智能装备展区",
        desc="人工智能与智能装备主题的往届交流会，展商名录保留供回顾查询。",
        title_en="2026 Global AI Industry Expo",
        desc_en="Past edition on AI and intelligent equipment; exhibitor directory kept for review.",
    ),
    dict(
        title="2025全球医疗器械与康复健康交流会",
        start="2025-11-12T09:00:00+08:00", end="2025-11-15T18:00:00+08:00",
        venue_id=16, organizer_id=2, organizer_name="中国对外贸易中心",
        theme=["医药及医疗保健"], target=26, vacant=0,
        hot_score=420, is_featured=0, visitor_count=11800,
        hall_a="A馆·医疗器械展区", hall_b="B馆·康复设备展区",
        desc="往届医疗器械与康复健康交流会，展商名录保留供回顾查询。",
        title_en="2025 Global Medical Devices & Rehabilitation Expo",
        desc_en="Past edition on medical devices and rehabilitation; exhibitor directory kept for review.",
    ),
    dict(
        title="2026中国国际食品加工与消费品交流会",
        start="2026-03-18T09:00:00+08:00", end="2026-03-21T18:00:00+08:00",
        venue_id=7, organizer_id=2, organizer_name="中国对外贸易中心",
        theme=["食品", "办公箱包及休闲用品", "礼品"], target=28, vacant=0,
        hot_score=560, is_featured=0, visitor_count=13500,
        hall_a="A馆·食品加工展区", hall_b="B馆·消费品展区",
        desc="往届食品加工与消费品交流会，展商名录保留供回顾查询。",
        title_en="2026 China International Food Processing & Consumer Goods Expo",
        desc_en="Past edition on food processing and consumer goods; exhibitor directory kept for review.",
    ),
]

MANAGED_TITLES = [s["title"] for s in UPCOMING + PAST]
SIZE_PRICE = {"6x6m": 12000.0, "9x6m": 22000.0, "9x9m": 28000.0}
SIZE_WEIGHTS = ["6x6m", "6x6m", "6x6m", "9x6m", "9x6m", "9x9m"]
DESC_OCCUPIED = [
    "主通道双面开放展位", "特装设计位，三面开放", "标准展位，临近论坛区",
    "展区核心位置，人流密集", "标准展位，含基础搭建",
]


def _q(db: sqlite3.Connection, sql: str, args=()):
    return db.execute(sql, args).fetchall()


def load_suppliers(db: sqlite3.Connection):
    """真实中标供应商池（id>=10001）。"""
    rows = _q(
        db,
        """
        SELECT u.id, u.username, u.company, u.industry_domain, u.region,
               COALESCE(m.membership_tier, 'free') AS tier
        FROM users u
        LEFT JOIN micro_booths m ON m.exhibitor_id = u.id
        WHERE u.role = 'exhibitor' AND u.id >= 10001 AND u.source IS NOT NULL
        """,
    )
    suppliers = []
    for uid, uname, company, industry, region, tier in rows:
        suppliers.append(
            dict(id=uid, username=uname, company=company or uname,
                 industry=industry or "综合服务", region=region or "", tier=tier)
        )
    return suppliers


def pick_suppliers(suppliers, spec, rng: random.Random):
    """按主题优先、不足则用其余供应商补足（确定性抽样）。"""
    target = spec["target"]
    themed = [s for s in suppliers if s["industry"] in spec["theme"]]
    others = [s for s in suppliers if s["industry"] not in spec["theme"]]
    rng.shuffle(themed)
    rng.shuffle(others)
    pool = themed + others
    # 展商不重复
    seen, picked = set(), []
    for s in pool:
        if s["id"] in seen:
            continue
        seen.add(s["id"])
        picked.append(s)
        if len(picked) >= target:
            break
    return picked


def build_booths(spec, picked, rng: random.Random, base_ts: dt.datetime):
    """生成展位行：(exhibitor_id, booth_number, exhibitor_name, company_name,
    size, location_area, price, description, status, created_at, updated_at)"""
    rows = []
    total = len(picked) + spec["vacant"]
    occupied = len(picked)
    for i in range(total):
        idx = i + 1
        prefix = "A" if idx <= 20 else "B"
        booth_number = f"{prefix}-{idx:03d}"
        hall = spec["hall_a"] if prefix == "A" else spec["hall_b"]
        size = rng.choice(SIZE_WEIGHTS)
        price = SIZE_PRICE[size] + float((idx % 3) * 500)
        ts = (base_ts + dt.timedelta(minutes=idx * 7)).strftime("%Y-%m-%d %H:%M:%S")
        if i < occupied:
            s = picked[i]
            rows.append((
                s["id"], booth_number, s["company"], s["company"],
                size, hall, price, rng.choice(DESC_OCCUPIED), "occupied", ts, ts,
            ))
        else:
            rows.append((
                None, booth_number, None, None,
                size, hall, price, "待预订", "available", ts, ts,
            ))
    return rows


def upsert_exhibition(db: sqlite3.Connection, spec: dict, is_past: bool) -> tuple[int, bool]:
    """返回 (exhibition_id, created)。已存在则只做轻量补齐，不覆盖人工字段。"""
    row = db.execute("SELECT id FROM exhibitions WHERE title = ?", (spec["title"],)).fetchone()
    if row:
        eid = row[0]
        # 补空字段 + 发布状态；简介同步为与真实展商数据一致的版本
        # （旧骨架简介里"华为/百度/西门子等已确认参展"与展商名录矛盾）
        db.execute(
            """
            UPDATE exhibitions
            SET status = ?, hot_score = COALESCE(NULLIF(hot_score, 0), ?),
                visitor_count = COALESCE(NULLIF(visitor_count, 0), ?),
                is_featured = COALESCE(NULLIF(is_featured, 0), ?),
                description = COALESCE(?, description),
                title_en = COALESCE(title_en, ?),
                description_en = COALESCE(description_en, ?)
            WHERE id = ?
            """,
            (spec.get("status", "published"), spec["hot_score"], spec["visitor_count"],
             spec["is_featured"], spec.get("desc"), spec.get("title_en"),
             spec.get("desc_en"), eid),
        )
        return eid, False

    now = dt.datetime.now()
    created = (now - dt.timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S")
    # 与既有骨架保持一致的 location 文案：展馆名（地址）
    venue = db.execute("SELECT name, address FROM venues WHERE id = ?", (spec["venue_id"],)).fetchone()
    location = f"{venue[0]}（{venue[1]}）" if venue else None
    cur = db.execute(
        """
        INSERT INTO exhibitions
            (title, description, title_en, description_en, cover_image,
             start_date, end_date, location, is_featured, hot_score, visitor_count,
             status, organizer_id, organizer_name, created_at, updated_at, venue_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            spec["title"], spec["desc"], spec.get("title_en"), spec.get("desc_en"), None,
            spec["start"], spec["end"], location, spec["is_featured"], spec["hot_score"],
            spec["visitor_count"], spec.get("status", "published"),
            spec["organizer_id"], spec["organizer_name"], created, created, spec["venue_id"],
        ),
    )
    return cur.lastrowid, True


def main():
    ap = argparse.ArgumentParser(description="生成近期/历史展会演示数据（幂等）")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"业务库不存在: {db_path}")

    # 1) 备份
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = db_path.with_name(f"{db_path.name}.bak-before-exhibitions-{stamp}")
    shutil.copy2(db_path, backup)
    print(f"[备份] {backup}")

    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout = 30000")
        suppliers = load_suppliers(conn)
        print(f"[供应商池] {len(suppliers)} 家真实中标供应商")
        if not suppliers:
            raise SystemExit("未找到真实供应商（users.source LIKE realdata%），中止")

        # 2) 展会 upstart
        summary = []
        managed_ids = []
        for is_past, specs in ((False, UPCOMING), (True, PAST)):
            for spec in specs:
                eid, created = upsert_exhibition(conn, spec, is_past)
                managed_ids.append(eid)
                rng = random.Random(f"expo-{spec['title']}")
                picked = pick_suppliers(suppliers, spec, rng)
                # 时间基准：历史展会 = 开幕前 40 天（展位预订期）；即将举办 = 现在前 30 天
                if is_past:
                    base = dt.datetime.fromisoformat(spec["start"].replace("+08:00", "")) - dt.timedelta(days=40)
                else:
                    base = dt.datetime.now() - dt.timedelta(days=30)
                rows = build_booths(spec, picked, rng, base)
                # 3) 重建展位
                conn.execute("DELETE FROM booths WHERE exhibition_id = ?", (eid,))
                conn.executemany(
                    """
                    INSERT INTO booths
                        (exhibition_id, exhibitor_id, booth_number, exhibitor_name, company_name,
                         size, location_area, price, description, status, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    [(eid, *r) for r in rows],
                )
                occupied = sum(1 for r in rows if r[8] == "occupied")
                summary.append(dict(eid=eid, created=created, title=spec["title"],
                                    occupied=occupied, available=len(rows) - occupied))
        conn.commit()

        print("\n[完成] 展会与展位：")
        for s in summary:
            tag = "新建" if s["created"] else "复用"
            print(f"  #{s['eid']:>3} {tag} 展商 {s['occupied']:>2} / 可预订 {s['available']:>2}  | {s['title']}")

        # 4) 查后核对
        rows = _q(
            conn,
            """
            SELECT e.id, e.title, COUNT(DISTINCT b.exhibitor_id)
            FROM exhibitions e LEFT JOIN booths b ON b.exhibition_id = e.id
            WHERE e.id IN ({})
            GROUP BY e.id ORDER BY e.id
            """.format(",".join("?" * len(managed_ids))),
            managed_ids,
        )
        print("\n[核对] 各展会参展展商数（去重）：")
        for r in rows:
            print(f"  #{r[0]:>3} {r[2]:>3} 家  {r[1]}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
