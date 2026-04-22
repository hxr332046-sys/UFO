import json
from pathlib import Path

raw = json.loads(Path('dashboard/data/records/phase1_steps_5_7_dump.json').read_text(encoding='utf-8'))
s = raw['7']['req_body']
try:
    obj = json.loads(s)
    print('parsed ok', list(obj.keys()))
except json.JSONDecodeError as e:
    print('msg=', e.msg)
    print('pos=', e.pos, 'lineno=', e.lineno, 'colno=', e.colno)
    start = max(0, e.pos - 200)
    end = min(len(s), e.pos + 400)
    print('snippet=')
    print(s[start:end])
