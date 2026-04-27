"""Re-login and clean up active matters."""
import sys, json
sys.path.insert(0, 'system')
from login_qrcode_pure_http import full_login
from icpsp_api_client import ICPSPClient

print("Re-logging in...")
token = full_login()
print(f"Token: {token[:8]}...")

client = ICPSPClient()

# Verify login
user_resp = client.get_json('/icpsp-api/v4/pc/manager/usermanager/getUserInfo')
user_bd = (user_resp.get('data') or {}).get('busiData') or {}
user_id = user_bd.get('id', '')
user_name = user_bd.get('name', '')
print(f"User: id={user_id} name={user_name}")

if not user_id:
    print("Login failed!")
    sys.exit(1)

# Search matters
print("\n=== 搜索办件 ===")
resp = client.get_json('/icpsp-api/v4/pc/manager/mattermanager/matters/search', 
                       params={'pageNo':'1','pageSize':'50'})
items = (resp.get('data') or {}).get('busiData') or []
print(f"Found {len(items)} matters:")
for it in items:
    mid = it.get("id", "")
    mname = it.get("entName", "")
    mstate = it.get("matterStateLangCode", "")
    mnameid = it.get("nameId", "")
    mtype = it.get("busiTypeName", "")
    print(f"  {mname} id={mid} state={mstate} type={mtype} nameId={mnameid}")

# Clean up each active matter
for it in items:
    busi_id = it.get("id", "")
    ent_name = it.get("entName", "")
    state = it.get("matterStateLangCode", "")
    
    if not busi_id:
        continue
    
    print(f"\n=== 清理: {ent_name} (busiId={busi_id}, state={state}) ===")
    
    # Try withdraw (104)
    for dealFlag in ["before", "operate"]:
        r = client.post_json(
            "/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
            {"busiId": busi_id, "btnCode": "104", "dealFlag": dealFlag},
        )
        rt = str((r.get("data") or {}).get("resultType", ""))
        msg = (r.get("data") or {}).get("msg") or r.get("msg") or ""
        print(f"  撤回104 {dealFlag}: code={r.get('code')} rt={rt} msg={msg[:80]}")
        if rt != "2" and dealFlag == "before":
            break  # No confirmation needed, skip operate
    
    # Try delete (103)
    for dealFlag in ["before", "operate"]:
        r = client.post_json(
            "/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
            {"busiId": busi_id, "btnCode": "103", "dealFlag": dealFlag},
        )
        rt = str((r.get("data") or {}).get("resultType", ""))
        msg = (r.get("data") or {}).get("msg") or r.get("msg") or ""
        print(f"  删除103 {dealFlag}: code={r.get('code')} rt={rt} msg={msg[:80]}")
        if rt != "2" and dealFlag == "before":
            break

# Verify
print("\n=== 验证 ===")
resp2 = client.get_json('/icpsp-api/v4/pc/manager/mattermanager/matters/search',
                        params={'pageNo':'1','pageSize':'50'})
items2 = (resp2.get('data') or {}).get('busiData') or []
print(f"剩余办件: {len(items2)}")
for it in items2:
    print(f"  {it.get('entName','')} id={it.get('id','')} state={it.get('matterStateLangCode','')}")
