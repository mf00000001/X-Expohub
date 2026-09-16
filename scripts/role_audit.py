"""全角色接口审计：5 角色 + 匿名 逐个调用全部 GET 路由，输出状态矩阵 CSV。

用法: cd expohub-backend && ../.venv/Scripts/python.exe ../scripts/role_audit.py [API_BASE]
默认打 http://127.0.0.1:8002（演示容器）。
"""
import csv
import json
import sqlite3
import sys
from pathlib import Path

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8002"
DB = Path(r"C:/Users/30288/AppData/Local/Temp/demo_container.db")
OUT = Path(r"C:/Users/30288/AppData/Local/Temp/role_audit.csv")

ROLES = {
    "admin": ("admin", "admin123"),
    "organizer": ("organizer_canton", "org123"),
    "exhibitor": ("exhibitor_siemens", "exh123"),
    "buyer": ("buyer_li", "buyer123"),
    "visitor": ("visitor_chen", "visitor123"),
}

# ---- 从演示库拿实体 id 供路径参数填充 ----
c = sqlite3.connect(str(DB))
def first(sql, default=1):
    try:
        row = c.execute(sql).fetchone()
        return row[0] if row else default
    except sqlite3.OperationalError:
        return default

PARAMS = {
    "exhibition_id": first("select id from exhibitions order by id limit 1"),
    "product_id": first("select id from products where status='published' order by id limit 1"),
    "procurement_id": first("select id from procurements where status='pending' order by id limit 1"),
    "mb_id": first("select id from micro_booths order by id limit 1"),
    "booth_id": first("select id from booths order by id limit 1"),
    "venue_id": first("select id from venues order by id limit 1"),
    "exhibitor_id": first("select id from users where username='exhibitor_siemens'"),
    "user_id": first("select id from users where username='buyer_li'"),
    "conversation_id": first("select id from conversations order by id limit 1", 0),
    "approval_id": first("select id from organizer_applications order by id limit 1", 0),
    "team_id": first("select id from teams order by id limit 1", 0),
    "ticket_no": first("select ticket_no from tickets order by id limit 1", "NONE"),
}
# 必备查询参数：按参数名从库里取/给默认值
REQUIRED_QUERY = {
    "ids": "1,2,3",
    "exhibition_id": str(PARAMS["exhibition_id"]),
    "q": "半导体",
    "keyword": "半导体",
    "user_id": str(PARAMS["user_id"]),
    "product_id": str(PARAMS["product_id"]),
    "item_id": str(PARAMS["product_id"]),
    "type": "exhibition",
}

spec = json.loads(httpx.get(f"{BASE}/openapi.json", timeout=10).text)
GETS = sorted(p for p, m in spec["paths"].items() if "get" in m)

client = httpx.Client(base_url=BASE, timeout=20)


def login(username: str, password: str):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    if r.status_code != 200:
        return None
    body = r.json()
    tok = (body.get("data") or {}).get("access_token") or body.get("access_token")
    return {"Authorization": f"Bearer {tok}"} if tok else None


HEADERS = {"anon": {}}
for role, (u, p) in ROLES.items():
    h = login(u, p)
    if h is None:
        print(f"[!] 登录失败: {role} {u}")
    HEADERS[role] = h or {}

rows = []
skipped = []
for path in GETS:
    # 路径参数替换
    p = path
    bad = False
    for name, val in PARAMS.items():
        token = "{" + name + "}"
        if token in p:
            if not val or val == 0 or val == "NONE":  # 库里没有该实体 → 无法构造请求
                bad = True
                break
            p = p.replace(token, str(val))
    if bad:
        skipped.append((path, "库中无对应实体(演示库为空表)"))
        continue
    # 剩余未解析参数
    import re
    left = re.findall(r"\{(\w+)\}", p)
    if left:
        skipped.append((path, f"未解析参数 {left}"))
        continue
    # 必需查询参数
    q = {}
    op = spec["paths"][path]["get"]
    for prm in op.get("parameters", []):
        if prm.get("required") and prm.get("in") == "query":
            if prm["name"] in REQUIRED_QUERY:
                q[prm["name"]] = REQUIRED_QUERY[prm["name"]]
            else:
                bad = True
    if bad:
        skipped.append((path, "必填查询参数未知"))
        continue
    row = {"route": p}
    for role, h in HEADERS.items():
        try:
            r = client.get(p, headers=h, params=q)
            row[role] = r.status_code
        except Exception as e:
            row[role] = f"ERR {type(e).__name__}"
    rows.append(row)

with OUT.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=["route"] + list(HEADERS))
    w.writeheader()
    w.writerows(rows)

print(f"共 {len(rows)} 条路由被调用，跳过 {len(skipped)} 条")
for s in skipped:
    print("  跳过:", s)

# ---- 摘要：按状态分组打印非 200 情况 ----
def col(role):
    return [(r["route"], r[role]) for r in rows if r[role] != 200]

for role in HEADERS:
    issues = col(role)
    print(f"\n=== {role}: {len(issues)} 条非 200 ===")
    for route, code in issues:
        print(f"  {code}  {route}")
print(f"\nCSV -> {OUT}")
