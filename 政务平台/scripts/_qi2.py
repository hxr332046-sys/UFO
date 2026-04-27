import json
d = json.load(open(r'dashboard\data\records\smart_register__case_兴裕为.json', 'r', encoding='utf-8'))
print(f'Keys: {list(d.keys())[:10]}')
print(f'status: {d.get("final_status")}')
print(f'busiId: {d.get("phase1_busi_id")}')
print(f'establish_busiId: {d.get("establish_busi_id")}')

# Check phase2 steps
p2 = d.get('phase2_result') or {}
steps = p2.get('steps') or []
print(f'\nPhase 2 steps: {len(steps)}')
for s in steps:
    idx = s.get('index', 0)
    name = s.get('name', '?')
    ok_val = s.get('ok')
    code = s.get('code', '')
    rt = s.get('result_type', '')
    msg = (s.get('message', '') or '')[:60]
    print(f'  [{idx}] {name} ok={ok_val} code={code} rt={rt} msg={msg}')
