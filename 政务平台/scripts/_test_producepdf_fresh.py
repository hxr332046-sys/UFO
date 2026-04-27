"""Test producePdf with fresh session."""
import sys, json, copy
sys.path.insert(0, 'system')
from login_qrcode_pure_http import ensure_token
from icpsp_api_client import ICPSPClient

# Force token refresh
token = ensure_token()
print(f"Token: {token[:8]}...")

client = ICPSPClient()
user_id = "824032604"

busi_id = "2048388847616139266"
name_id = "2048387710974500865"

# First, load current position
pos_resp = client.get_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    params={"busiId": busi_id}
)
print(f"loadCurrentLocationInfo: code={pos_resp.get('code')} msg={pos_resp.get('msg')}")
if pos_resp.get('code') != '00000':
    print("  Session expired or busiId invalid, cannot test producePdf")
    sys.exit(1)

bd = pos_resp.get('data', {}).get('busiData', {})
fd = bd.get('flowData', {})
print(f"  currCompUrl={fd.get('currCompUrl')}")
print(f"  status={fd.get('status')}")
print(f"  busiId={fd.get('busiId')}")

# Load YbbSelect
print("\n=== Load YbbSelect ===")
ybb_load_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/component/YbbSelect/loadBusinessDataInfo",
    {
        "flowData": copy.deepcopy(fd),
        "linkData": {
            "compUrl": "YbbSelect",
            "opeType": "load",
            "compUrlPaths": ["YbbSelect"],
            "busiCompUrlPaths": "%5B%5D",
            "continueFlag": "",
            "token": user_id,
        },
        "itemId": "",
    }
)
print(f"  code={ybb_load_resp.get('code')} msg={ybb_load_resp.get('msg')}")
ybb_bd = (ybb_load_resp.get('data') or {}).get('busiData') or {}
ybb_fd = ybb_bd.get('flowData', {})
ybb_ld = ybb_bd.get('linkData', {})
print(f"  flowData.busiId={ybb_fd.get('busiId')}")
print(f"  linkData.token={ybb_ld.get('token')}")
print(f"  isSelectYbb={ybb_bd.get('isSelectYbb')}")

# producePdf with fresh load data
print("\n=== producePdf with fresh load data ===")
body = {
    "flowData": copy.deepcopy(ybb_fd),
    "linkData": copy.deepcopy(ybb_ld),
}
body["linkData"]["token"] = user_id
body["linkData"]["continueFlag"] = ""
resp = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body)
print(f"  code={resp.get('code')} msg={resp.get('msg')}")
if resp.get('data'):
    d = resp['data']
    print(f"  resultType={d.get('resultType')} msg={d.get('msg')}")
