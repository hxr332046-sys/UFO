import json
from pathlib import Path

MITM_LOG = Path(__file__).resolve().parent.parent / "dashboard" / "data" / "records" / "mitm_ufo_flows.jsonl"

with open(MITM_LOG, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"MITM total lines: {len(lines)}")
print("=" * 70)

# 关键词顺序
keywords = [
    'checkEstablishName',
    'loadCurrentLocationInfo',
    'operationBusinessDataInfo',
    'nameCheckRepeat',
    'submitBusiness',
    'saveBusiness',
    'loadBusinessDataInfo',
    'loadBusinessInfoList',
    'getService',
    'getUserInfo',
    'checkToken',
    'cachePing',
]

# 提取所有关键请求
results = {}
for line in lines:
    d = json.loads(line)
    url = d.get('url', '')
    for kw in keywords:
        if kw in url:
            if kw not in results:
                results[kw] = []
            # 只保留200且有响应体的
            if d.get('status_code') == 200 and d.get('resp_body'):
                results[kw].append({
                    'url': url,
                    'method': d.get('method'),
                    'req_body': d.get('req_body', '')[:500],
                    'resp_body': d.get('resp_body', '')[:500],
                })

# 去重，只保留最新的一个（URL最长的通常是最新的，因为时间戳不同）
for kw in results:
    # 按URL长度排序，取最后一个
    results[kw] = sorted(results[kw], key=lambda x: len(x['url']))[-1] if results[kw] else None

print("\n=== Phase 1 关键请求链路 ===\n")
for i, kw in enumerate(keywords, 1):
    item = results.get(kw)
    if item:
        print(f"[{i}] {kw}")
        print(f"    URL: {item['url']}")
        if item['req_body']:
            print(f"    REQ: {item['req_body'][:200]}")
        if item['resp_body']:
            try:
                resp = json.loads(item['resp_body'])
                code = resp.get('code', 'N/A')
                print(f"    RESP code: {code}")
            except:
                print(f"    RESP: {item['resp_body'][:100]}")
        print()

# 保存完整提取
out = Path(__file__).resolve().parent.parent / "dashboard" / "data" / "records" / "phase1_full_chain.json"
with open(out, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"Saved to: {out}")
