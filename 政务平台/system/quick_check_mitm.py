import json

with open('dashboard/data/records/mitm_ufo_flows.jsonl','r',encoding='utf-8') as f:
    lines = f.readlines()

# 找最近30条中 register/guide/name/flow 相关的
for line in lines[-30:]:
    d = json.loads(line)
    url = d['url']
    if any(k in url for k in ['register','guide','name','flow']):
        print(d.get('method','GET'), url[:100], d.get('status_code'))
