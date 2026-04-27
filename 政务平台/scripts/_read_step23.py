"""Read the full phase2 establish record to understand step 23 behavior."""
import json
from pathlib import Path

p = Path(r'dashboard\data\records\phase2_establish_latest.json')
d = json.load(open(p, 'r', encoding='utf-8'))

steps = d.get('steps', [])
for s in steps:
    idx = s.get('index', 0)
    if idx >= 22:
        print(f'\n=== [{idx}] {s.get("name","?")} ===')
        print(f'  ok={s.get("ok")} code={s.get("code")} rt={s.get("result_type")}')
        msg = s.get('message', '') or ''
        if msg:
            print(f'  message={msg[:200]}')
        ext = s.get('extracted', {})
        if ext:
            for k, v in ext.items():
                print(f'  ext.{k}={str(v)[:120]}')
        raw = s.get('raw_response', {})
        if raw:
            code = raw.get('code', '')
            data = raw.get('data', {})
            rt = data.get('resultType', '')
            msg2 = data.get('msg', '')
            print(f'  raw: code={code} rt={rt} msg={msg2[:100]}')
