"""测试第三批 3 个新 API：经营范围实时搜索 + sysParam + mitm 样本查询。"""
import json
import urllib.request

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


print('=== 第三批 API 冒烟 ===\n')

# 1. 经营范围实时搜索
print('[1] GET /api/phase1/scope/search?keyword=软件&industry_code=6513')
code, r = http('GET', '/api/phase1/scope/search?keyword=%E8%BD%AF%E4%BB%B6&industry_code=6513&limit=5')
print(f'  HTTP {code}')
if isinstance(r, dict):
    print(f'  success={r.get("success")} total={r.get("total")} reason={r.get("reason")}')
    for it in (r.get('items') or [])[:3]:
        if isinstance(it, dict):
            print(f'    id={it.get("id")} name={it.get("name")} stateCo={it.get("stateCo")}')
print()

# 2. sysParam 快照
print('[2] GET /api/system/sysparam/snapshot?keys=aesKey,numberEncryptPublicKey')
code, r = http('GET', '/api/system/sysparam/snapshot?keys=aesKey,numberEncryptPublicKey')
print(f'  HTTP {code}')
if isinstance(r, dict):
    print(f'  success={r.get("success")} total={r.get("total")} returned={r.get("returned")}')
    print(f'  snapshot_mtime={r.get("snapshot_mtime")}')
    data = r.get('data') or {}
    for k, v in data.items():
        s = str(v)
        print(f'    {k}: {s[:80]}' + ('...' if len(s) > 80 else ''))
print()

# 3. sysParam 单 key
print('[3] GET /api/system/sysparam/key/aesKey')
code, r = http('GET', '/api/system/sysparam/key/aesKey')
print(f'  HTTP {code}')
if isinstance(r, dict):
    print(f'  success={r.get("success")} key={r.get("key")} value={r.get("value")}')
print()

# 4. sysParam 刷新（调平台 API）
print('[4] POST /api/system/sysparam/refresh')
code, r = http('POST', '/api/system/sysparam/refresh')
print(f'  HTTP {code}')
if isinstance(r, dict):
    print(f'  success={r.get("success")} total={r.get("total")} previous_total={r.get("previous_total")}')
    print(f'  important_keys_changed={r.get("important_keys_changed")}')
    print(f'  has_aesKey={r.get("has_aesKey")} has_numberEncryptPublicKey={r.get("has_numberEncryptPublicKey")}')
print()

# 5. mitm 样本统计
print('[5] GET /api/debug/mitm/stats')
code, r = http('GET', '/api/debug/mitm/stats')
print(f'  HTTP {code}')
if isinstance(r, dict):
    print(f'  success={r.get("success")} total={r.get("total_records")} size_mb={r.get("size_mb")}')
    print(f'  methods={r.get("methods")}')
    print(f'  top_codes={r.get("top_codes")}')
    print(f'  top_apis (前 5):')
    for item in (r.get('top_apis') or [])[:5]:
        print(f'    {item.get("count"):4d}  {item.get("api")}')
print()

# 6. mitm 样本查询 - BasicInfo save
print('[6] GET /api/debug/mitm/latest?api_pattern=BasicInfo/operationBusinessDataInfo')
code, r = http('GET', '/api/debug/mitm/latest?api_pattern=BasicInfo%2FoperationBusinessDataInfo&only_success=true')
print(f'  HTTP {code}')
if isinstance(r, dict):
    print(f'  success={r.get("success")}')
    sample = r.get('sample') or {}
    if sample:
        print(f'  ts={sample.get("ts")} code={sample.get("code")} opeType={sample.get("opeType")}')
        req_body = sample.get('req_body')
        if isinstance(req_body, dict):
            print(f'  req_body.signInfo={req_body.get("signInfo")}')
            print(f'  req_body.name={req_body.get("name")}')
            print(f'  req_body.keys_count={len(req_body)}')
print()

print('=== 完成 ===')
