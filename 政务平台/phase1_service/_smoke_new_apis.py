"""测试今天新增的 6 个 API。"""
import json
import urllib.request
import urllib.parse

BASE = 'http://127.0.0.1:8800'


def http(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode('utf-8') if body else b''
    headers = {'Content-Type': 'application/json'} if body is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='replace')
    except Exception as e:
        return 0, str(e)


print('=== 新增 API 冒烟测试 ===\n')

# 1. auth/token/refresh
print('[1] POST /api/auth/token/refresh')
code, r = http('POST', '/api/auth/token/refresh')
print(f'  HTTP {code}')
if isinstance(r, dict):
    print(f'  success={r.get("success")} reason={r.get("reason")}')
    if r.get('authorization'):
        print(f'  authorization={r["authorization"][:16]}...')
print()

# 2. auth/token/ensure
print('[2] POST /api/auth/token/ensure')
code, r = http('POST', '/api/auth/token/ensure')
print(f'  HTTP {code}')
if isinstance(r, dict):
    print(f'  success={r.get("success")} source={r.get("source")} reason={r.get("reason")}')
print()

# 3. matters/list
print('[3] GET /api/matters/list')
code, r = http('GET', '/api/matters/list?size=5')
print(f'  HTTP {code}')
if isinstance(r, dict):
    print(f'  success={r.get("success")} total={r.get("total")} reason={r.get("reason")}')
    for it in (r.get('items') or [])[:3]:
        print(f'    id={it.get("id")} busiType={it.get("busiType")} entName={it.get("entName")}')
print()

# 4. matters/detail
print('[4] GET /api/matters/detail?busi_id=2047122548757872642')
code, r = http('GET', '/api/matters/detail?busi_id=2047122548757872642')
print(f'  HTTP {code}')
if isinstance(r, dict):
    print(f'  success={r.get("success")} busi_id={r.get("busi_id")}')
    print(f'  entName={r.get("entName")} busiType={r.get("busiType")}')
    print(f'  currCompUrl={r.get("currCompUrl")} establish_status={r.get("establish_status")}')
print()

# 5. phase2/progress
print('[5] GET /api/phase2/progress?busi_id=2047122548757872642&name_id=2047094115971878913')
code, r = http('GET', '/api/phase2/progress?busi_id=2047122548757872642&name_id=2047094115971878913')
print(f'  HTTP {code}')
if isinstance(r, dict):
    print(f'  success={r.get("success")} currCompUrl={r.get("currCompUrl")} status={r.get("status")}')
    print(f'  busiCompComb={r.get("busiCompComb")}')
print()

# 6. auth/qr/start (不真扫，只验 API 能返 QR 码)
print('[6] POST /api/auth/qr/start (仅验证接口能生成 QR，不会真扫)')
code, r = http('POST', '/api/auth/qr/start?user_type=1')
print(f'  HTTP {code}')
if isinstance(r, dict):
    print(f'  success={r.get("success")} sid={r.get("sid")}')
    qr_b64 = r.get('qr_image_base64') or ''
    print(f'  qr_image_base64 len={len(qr_b64)}')
    if r.get('sid'):
        # 立即 status 一次，期望 pending=True
        print(f'[6.1] GET /api/auth/qr/status?sid={r["sid"]}')
        code2, r2 = http('GET', f'/api/auth/qr/status?sid={r["sid"]}')
        print(f'  HTTP {code2}')
        if isinstance(r2, dict):
            print(f'    success={r2.get("success")} scanned={r2.get("scanned")} pending={r2.get("pending")}')
print()

print('=== 冒烟结束 ===')
