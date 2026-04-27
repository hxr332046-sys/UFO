import json
from pathlib import Path

p = Path(r'dashboard\data\records\phase2_establish_latest.json')
d = json.load(open(p, 'r', encoding='utf-8'))
cs = d.get('context_state', {})
snap = cs.get('phase2_driver_snapshot', {})

lsld = snap.get('last_save_linkData', {})
print("=== last_save_linkData (FULL) ===")
print(json.dumps(lsld, ensure_ascii=False, indent=2))

# Also check YbbSelect_busiData.linkData
ybb_bd = snap.get('YbbSelect_busiData', {})
ybb_ld = ybb_bd.get('linkData', {})
print("\n=== YbbSelect_busiData.linkData ===")
print(json.dumps(ybb_ld, ensure_ascii=False, indent=2))

# Check producePdfVo
ybb_ppv = ybb_bd.get('producePdfVo', {})
print("\n=== YbbSelect producePdfVo ===")
print(json.dumps(ybb_ppv, ensure_ascii=False, indent=2))

# Check the full YbbSelect_busiData structure (top-level keys)
print(f"\n=== YbbSelect_busiData top keys ===")
for k in ybb_bd.keys():
    v = ybb_bd[k]
    if isinstance(v, dict):
        print(f"  {k}: dict({len(v)} keys)")
    elif isinstance(v, list):
        print(f"  {k}: list({len(v)} items)")
    else:
        print(f"  {k}: {type(v).__name__} = {str(v)[:80]}")
