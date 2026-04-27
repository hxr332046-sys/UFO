"""Explore name release / withdraw APIs for occupied names after deletion"""
import json, sys
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()

# Search for matters with status != 100 (completed/expired)
r = client.get_json("/icpsp-api/v4/pc/manager/mattermanager/matters/search",
                    params={"pageNo": "1", "pageSize": "50"})
items = (r.get("data") or {}).get("busiData") or []
print(f"Total matters: {len(items)}")

# Show all matters with their states
for it in items[:20]:
    mid = it.get("id", "")
    name = it.get("entName", "")
    state = it.get("matterStateLangCode", "")
    ent_type = it.get("entType", "")
    name_id = it.get("nameId", "")
    print(f"  {name} | id={mid} | nameId={name_id} | state={state} | entType={ent_type}")

# Try name release APIs
# 1. Check if there's a name/withdraw or name/cancel API
test_paths = [
    "/icpsp-api/v4/pc/register/name/withdraw",
    "/icpsp-api/v4/pc/register/name/cancel",
    "/icpsp-api/v4/pc/register/name/release",
    "/icpsp-api/v4/pc/register/name/revoke",
    "/icpsp-api/v4/pc/register/name/operate",
    "/icpsp-api/v4/pc/manager/namemanager/names/search",
    "/icpsp-api/v4/pc/manager/namemanager/names/operate",
]

for path in test_paths:
    try:
        if "search" in path:
            r = client.get_json(path, params={"pageNo": "1", "pageSize": "10"})
        else:
            r = client.post_json(path, {})
        code = r.get("code", "")
        msg = r.get("msg", "")[:80]
        print(f"\n  {path}")
        print(f"    code={code} msg={msg}")
        if r.get("data"):
            bd = r.get("data", {}).get("busiData")
            if bd:
                print(f"    busiData keys: {list(bd.keys()) if isinstance(bd, dict) else type(bd)}")
    except Exception as e:
        print(f"\n  {path}")
        print(f"    ERROR: {e}")
