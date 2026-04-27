"""Check server state after YbbSelect save."""
import sys, json, copy
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
user_id = "824032604"
busi_id = "2048544858885832706"
name_id = "2048544825345122306"

# Check current location
loc_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    {"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id},
     "linkData": {"continueFlag": "continueFlag", "token": user_id}},
)
loc_bd = (loc_resp.get('data') or {}).get('busiData') or {}
loc_fd = loc_bd.get('flowData', {})
pvo = loc_bd.get('processVo', {})
print(f"currCompUrl={loc_fd.get('currCompUrl')}")
print(f"status={loc_fd.get('status')}")
print(f"currentComp={pvo.get('currentComp')}")
print(f"currentStep={pvo.get('currentStep')}")
print(f"maxSaveStep={pvo.get('maxSaveStep')}")
print(f"producePdfVo={loc_bd.get('producePdfVo')}")
print(f"preSubmitVo={loc_bd.get('preSubmitVo')}")
print(f"submitVo={loc_bd.get('submitVo')}")

# Full processVo
print(f"\nprocessVo: {json.dumps(pvo, ensure_ascii=False, indent=2)[:500]}")

# Check if producePdfVo appears when we load with different params
print("\n=== Try loadCurrentLocationInfo without continueFlag ===")
loc2_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    {"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id},
     "linkData": {"token": user_id}},
)
loc2_bd = (loc2_resp.get('data') or {}).get('busiData') or {}
print(f"producePdfVo={loc2_bd.get('producePdfVo')}")
print(f"currCompUrl={loc2_bd.get('flowData', {}).get('currCompUrl')}")
