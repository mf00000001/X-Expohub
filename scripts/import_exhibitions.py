"""展会清单导入器（读 CSV/JSON → 走平台批量导入接口）

为什么走接口而不是直接写库：
  1. 复用后端已有的「标题去重 + 逐行校验 + 日期格式/年份/先后校验」；
  2. 导入的展会自动归属「平台运营」（2026-10-19 起平台自营）；
  3. 导入默认 draft，人工复核后再发布，避免脏数据直接上首页。

CSV 列（UTF-8 with BOM，Excel 直接另存即可）：
    名称,开始日期,结束日期,地点,简介,封面图URL,状态
    - 名称/开始日期/结束日期/地点 必填
    - 日期支持 2027-03-18 或 2027-03-18T09:00:00（年份需 2000-2100，结束>=开始）
    - 状态可留空（默认 draft），可填 draft/published
    - 简介 <= 500 字；封面图URL 可留空

用法：
    # 1) 先预演（不发请求，只校验并打印将导入什么）
    python scripts/import_exhibitions.py --file 清单.csv --dry-run

    # 2) 真导入（需要管理员 token）
    python scripts/import_exhibitions.py --file 清单.csv \
        --api http://127.0.0.1:8002 --token <admin_access_token> --status draft

    # 也支持 JSON：[{"名称": "...", "开始日期": "..."}] 或英文键 title/start_date/...
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime

# 中文列名 → 接口字段
COLUMN_MAP = {
    "名称": "title", "展会名称": "title", "title": "title",
    "开始日期": "start_date", "start_date": "start_date",
    "结束日期": "end_date", "end_date": "end_date",
    "地点": "location", "展馆": "location", "城市": "location", "location": "location",
    "简介": "description", "description": "description",
    "封面图URL": "cover_image", "封面": "cover_image", "cover_image": "cover_image",
    "状态": "status", "status": "status",
}

REQUIRED = ("title", "start_date", "end_date", "location")
ALLOWED_STATUS = ("draft", "pending", "published", "registering", "live", "ended", "cancelled")


def normalize(row: dict) -> dict:
    out = {}
    for key, value in row.items():
        if key is None:
            continue
        field = COLUMN_MAP.get(str(key).strip()) or COLUMN_MAP.get(str(key).strip().lower())
        if not field:
            continue
        text = "" if value is None else str(value).strip()
        if text:
            out[field] = text
    return out


def load_rows(path: str) -> list[dict]:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        data = json.load(open(path, encoding="utf-8-sig"))
        if isinstance(data, dict):
            data = data.get("rows") or data.get("list") or []
        return [normalize(item) for item in data]
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return [normalize(row) for row in reader]


def validate(rows: list[dict], default_status: str) -> tuple[list[dict], list[str]]:
    good, errors = [], []
    for idx, row in enumerate(rows, start=1):
        missing = [f for f in REQUIRED if not row.get(f)]
        if missing:
            errors.append(f"第{idx}行 缺字段：{','.join(missing)}")
            continue
        # 日期：交给后端校验，这里只做一眼可见的格式提示
        for field in ("start_date", "end_date"):
            value = row[field]
            if len(value) < 8:
                errors.append(f"第{idx}行 {field} 太短：{value}")
                break
        status = row.get("status") or default_status
        if status not in ALLOWED_STATUS:
            errors.append(f"第{idx}行 非法状态：{status}")
            continue
        # 模板里的示例行：自动跳过，避免误导入
        if any(k in row["title"] for k in ("示例", "请删除")):
            errors.append(f"第{idx}行 是模板示例行，已跳过：{row['title']}")
            continue
        payload = {
            "title": row["title"],
            "start_date": row["start_date"],
            "end_date": row["end_date"],
            "location": row["location"],
            "status": status,
            "description": row.get("description"),
            "cover_image": row.get("cover_image"),
        }
        good.append(payload)
    return good, errors


def push(api: str, token: str, rows: list[dict]) -> int:
    body = json.dumps({"rows": rows}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{api.rstrip('/')}/api/platform/import/exhibitions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:400]
        print(f"[XX] 导入失败 HTTP {exc.code}: {detail}")
        return 1
    data = result.get("data", {})
    print(f"[OK] 导入完成：成功 {data.get('success_count')}/{data.get('total')}")
    for item in data.get("results", []):
        flag = "OK " if item.get("ok") else "FAIL"
        print(f"  [{flag}] 第{item.get('row')}行 {item.get('title')} — {item.get('reason')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="展会清单导入（CSV/JSON → 平台导入接口）")
    ap.add_argument("--file", required=True, help="清单文件（.csv 或 .json）")
    ap.add_argument("--api", default="http://127.0.0.1:8002")
    ap.add_argument("--token", help="管理员 access_token（非 dry-run 必填）")
    ap.add_argument("--status", default="draft", help="清单未指定状态时的默认值（默认 draft）")
    ap.add_argument("--dry-run", action="store_true", help="只校验与预演，不发请求")
    args = ap.parse_args()

    if not os.path.exists(args.file):
        print(f"[XX] 文件不存在：{args.file}")
        return 2

    rows = load_rows(args.file)
    if not rows:
        print("[XX] 清单为空（或表头没有被识别：请确认含『名称/开始日期/结束日期/地点』四列）")
        return 2

    good, errors = validate(rows, args.status)
    print(f"[..] 读取 {len(rows)} 行，校验通过 {len(good)} 行，问题 {len(errors)} 行")
    for err in errors:
        print("  [!!]", err)

    if args.dry_run:
        print("\n=== DRY-RUN：以下数据本会提交（前 5 条）===")
        for row in good[:5]:
            print("  -", row["title"], "|", row["start_date"], "→", row["end_date"], "|", row["location"], "|", row["status"])
        print(f"  ... 共 {len(good)} 条（未发请求）")
        return 0 if good else 1

    if not args.token:
        print("[XX] 需要 --token（管理员登录后的 access_token）")
        return 2
    if not good:
        print("[XX] 没有可导入的行")
        return 1
    return push(args.api, args.token, good)


if __name__ == "__main__":
    sys.exit(main())
