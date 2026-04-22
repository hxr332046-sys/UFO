import json

with open('dashboard/data/records/mitm_ufo_flows.jsonl','r',encoding='utf-8') as f:
    lines = f.readlines()

# 提取关键4跳请求的完整信息
keywords = [
    'checkEstablishName',
    'loadCurrentLocationInfo',
    'operationBusinessDataInfo',
    'nameCheckRepeat'
]

results = {}
for line in lines:
    d = json.loads(line)
    url = d.get('url','')
    for kw in keywords:
        if kw in url and kw not in results:
            results[kw] = {
                'method': d.get('method'),
                'url': url,
                'status_code': d.get('status_code'),
                'req_headers': d.get('req_headers',{}),
                'req_body': d.get('req_body',''),
                'resp_body': d.get('resp_body','')[:500]
            }

# 保存提取结果
with open('dashboard/data/records/manual_replay_chain.json','w',encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f'Extracted {len(results)} key requests:')
for k,v in results.items():
    print(f'  {k}: {v["method"]} {v["url"][:80]} status={v["status_code"]}')
    print(f'    req_headers keys: {list(v["req_headers"].keys())}')
    print(f'    req_body len: {len(v["req_body"])}')
    print()
