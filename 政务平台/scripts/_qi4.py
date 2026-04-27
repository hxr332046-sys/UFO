import json
d = json.load(open(r'dashboard\data\records\smart_register__case_兴裕为.json', 'r', encoding='utf-8'))
# Check log and checkpoint
log = d.get('log', [])
for entry in log:
    print(f'Phase: {entry.get("phase")} status={entry.get("status")} steps={len(entry.get("steps",[]))}')
    for s in entry.get('steps', []):
        idx = s.get('index', 0)
        name = s.get('name', '?')
        ok_val = s.get('ok')
        code = s.get('code', '')
        rt = s.get('result_type', '')
        print(f'  [{idx}] {name} ok={ok_val} code={code} rt={rt}')

# Check checkpoint
cp = d.get('checkpoint', {})
print(f'\nCheckpoint status: {cp.get("status")}')
print(f'Checkpoint next_index: {cp.get("next_index")}')
ctx_state = cp.get('context_state', {})
print(f'Context state keys: {list(ctx_state.keys())[:15]}')
print(f'  current_comp_url: {ctx_state.get("current_comp_url")}')
print(f'  current_status: {ctx_state.get("current_status")}')
print(f'  last_ok_step: {ctx_state.get("last_ok_step")}')
