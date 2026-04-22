import json
from pathlib import Path

MITM_LOG = Path(__file__).resolve().parent.parent / "dashboard" / "data" / "records" / "mitm_ufo_flows.jsonl"

# 提取完整的请求链
targets = [
    'checkEstablishName',
    'loadCurrentLocationInfo', 
    'name/component/NameCheckInfo/operationBusinessDataInfo',
    'nameCheckRepeat',
    'name/component/NameSupplement/operationBusinessDataInfo',
    'name/component/NameShareholder/operationBusinessDataInfo',
    'name/component/NameSuccess/loadBusinessDataInfo',
    'name/submit',
]

results = {}
with open(MITM_LOG, 'r', encoding='utf-8') as f:
    for line in f:
        d = json.loads(line)
        url = d.get('url', '')
        for target in targets:
            if target in url:
                # 保存最新的（如果有多个）
                key = target.split('/')[-1]  # 取最后部分作为key
                results[key] = {
                    'url': url,
                    'method': d.get('method'),
                    'req_body': d.get('req_body', ''),
                    'resp_body': d.get('resp_body', ''),
                    'req_headers': d.get('req_headers', {}),
                }

# 保存完整提取
out = Path(__file__).resolve().parent.parent / "dashboard" / "data" / "records" / "phase1_submit_chain_full.json"
with open(out, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("Extracted requests:\n")
for k, v in results.items():
    print(f"[{k}]")
    print(f"  URL: {v['url'][:100]}")
    print(f"  Method: {v['method']}")
    if v['req_body']:
        try:
            body = json.loads(v['req_body'])
            print(f"  Body keys: {list(body.keys())}")
        except:
            print(f"  Body: {v['req_body'][:100]}")
    if v['resp_body']:
        try:
            resp = json.loads(v['resp_body'])
            code = resp.get('code', 'N/A')
            print(f"  Resp code: {code}")
        except:
            print(f"  Resp: {v['resp_body'][:100]}")
    print()

print(f"Saved to: {out}")
