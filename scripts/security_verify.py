"""安全修复回归验证脚本(角色权限矩阵)

运行: python scripts/security_verify.py
要求: 后端已启动于 http://localhost:8002, 工作目录为仓库根(expohub-backend 同级)

覆盖: 四角色登录 / 匿名接口 / 普通用户越权(展会/展品) / 管理员专属接口 / book 角色限制 / 报价接口鉴权 / banned refresh

2026-10-19：主办方(organizer)角色已取消，原「organizer 越权」用例改为「展商越权」，
原「pending 主办方」用例改为「展商不能审批展会/看后台统计」。
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
                 ("buyer_li", "buyer123"), ("visitor_chen", "visitor123")]:
        st, j = req("POST", "/api/auth/login", body={"username": u, "password": p})
        toks[u] = j["data"]["access_token"] if st == 200 else None
        check(f"login:{u}", st == 200, f"http={st}")

    # 2. 匿名访问报名列表(P0-1) -> 401/403
    st, _ = req("GET", "/api/admin/exhibitions/1/registrations")
    check("anon:registrations", st in (401, 403), f"http={st}")

    # 3. 展商改他人展品 -> 403（原 organizer 越权用例）
    st, j = req("GET", "/api/products?exhibitor_id=6")
    lst = j.get("data", {}).get("list") or j.get("data", {}).get("items") or []
    if lst:
        st, _ = req("PUT", f"/api/products/{lst[0]['id']}", token=toks["exhibitor_huawei"], body={"name": "hack"})
        check("exhibitor:edit-others-product", st == 403, f"http={st}")
    else:
        check("exhibitor:edit-others-product", False, "no product found")

    # 3b. 展会创建/发布只归平台管理员：展商 -> 403
    st, j = req("GET", "/api/exhibitions?page_size=50")
    exhs = j.get("data", {}).get("list") or j.get("data", {}).get("items") or []
    if exhs:
        st, _ = req("POST", f"/api/exhibitions/{exhs[0]['id']}/publish", token=toks["exhibitor_huawei"])
        check("exhibitor:publish-exhibition", st == 403, f"http={st}")
        st, _ = req("POST", f"/api/exhibitions/{exhs[0]['id']}/approve", token=toks["exhibitor_huawei"], body={"approved": True})
        check("exhibitor:approve-exhibition", st == 403, f"http={st}")
    else:
        check("exhibitor:publish-exhibition", False, "no exhibition found")

    # 4. 普通用户不能看后台统计；注册接口已拒绝 organizer 角色
    st, _ = req("GET", "/api/admin/stats", token=toks["exhibitor_huawei"])
    check("exhibitor:admin-stats", st == 403, f"http={st}")
    st, j = req("POST", "/api/auth/register", body={
        "username": f"org_{TS}", "email": f"org_{TS}@t.com", "password": "tmp123456",
        "role": "organizer", "company_name": "临时", "business_license": "https://x/l.jpg",
        "privacy_agreed": True})
    check("register:organizer-rejected", st in (400, 422), f"http={st}")
    porg = None

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
        "username": f"by_{TS}", "email": f"by_{TS}@t.com", "password": "tmp123456", "role": "buyer",
        "privacy_agreed": True})
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
    conn.execute("DELETE FROM users WHERE id=?", (bid2,))
    conn.commit()
    conn.close()

    print("RESULT:", "ALL PASS" if not fails else f"FAILED: {fails}")
    sys.exit(0 if not fails else 1)


if __name__ == "__main__":
    main()
