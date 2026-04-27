"""Full cleanup: check all matter states and try to remove blocking ones."""
import sys, json
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()

# Verify session
user_resp = client.get_json('/icpsp-api/v4/pc/manager/usermanager/getUserInfo')
user_bd = (user_resp.get('data') or {}).get('busiData') or {}
user_id = user_bd.get('id', '')
print(f"User: id={user_id} name={user_bd.get('name','')}")
if not user_id:
    print("Session expired! Need re-login.")
    sys.exit(1)

# Search ALL matters with different states
print("\n=== 搜索所有办件 ===")
for state_code in ['', '100', '101', '102', '103', '104', '105']:
    params = {'pageNo': '1', 'pageSize': '50'}
    if state_code:
        params['matterStateCode'] = state_code
    resp = client.get_json('/icpsp-api/v4/pc/manager/mattermanager/matters/search', params=params)
    items = (resp.get('data') or {}).get('busiData') or []
    if items:
        print(f"\n  state={state_code or 'all'}: {len(items)} matters")
        for it in items:
            mid = it.get("id", "")
            mname = it.get("entName", "")
            mstate = it.get("matterStateLangCode", "")
            mtype = it.get("busiTypeName", "")
            print(f"    {mname} id={mid} state={mstate} type={mtype}")

# Try to clean up state=100 matters (active/进行中)
print("\n=== 清理进行中的办件 ===")
resp = client.get_json('/icpsp-api/v4/pc/manager/mattermanager/matters/search',
                       params={'pageNo':'1','pageSize':'50','matterStateCode':'100'})
items = (resp.get('data') or {}).get('busiData') or []
for it in items:
    busi_id = it.get("id", "")
    ent_name = it.get("entName", "")
    if not busi_id:
        continue
    print(f"\n  清理: {ent_name} (busiId={busi_id})")
    
    # Try btnCode=103 (delete) directly
    for dealFlag in ["before", "operate"]:
        r = client.post_json(
            "/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
            {"busiId": busi_id, "btnCode": "103", "dealFlag": dealFlag},
        )
        rt = str((r.get("data") or {}).get("resultType", ""))
        msg = (r.get("data") or {}).get("msg") or r.get("msg") or ""
        code = r.get("code")
        print(f"    删除103 {dealFlag}: code={code} rt={rt} msg={msg[:80]}")
        if code != "00000" or (dealFlag == "before" and rt != "2"):
            break

# Also try btnCode=108 (继续办理) for state=104 matters to see if they can be resumed and then withdrawn
print("\n=== 检查已提交办件(104)是否可撤回 ===")
resp = client.get_json('/icpsp-api/v4/pc/manager/mattermanager/matters/search',
                       params={'pageNo':'1','pageSize':'50','matterStateCode':'104'})
items = (resp.get('data') or {}).get('busiData') or []
for it in items:
    busi_id = it.get("id", "")
    ent_name = it.get("entName", "")
    if not busi_id:
        continue
    # Try btnCode=104 (withdraw)
    r = client.post_json(
        "/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
        {"busiId": busi_id, "btnCode": "104", "dealFlag": "before"},
    )
    rt = str((r.get("data") or {}).get("resultType", ""))
    msg = (r.get("data") or {}).get("msg") or r.get("msg") or ""
    code = r.get("code")
    print(f"  {ent_name}: 撤回104 code={code} rt={rt} msg={msg[:80]}")

# Final check: try to start a new name registration
print("\n=== 测试能否新建办件 ===")
name_resp = client.post_json(
    "/icpsp-api/v4/pc/register/name/loadCurrentLocationInfo",
    {"flowData": {"busiType": "01_4", "entType": "4540"}, "linkData": {"token": user_id}},
)
print(f"  name/loadCurrentLocationInfo: code={name_resp.get('code')} msg={name_resp.get('msg')}")
