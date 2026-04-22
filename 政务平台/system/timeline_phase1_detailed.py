import json
from pathlib import Path

p = Path('dashboard/data/records/mitm_ufo_flows.jsonl')
lines = p.read_text(encoding='utf-8').splitlines()
keys = ['/icpsp-api/v4/pc/register/name/', 'checkEstablishName', 'loadCurrentLocationInfo']
idx = 0
for s in lines:
    d = json.loads(s)
    u = d.get('url', '')
    if not any(k in u for k in keys):
        continue
    idx += 1
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
            brief['req.flowData.busiId'] = flow.get('busiId')
            brief['req.flowData.currCompUrl'] = flow.get('currCompUrl')
            brief['req.flowData.status'] = flow.get('status')
        if link:
            brief['req.linkData.compUrl'] = link.get('compUrl')
            brief['req.linkData.opeType'] = link.get('opeType')
            brief['req.linkData.compUrlPaths'] = link.get('compUrlPaths')
        print('REQ:', json.dumps(brief, ensure_ascii=False))

    if isinstance(rp, dict):
        data = rp.get('data') if isinstance(rp.get('data'), dict) else {}
        busi = data.get('busiData') if isinstance(data.get('busiData'), dict) else {}
        flow = busi.get('flowData') if isinstance(busi.get('flowData'), dict) else {}
        link = busi.get('linkData') if isinstance(busi.get('linkData'), dict) else {}
        brief = {'resp.code': rp.get('code'), 'resp.resultType': data.get('resultType')}
        if flow:
            brief['resp.flowData.busiId'] = flow.get('busiId')
            brief['resp.flowData.currCompUrl'] = flow.get('currCompUrl')
            brief['resp.flowData.status'] = flow.get('status')
            brief['resp.flowData.nameId'] = flow.get('nameId')
        if link:
            brief['resp.linkData.compUrl'] = link.get('compUrl')
            brief['resp.linkData.opeType'] = link.get('opeType')
            brief['resp.linkData.compUrlPaths'] = link.get('compUrlPaths')
        if isinstance(busi.get('checkResult'), list):
            brief['resp.checkResult.count'] = len(busi.get('checkResult'))
            brief['resp.checkState'] = busi.get('checkState')
        print('RESP:', json.dumps(brief, ensure_ascii=False))
