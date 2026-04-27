"""Test btnCode=104 (withdraw) on completed matters and check name release"""
import json, sys
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()

# Get matters with state 104 (completed/submitted)
r = client.get_json("/icpsp-api/v4/pc/manager/mattermanager/matters/search",
                    params={"pageNo": "1", "pageSize": "50"})
items = (r.get("data") or {}).get("busiData") or []

for it in items:
    busi_id = it.get("id", "")
    name = it.get("entName", "")
    state = it.get("matterStateLangCode", "")
    name_id = it.get("nameId", "")
    print(f"\n=== {name} id={busi_id} nameId={name_id} state={state} ===")
    
    # Test btnCode 104 (withdraw)
    r104 = client.post_json("/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
                            {"busiId": busi_id, "btnCode": "104", "dealFlag": "before"})
    code104 = r104.get("code", "")
    data104 = r104.get("data") or {}
    rt104 = data104.get("resultType", "")
    msg104 = data104.get("msg", "")[:100]
    print(f"  btnCode=104 before: code={code104} rt={rt104} msg={msg104}")
    
    # Test btnCode 103 (delete) 
    r103 = client.post_json("/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
                            {"busiId": busi_id, "btnCode": "103", "dealFlag": "before"})
    code103 = r103.get("code", "")
    data103 = r103.get("data") or {}
    rt103 = data103.get("resultType", "")
    msg103 = data103.get("msg", "")[:100]
    print(f"  btnCode=103 before: code={code103} rt={rt103} msg={msg103}")
