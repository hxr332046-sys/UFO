"""Check if matter still exists."""
import sys, json
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()

# Search matters
resp = client.get_json('/icpsp-api/v4/pc/manager/mattermanager/matters/search', params={'pageNo':'1','pageSize':'50'})
items = (resp.get('data') or {}).get('busiData') or []
print(f"Found {len(items)} matters:")
for it in items:
    mid = it.get("id", "")
    mname = it.get("entName", "")
    mstate = it.get("matterStateLangCode", "")
    mnameid = it.get("nameId", "")
    print(f"  {mname} id={mid} state={mstate} nameId={mnameid}")

# Check specific busiId
busi_id = "2048388847616139266"
print(f"\nChecking busiId {busi_id}...")
found = any(it.get("id") == busi_id for it in items)
print(f"  Found in matters list: {found}")
