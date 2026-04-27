import json
from pathlib import Path

p = Path(r'dashboard\data\records\phase2_establish_latest.json')
d = json.load(open(p, 'r', encoding='utf-8'))

steps = d.get('steps', [])
for i, s in enumerate(steps):
    name = s.get('name', '?')
    ok = s.get('ok')
    code = s.get('code', '')
    rt = s.get('resultType', '')
    msg = (s.get('message', '') or '')[:80]
    print(f'[{i}] {name} ok={ok} code={code} rt={rt} msg={msg}')
    if 'ybb' in name.lower() or 'produce' in name.lower() or 'electronic' in name.lower() or 'submit' in name.lower():
        ext = s.get('extracted', {})
        for k, v in ext.items():
            print(f'  ext.{k}={str(v)[:120]}')
