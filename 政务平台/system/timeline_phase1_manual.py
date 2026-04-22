import json
from pathlib import Path

p = Path('dashboard/data/records/mitm_ufo_flows.jsonl')
lines = p.read_text(encoding='utf-8').splitlines()
keys = ['/icpsp-api/v4/pc/register/name/', 'checkEstablishName', 'loadCurrentLocationInfo']
idx = 0
for s in lines:
    d = json.loads(s)
    u = d.get('url', '')
    if any(k in u for k in keys):
        idx += 1
        print(f"{idx:02d} {d.get('method')} {u.split('9087')[-1][:140]} status={d.get('status_code')}")
