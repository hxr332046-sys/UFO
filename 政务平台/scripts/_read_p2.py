import json
from pathlib import Path

p = Path(r'dashboard\data\records\phase2_establish_latest.json')
d = json.load(open(p, 'r', encoding='utf-8'))
print(f'Top keys: {list(d.keys())[:10]}')
print(f'Status: {d.get("status")}')
print(f'Next index: {d.get("next_index")}')

# Check steps
steps = d.get('steps', [])
print(f'Steps: {len(steps)}')
for s in steps[:3]:
    print(f'  Step keys: {list(s.keys())[:10]}')
    print(f'  Sample: index={s.get("index")} name={s.get("name")} ok={s.get("ok")}')

# Check context_state
cs = d.get('context_state', {})
print(f'\nContext state keys: {list(cs.keys())[:15]}')
snap = cs.get('phase2_driver_snapshot', {})
print(f'Snapshot keys: {list(snap.keys())[:15]}')
