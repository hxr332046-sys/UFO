"""Check if Authorization token is still valid for component APIs."""
import sys, json, requests, copy, warnings, time
warnings.filterwarnings("ignore")
sys.path.insert(0, 'system')
from login_qrcode_pure_http import ensure_token, refresh_token
from icpsp_api_client import ICPSPClient

# Force refresh token
print("=== Force token refresh ===")
new_token = refresh_token()
print(f"New token: {new_token}")

# Recreate client
client = ICPSPClient()
busi_id = "2048544858885832706"
name_id = "2048544825345122306"
user_id = "824032604"

# Test loadCurrentLocationInfo
print("\n=== loadCurrentLocationInfo ===")
r1 = client.post_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    {"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id},
     "linkData": {"continueFlag": "continueFlag", "token": user_id}},
)
print(f"  code={r1.get('code')}")

# Test YbbSelect load
print("\n=== YbbSelect/loadBusinessDataInfo ===")
r2 = client.post_json(
    "/icpsp-api/v4/pc/register/establish/component/YbbSelect/loadBusinessDataInfo",
    {"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id, "currCompUrl": "YbbSelect"},
     "linkData": {"compUrl": "YbbSelect", "compUrlPaths": ["YbbSelect"], "busiCompComb": True, "opeType": "load", "token": user_id}},
)
print(f"  code={r2.get('code')}")

# Test BasicInfo load (this worked during runner)
print("\n=== BasicInfo/loadBusinessDataInfo ===")
r3 = client.post_json(
    "/icpsp-api/v4/pc/register/establish/component/BasicInfo/loadBusinessDataInfo",
    {"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id, "currCompUrl": "BasicInfo"},
     "linkData": {"compUrl": "BasicInfo", "compUrlPaths": ["BasicInfo"], "busiCompComb": True, "opeType": "load", "token": user_id}},
)
print(f"  code={r3.get('code')}")

# If still A0002, try with full busiCompComb from loadCurrentLocationInfo
if r2.get('code') != '00000':
    r1_bd = (r1.get('data') or {}).get('busiData') or {}
    r1_ld = r1_bd.get('linkData', {})
    r1_fd = r1_bd.get('flowData', {})
    
    print(f"\nloadCurrentLocationInfo linkData has busiCompComb: {bool(r1_ld.get('busiCompComb'))}")
    print(f"loadCurrentLocationInfo flowData keys: {list(r1_fd.keys())}")
    
    # Try YbbSelect load with FULL flowData/linkData from loadCurrentLocationInfo
    print("\n=== YbbSelect/load with full flowData from loadCurrentLocationInfo ===")
    load_body = {
        "flowData": copy.deepcopy(r1_fd),
        "linkData": copy.deepcopy(r1_ld),
        "itemId": "",
    }
    load_body["linkData"]["compUrl"] = "YbbSelect"
    load_body["linkData"]["opeType"] = "load"
    load_body["linkData"]["compUrlPaths"] = ["YbbSelect"]
    load_body["flowData"]["currCompUrl"] = "YbbSelect"
    
    r4 = client.post_json(
        "/icpsp-api/v4/pc/register/establish/component/YbbSelect/loadBusinessDataInfo",
        load_body,
    )
    print(f"  code={r4.get('code')}")
    if r4.get('code') == '00000':
        r4_bd = (r4.get('data') or {}).get('busiData') or {}
        print(f"  flowData keys: {list(r4_bd.get('flowData', {}).keys())}")
        print(f"  signInfo={r4_bd.get('signInfo')}")
        print(f"  producePdfVo={r4_bd.get('producePdfVo')}")
