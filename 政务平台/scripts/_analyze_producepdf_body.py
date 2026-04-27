"""Analyze the producePdf request body that was sent during step 23."""
import json
from pathlib import Path

p = Path(r'dashboard\data\records\phase2_establish_latest.json')
d = json.load(open(p, 'r', encoding='utf-8'))

steps = d.get('steps', [])
# Find step 13 (YbbSelect save)
for i, s in enumerate(steps):
    if 'YbbSelect' in s.get('name', '') and 'save' in s.get('name', '').lower():
        print(f'=== Step {i}: {s["name"]} ===')
        # Check sent_body_keys
        sbk = s.get('sent_body_keys', [])
        print(f'sent_body_keys: {sbk}')
        
        # Check diagnostics
        diag = s.get('diagnostics', {})
        print(f'diagnostics keys: {list(diag.keys())}')
        for k, v in diag.items():
            print(f'  {k}: {str(v)[:150]}')

# Also check the snapshot for last_save_flowData and last_save_linkData
cs = d.get('context_state', {})
snap = cs.get('phase2_driver_snapshot', {})
print(f'\n=== Snapshot ===')
lsfd = snap.get('last_save_flowData', {})
lsld = snap.get('last_save_linkData', {})
print(f'last_save_flowData keys: {list(lsfd.keys())}')
print(f'last_save_flowData: {json.dumps(lsfd, ensure_ascii=False)[:300]}')
print(f'last_save_linkData keys: {list(lsld.keys())}')
print(f'last_save_linkData: {json.dumps(lsld, ensure_ascii=False)[:300]}')

# Check YbbSelect specific data
ybb_bd = snap.get('YbbSelect_busiData', {})
print(f'\nYbbSelect_busiData keys: {list(ybb_bd.keys())[:15]}')
