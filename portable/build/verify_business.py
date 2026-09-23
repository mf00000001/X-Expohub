"""业务链路验证：确认裁剪 jieba 之后，智能匹配仍然真的在工作。

关键点：textkit 在 jieba 不可用时会**静默降级**成二元组分词，功能不报错但精度下降。
所以这里不能只看接口返回 200，必须直接查 _JIEBA_OK 标志，证明确实加载了 jieba。
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

_ap = argparse.ArgumentParser(description='便携包业务链路验证（需服务已启动）')
_ap.add_argument('--pkg', required=True,
                 help='便携包目录（形如 ...\\ExpoHub-试用版）。端口从该包的 logs\\server.pid 读取')
_args = _ap.parse_args()

PKG = os.path.abspath(_args.pkg)
SERVER = os.path.join(PKG, 'server')
PIDFILE = os.path.join(PKG, 'logs', 'server.pid')

fails = []


def check(name, cond, detail=''):
    mark = 'PASS' if cond else 'FAIL'
    print(f'  [{mark}] {name}  {detail}')
    if not cond:
        fails.append(name)


# ---------------------------------------------------------------- 端口
port = None
with open(PIDFILE, encoding='ascii') as f:
    parts = f.read().strip().split()
    port = int(parts[1])
BASE = f'http://127.0.0.1:{port}'
print(f'服务端口: {port}\n')


def api(path, token=None, method='GET', body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')


# ---------------------------------------------------------------- 1. jieba 真的加载了吗
print('=== 1. jieba 加载状态（决定分词精度，不能静默降级）===')
sys.path.insert(0, SERVER)
os.chdir(SERVER)
try:
    from app.modules.matching import textkit
    check('textkit._JIEBA_OK 为真', textkit._JIEBA_OK is True,
          f'_JIEBA_OK={textkit._JIEBA_OK}')
    toks = textkit.tokenize('采购一批数控机床和工业机器人')
    check('分词产出多字词（非二元组降级）', any(len(t) > 2 for t in toks), f'tokens={toks}')
except Exception as exc:  # noqa: BLE001
    check('textkit 导入', False, f'{type(exc).__name__}: {exc}')

# ---------------------------------------------------------------- 2. 登录
print('\n=== 2. 演示账号登录 ===')
tokens = {}
for user, pwd in [('exhibitor_huawei', 'exh123'), ('buyer_li', 'buyer123'), ('admin', 'admin123')]:
    st, body = api('/api/auth/login', method='POST', body={'username': user, 'password': pwd})
    # 统一响应结构：{success, code, message, data:{access_token,...}}
    tok = (body.get('data') or {}).get('access_token') if isinstance(body, dict) else None
    ok = st == 200 and bool(tok)
    check(f'{user} 登录', ok, f'HTTP {st}')
    if ok:
        tokens[user] = tok

# ---------------------------------------------------------------- 3. 智能匹配（走 jieba）
print('\n=== 3. 智能匹配接口（真实走 jieba 分词链路）===')
if 'exhibitor_huawei' in tokens:
    st, body = api('/api/recommendations/for-exhibitor', token=tokens['exhibitor_huawei'])
    ok = st == 200 and isinstance(body, dict) and body.get('success')
    check('展商←采购需求 推荐', ok, f'HTTP {st}')
    if ok:
        data = body.get('data') or []
        pipe = body.get('pipeline') or {}
        check('返回匹配结果', len(data) > 0, f'{len(data)} 条')
        stages = pipe.get('stages') or []
        check('工作流阶段有产出（S0–S5）', len(stages) >= 3,
              f'{len(stages)} 个阶段: {[s.get("name") for s in stages]}')
        if data:
            top = data[0]
            check('匹配条目带分数与理由',
                  bool(top.get('match_score') is not None or top.get('score') is not None),
                  f"score={top.get('match_score') or top.get('score')} "
                  f"reasons={len(top.get('match_reasons') or top.get('reasons') or [])}")

if 'buyer_li' in tokens:
    st, body = api('/api/recommendations/for-buyer', token=tokens['buyer_li'])
    ok = st == 200 and isinstance(body, dict) and body.get('success')
    check('买家←展品 推荐', ok, f'HTTP {st}')
    if ok:
        check('返回展品结果', len(body.get('data') or []) > 0,
              f"{len(body.get('data') or [])} 条, mode={(body.get('pipeline') or {}).get('mode')}")

# ---------------------------------------------------------------- 4. 其它域抽查
print('\n=== 4. 其它业务域抽查 ===')
if 'admin' in tokens:
    for path, name in [('/api/exhibitions', '展会列表'),
                       ('/api/venues', '展馆'),
                       ('/api/categories', '品类'),
                       ('/api/notifications', '通知')]:
        st, body = api(path, token=tokens['admin'])
        ok = st == 200
        cnt = ''
        if ok and isinstance(body, dict):
            d = body.get('data')
            cnt = f'{(len(d) if isinstance(d, list) else len(d.get("list", [])) if isinstance(d, dict) else "?")} 条'
        check(name, ok, f'HTTP {st} {cnt}')

print('\n===== RESULT =====')
if fails:
    print(f'  {len(fails)} 项失败: {fails}')
    sys.exit(1)
print('  ALL PASSED')
sys.exit(0)
