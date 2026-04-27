import json
d = json.load(open(r'dashboard\data\records\phase2_establish_latest.json', 'r', encoding='utf-8'))
steps = d.get('steps', [])
print(f'{len(steps)} steps total')
for s in steps:
    idx = s.get('index', 0)
    if idx >= 22:
        name = s.get('name', '?')
        ok_val = s.get('ok')
        code = s.get('code', '')
        rt = s.get('result_type', '')
        msg = (s.get('message', '') or '')[:80]
        print(f'[{idx}] {name} ok={ok_val} code={code} rt={rt} msg={msg}')
        ext = s.get('extracted', {})
        for k, v in ext.items():
            print(f'  {k}: {str(v)[:100]}')
