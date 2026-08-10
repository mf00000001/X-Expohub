"""完整登录链路测试"""
import requests, json

BASE = "http://127.0.0.1:3000"

print("=== 1. 登录 ===")
r = requests.post(f"{BASE}/auth/login", json={"username":"test","password":"123456"})
print(f"HTTP {r.status_code}")
d = r.json()
print(f"code: {d.get('code')}, message: {d.get('message')}")

inner = d.get("data", {})
token = inner.get("access_token", "")
print(f"token: {token[:30]}...")

print("\n=== 2. 获取个人信息 ===")
r2 = requests.get(f"{BASE}/auth/profile", headers={"Authorization": f"Bearer {token}"})
d2 = r2.json()
print(f"HTTP {r2.status_code}, code: {d2.get('code')}")
print(f"username: {d2.get('data',{}).get('username')}")
print(f"role: {d2.get('data',{}).get('role')}")

print("\n=== 3. 验证前端解包 ===")
print(f"authApi.login 返回: r.data.data = {json.dumps(inner, ensure_ascii=False)[:80]}...")
print(f"store.login 取: res.access_token = {inner.get('access_token','')[:30]}...")
print(f"结果: {'✅ 登录成功' if token else '❌ 失败'}")
