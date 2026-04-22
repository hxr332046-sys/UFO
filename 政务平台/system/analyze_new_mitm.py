import json

with open('dashboard/data/records/mitm_ufo_flows.jsonl','r',encoding='utf-8') as f:
    lines = f.readlines()

print(f'Total lines now: {len(lines)} (was 638, new: {len(lines)-638})')

# 分析新增部分
for line in lines[638:]:
    d = json.loads(line)
    url = d.get('url','')
    if any(k in url for k in ['checkEstablishName','loadCurrentLocationInfo','operationBusinessDataInfo','nameCheckRepeat','loadBusi']):
        print('\n===', d.get('method'), '===')
        print('URL:', url)
        print('STATUS:', d.get('status_code'))
        if d.get('req_body'):
            try:
                rb = json.loads(d['req_body'])
                print('REQ_BODY:', {k:v for k,v in rb.items() if k in ['entType','nameCode','distCode','name','spellType','checkState','areaCode','namePre','nameMark','organize']})
            except:
                print('REQ_BODY:', d['req_body'][:200])
        if d.get('resp_body'):
            try:
                resp = json.loads(d['resp_body'])
                print('RESP: code=', resp.get('code'), 'resultType=', resp.get('data',{}).get('resultType'))
            except:
                print('RESP_BODY:', d['resp_body'][:200])
