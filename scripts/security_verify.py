"""安全修复回归验证脚本(角色权限矩阵)

运行: python scripts/security_verify.py
要求: 后端已启动于 http://localhost:8002, 工作目录为仓库根(expohub-backend 同级)

覆盖: 四角色登录 / 匿名接口 / organizer 越权 / pending 主办方限制 / book 角色限制 / 报价接口鉴权 / banned refresh
"""
import json
import sqlite3
import sys
import time
import urllib.request
import os

BASE = "http://localhost:8002"
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "expohub-backend", "expohub.db")
TS = int(time.time())
fails = []


def req(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def check(name, cond, detail):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name} ({detail})")
    if not cond:
        fails.append(name)


def main():
    # 1. 四角色登录
    toks = {}
    for u, p in [("admin", "admin123"), ("exhibitor_huawei", "exh123"),
                 ("buyer_li", "buyer123"), ("organizer_canton", "org123")]:
        st, j = req("POST", "/api/auth/login", body={"username": u, "password": p})
        toks[u] = j["data"]["access_token"] if st == 200 else None
        check(f"login:{u}", st == 200, f"http={st}")

    # 2. 匿名访问报名列表(P0-1) -> 401/403
    st, _ = req("GET", "/api/admin/exhibitions/1/registrations")
    check("anon:registrations", st in (401, 403), f"http={st}")

    # 3. organizer 改他人展品(P0-2) -> 403
    st, j = req("GET", "/api/products?exhibitor_id=5")
    lst = j.get("data", {}).get("list") or j.get("data", {}).get("items") or []
    if lst:
        st, _ = req("PUT", f"/api/products/{lst[0]['id']}", token=toks["organizer_canton"], body={"name": "hack"})
        check("organizer:edit-others-product", st == 403, f"http={st}")
    else:
        check("organizer:edit-others-product", False, "no product found")

    # 4. pending 主办方(P0-2b) -> 403
    st, j = req("POST", "/api/auth/register", body={
        "username": f"org_{TS}", "email": f"org_{TS}@t.com", "password": "tmp123456",
        "role": "organizer", "company_name": "临时", "business_license": "https://x/l.jpg"})
    ptok = j["data"]["access_token"]
    porg = j["data"]["user"]["id"]
    st, _ = req("GET", "/api/admin/stats", token=ptok)
    check("pending-organizer:admin-stats", st == 403, f"http={st}")
    st, _ = req("POST", "/api/exhibitions/1/approve", token=ptok, body={"approved": True})
    check("pending-organizer:approve", st == 403, f"http={st}")

    # 5. buyer 预订展位(P1) -> 403; 匿名匹配(P1) -> 401
    st, j = req("GET", "/api/booths?status=available&page_size=5")
    bid = (j.get("data", {}).get("list") or j.get("data", {}).get("items") or [{}])[0].get("id")
    if bid:
        st, _ = req("POST", "/api/booths/book", token=toks["buyer_li"], body={"booth_id": bid})
        check("buyer:book-booth", st == 403, f"http={st}")
    else:
        check("buyer:book-booth", False, "no available booth")
    st, _ = req("GET", "/api/procurements/1/matches")
    check("anon:matches", st in (401, 403), f"http={st}")

    # 6. banned refresh(P1) -> 401
    st, j = req("POST", "/api/auth/register", body={
        "username": f"by_{TS}", "email": f"by_{TS}@t.com", "password": "tmp123456", "role": "buyer"})
    bid2 = j["data"]["user"]["id"]
    bref = j["data"]["refresh_token"]
    conn = sqlite3.connect(DB)
    conn.execute("UPDATE users SET status='banned' WHERE id=?", (bid2,))
    conn.commit()
    conn.close()
    st, _ = req("POST", "/api/auth/refresh", body={"refresh_token": bref})
    check("banned:refresh", st == 401, f"http={st}")

    # 清理临时用户
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM users WHERE id IN (?, ?)", (porg, bid2))
    conn.commit()
    conn.close()

    print("RESULT:", "ALL PASS" if not fails else f"FAILED: {fails}")
    sys.exit(0 if not fails else 1)


if __name__ == "__main__":
    main()
