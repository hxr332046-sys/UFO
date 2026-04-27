"""Try to resume the active matter and test producePdf."""
import sys, json, copy
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
user_id = "824032604"
busi_id = "2048388847616139266"
name_id = "2048387710974500865"

# Try btnCode=108 (继续办理) to re-enter the establish flow
print("=== Try btnCode=108 (继续办理) ===")
r1 = client.post_json("/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
                       {"busiId": busi_id, "btnCode": "108", "dealFlag": "before"})
rt1 = (r1.get("data") or {}).get("resultType", "")
msg1 = (r1.get("data") or {}).get("msg", "")[:80]
print(f"  before: rt={rt1} msg={msg1}")
if rt1 == "2":
    r2 = client.post_json("/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
                           {"busiId": busi_id, "btnCode": "108", "dealFlag": "operate"})
    rt2 = (r2.get("data") or {}).get("resultType", "")
    msg2 = (r2.get("data") or {}).get("msg", "")[:80]
    print(f"  operate: rt={rt2} msg={msg2}")

# Now try loadCurrentLocationInfo again
print("\n=== loadCurrentLocationInfo ===")
pos_resp = client.get_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    params={"busiId": busi_id}
)
print(f"  code={pos_resp.get('code')} msg={pos_resp.get('msg')}")
if pos_resp.get('code') == '00000':
    bd = pos_resp.get('data', {}).get('busiData', {})
    fd = bd.get('flowData', {})
    print(f"  currCompUrl={fd.get('currCompUrl')}")
    print(f"  status={fd.get('status')}")
    print(f"  busiId={fd.get('busiId')}")
    
    # Try producePdf
    print("\n=== producePdf ===")
    body = {
        "flowData": copy.deepcopy(fd),
        "linkData": {
            "compUrl": "YbbSelect",
            "compUrlPaths": ["YbbSelect"],
            "continueFlag": "",
            "token": user_id,
        },
    }
    resp = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body)
    print(f"  code={resp.get('code')} msg={resp.get('msg')}")
    if resp.get('data'):
        d = resp['data']
        print(f"  resultType={d.get('resultType')} msg={d.get('msg')}")
else:
    # Try getUserInfo to verify session
    print("\n=== getUserInfo ===")
    ui_resp = client.get_json("/icpsp-api/v4/pc/manager/usermanager/getUserInfo")
    print(f"  code={ui_resp.get('code')}")
    bd = ui_resp.get('data', {}).get('busiData', {})
    print(f"  id={bd.get('id')}")
    print(f"  name={bd.get('name')}")
