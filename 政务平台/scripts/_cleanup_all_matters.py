"""Cleanup: withdraw + delete matters that are in progress (state=101)"""
import sys; sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient
client = ICPSPClient()

# Get all matters
r = client.get_json('/icpsp-api/v4/pc/manager/mattermanager/matters/search', params={'pageNo':'1','pageSize':'50'})
items = (r.get('data') or {}).get('busiData') or []

for it in items:
    busi_id = it.get("id", "")
    name = it.get("entName", "")
    state = it.get("matterStateLangCode", "")
    name_id = it.get("nameId", "")
    print(f"\n=== {name} id={busi_id} state={state} nameId={name_id} ===")
    
    # Only handle state=100 or 101 (in progress / completed)
    if "100" in state or "101" in state:
        # Step 1: Withdraw (btnCode=104)
        print(f"  Withdrawing (btnCode=104)...")
        r1 = client.post_json("/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
                              {"busiId": busi_id, "btnCode": "104", "dealFlag": "before"})
        rt1 = (r1.get("data") or {}).get("resultType", "")
        msg1 = (r1.get("data") or {}).get("msg", "")[:80]
        print(f"    before: rt={rt1} msg={msg1}")
        if rt1 == "2":
            r2 = client.post_json("/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
                                  {"busiId": busi_id, "btnCode": "104", "dealFlag": "operate"})
            rt2 = (r2.get("data") or {}).get("resultType", "")
            msg2 = (r2.get("data") or {}).get("msg", "")[:80]
            print(f"    operate: rt={rt2} msg={msg2}")
        else:
            print(f"    Skip withdraw operate (rt={rt1})")
        
        # Step 2: Delete (btnCode=103)
        print(f"  Deleting (btnCode=103)...")
        r3 = client.post_json("/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
                              {"busiId": busi_id, "btnCode": "103", "dealFlag": "before"})
        rt3 = (r3.get("data") or {}).get("resultType", "")
        msg3 = (r3.get("data") or {}).get("msg", "")[:80]
        print(f"    before: rt={rt3} msg={msg3}")
        if rt3 == "2":
            r4 = client.post_json("/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
                                  {"busiId": busi_id, "btnCode": "103", "dealFlag": "operate"})
            rt4 = (r4.get("data") or {}).get("resultType", "")
            msg4 = (r4.get("data") or {}).get("msg", "")[:80]
            print(f"    operate: rt={rt4} msg={msg4}")
        else:
            print(f"    Skip delete operate (rt={rt3})")
    else:
        print(f"  State {state} - skip (only handle 100/101)")
