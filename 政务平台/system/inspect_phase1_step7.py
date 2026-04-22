import json
from pathlib import Path

p = Path('dashboard/data/records/mitm_ufo_flows.jsonl')
rows = []
for s in p.read_text(encoding='utf-8').splitlines():
    d = json.loads(s)
    u = d.get('url','')
    if '/icpsp-api/v4/pc/register/name/' in u or 'checkEstablishName' in u or 'loadCurrentLocationInfo' in u:
        rows.append(d)

for idx, d in enumerate(rows, 1):
    if idx in (5,6,7,8):
        print('=' * 100)
        print('IDX', idx)
        print('URL', d.get('url'))
        rb = d.get('req_body')
        print('REQ_BODY_RAW_REPR', repr(rb))
        rp = d.get('resp_body')
        print('RESP_BODY_HEAD', (rp or '')[:500])
