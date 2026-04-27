"""Test producePdf with different body variations on the current active matter."""
import sys, json, copy, time
sys.path.insert(0, 'system')
from login_qrcode_pure_http import ensure_token
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
user_id = "824032604"

# Load latest context
with open('dashboard/data/records/phase2_establish_latest.json', 'r', encoding='utf-8') as f:
    latest = json.load(f)

ctx_state = latest.get('context_state', {})
snap = ctx_state.get('phase2_driver_snapshot', {})
busi_id = snap.get('establish_busiId')
name_id = ctx_state.get('name_id')
print(f"busi_id={busi_id}")
print(f"name_id={name_id}")

# First, load current position
pos_resp = client.get_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    params={"busiId": busi_id}
)
print(f"\nloadCurrentLocationInfo: code={pos_resp.get('code')}")
if pos_resp.get('code') == '00000':
    bd = pos_resp.get('data', {}).get('busiData', {})
    fd = bd.get('flowData', {})
    print(f"  currCompUrl={fd.get('currCompUrl')}")
    print(f"  status={fd.get('status')}")
    print(f"  busiId={fd.get('busiId')}")
else:
    print("  Failed to get position")
    sys.exit(1)

# Load YbbSelect to get fresh data
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
print(f"  code={ybb_load_resp.get('code')}")
ybb_bd = (ybb_load_resp.get('data') or {}).get('busiData') or {}
ybb_fd = ybb_bd.get('flowData', {})
ybb_ld = ybb_bd.get('linkData', {})
ybb_si = ybb_bd.get('signInfo')
print(f"  flowData keys: {list(ybb_fd.keys())[:10]}")
print(f"  linkData keys: {list(ybb_ld.keys())}")
print(f"  signInfo: {ybb_si}")
print(f"  isOptional: {ybb_bd.get('isOptional')}")
print(f"  preAuditSign: {ybb_bd.get('preAuditSign')}")
print(f"  isSelectYbb: {ybb_bd.get('isSelectYbb')}")

# Now try producePdf with the loaded data
print("\n=== producePdf attempt 1: with fresh load data ===")
body1 = {
    "flowData": copy.deepcopy(ybb_fd),
    "linkData": copy.deepcopy(ybb_ld),
}
body1["linkData"]["token"] = user_id
body1["linkData"]["continueFlag"] = ""
resp1 = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body1)
print(f"  code={resp1.get('code')} msg={resp1.get('msg')}")
if resp1.get('data'):
    d = resp1['data']
    print(f"  resultType={d.get('resultType')} msg={d.get('msg')}")

# Attempt 2: with only flowData.busiId and linkData.token (minimal)
print("\n=== producePdf attempt 2: minimal body ===")
body2 = {
    "flowData": {"busiId": busi_id},
    "linkData": {"token": user_id},
}
resp2 = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body2)
print(f"  code={resp2.get('code')} msg={resp2.get('msg')}")

# Attempt 3: with flowData from loadCurrentLocationInfo
print("\n=== producePdf attempt 3: with loadCurrentLocationInfo flowData ===")
body3 = {
    "flowData": copy.deepcopy(fd),
    "linkData": {
        "compUrl": "YbbSelect",
        "compUrlPaths": ["YbbSelect"],
        "continueFlag": "",
        "token": user_id,
    },
}
resp3 = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body3)
print(f"  code={resp3.get('code')} msg={resp3.get('msg')}")

# Attempt 4: Try the submit endpoint instead
print("\n=== Try submit endpoint ===")
body4 = {
    "flowData": copy.deepcopy(fd),
    "linkData": {
        "compUrl": "YbbSelect",
        "compUrlPaths": ["YbbSelect"],
        "continueFlag": "",
        "token": user_id,
    },
}
resp4 = client.post_json("/icpsp-api/v4/pc/register/establish/submit", body4)
print(f"  code={resp4.get('code')} msg={resp4.get('msg')}")

# Attempt 5: Try with flowData.status=90 (maybe producePdf needs status=90?)
print("\n=== producePdf attempt 5: with status=90 ===")
body5 = copy.deepcopy(body3)
body5["flowData"]["status"] = "90"
resp5 = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body5)
print(f"  code={resp5.get('code')} msg={resp5.get('msg')}")
