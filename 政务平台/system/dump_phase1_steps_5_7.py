import json
from pathlib import Path

p = Path('dashboard/data/records/mitm_ufo_flows.jsonl')
out = Path('dashboard/data/records/phase1_steps_5_7_dump.json')
rows = []
for s in p.read_text(encoding='utf-8').splitlines():
    d = json.loads(s)
    u = d.get('url','')
    if '/icpsp-api/v4/pc/register/name/' in u or 'checkEstablishName' in u or 'loadCurrentLocationInfo' in u:
        rows.append(d)

picked = {}
for idx, d in enumerate(rows, 1):
    if idx in (5,6,7):
        picked[str(idx)] = {
            'url': d.get('url'),
            'method': d.get('method'),
            'req_body': d.get('req_body'),
            'resp_body': d.get('resp_body'),
            'req_headers': d.get('req_headers'),
        }

out.write_text(json.dumps(picked, ensure_ascii=False, indent=2), encoding='utf-8')
print(out)
