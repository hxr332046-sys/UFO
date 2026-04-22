import json
from pathlib import Path

p = Path('dashboard/data/records/mitm_ufo_flows.jsonl')
lines = p.read_text(encoding='utf-8').splitlines()
keys = ['/icpsp-api/v4/pc/register/name/', 'checkEstablishName', 'loadCurrentLocationInfo']
rows = []
for s in lines:
    d = json.loads(s)
    u = d.get('url', '')
    if any(k in u for k in keys):
        rows.append(d)

for idx, d in enumerate(rows[:8], 1):
    u = d.get('url', '')
    print('=' * 90)
    print(f"{idx:02d} {d.get('method')} {u}")
    print(f"status={d.get('status_code')}")
    req = d.get('req_body') or ''
    resp = d.get('resp_body') or ''
    try:
        rb = json.loads(req) if req else {}
    except Exception:
        rb = {}
    try:
        rp = json.loads(resp) if resp else {}
    except Exception:
        rp = {}

    if isinstance(rb, dict):
        flow = rb.get('flowData') if isinstance(rb.get('flowData'), dict) else {}
        link = rb.get('linkData') if isinstance(rb.get('linkData'), dict) else {}
        brief = {}
        for k in ['name','namePre','nameMark','industry','industrySpecial','areaCode','distCode','entType','checkState']:
            if k in rb:
                brief[k] = rb.get(k)
        if flow:
            brief['req.flowData'] = flow
        if link:
            brief['req.linkData'] = link
        if rb.get('extraDto') is not None:
            brief['req.extraDto.keys'] = list((rb.get('extraDto') or {}).keys()) if isinstance(rb.get('extraDto'), dict) else type(rb.get('extraDto')).__name__
        print('REQ:', json.dumps(brief, ensure_ascii=False))

    if isinstance(rp, dict):
        data = rp.get('data') if isinstance(rp.get('data'), dict) else {}
        busi = data.get('busiData') if isinstance(data.get('busiData'), dict) else {}
        flow = busi.get('flowData') if isinstance(busi.get('flowData'), dict) else {}
        link = busi.get('linkData') if isinstance(busi.get('linkData'), dict) else {}
        brief = {'resp.code': rp.get('code'), 'resp.resultType': data.get('resultType')}
        if flow:
            brief['resp.flowData'] = flow
        if link:
            brief['resp.linkData'] = link
        if isinstance(busi.get('checkResult'), list):
            brief['resp.checkResult.count'] = len(busi.get('checkResult'))
            brief['resp.checkState'] = busi.get('checkState')
        print('RESP:', json.dumps(brief, ensure_ascii=False))
