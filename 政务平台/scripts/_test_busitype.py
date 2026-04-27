"""Test different busiType values for YbbSelect load."""
import sys, json, copy
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
user_id = "824032604"
busi_id = "2048544858885832706"
name_id = "2048544825345122306"

# Try different busiType values
for bt in ["02", "02_4", "02_1"]:
    print(f"\n=== YbbSelect load with busiType={bt} ===")
    resp = client.post_json(
        "/icpsp-api/v4/pc/register/establish/component/YbbSelect/loadBusinessDataInfo",
        {"flowData": {"busiId": busi_id, "busiType": bt, "entType": "4540", "nameId": name_id, "currCompUrl": "YbbSelect"},
         "linkData": {"compUrl": "YbbSelect", "compUrlPaths": ["YbbSelect"], "busiCompComb": True, "opeType": "load", "token": user_id}},
    )
    code = resp.get('code', '')
    bd = (resp.get('data') or {}).get('busiData') or {}
    fd = bd.get('flowData', {})
    print(f"  code={code} currCompUrl={fd.get('currCompUrl')}")
    if code == '00000':
        print(f"  flowData keys: {list(fd.keys())}")
        print(f"  signInfo={bd.get('signInfo')}")
        ld = bd.get('linkData', {})
        print(f"  linkData keys: {list(ld.keys())}")
        print(f"  linkData.busiCompComb={ld.get('busiCompComb')}")
        # Also check producePdfVo
        print(f"  producePdfVo={bd.get('producePdfVo')}")

# Also try loadCurrentLocationInfo with different busiType
print("\n\n=== loadCurrentLocationInfo with busiType=02 ===")
loc_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    {"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id},
     "linkData": {"continueFlag": "continueFlag", "token": user_id}},
)
loc_bd = (loc_resp.get('data') or {}).get('busiData') or {}
loc_fd = loc_bd.get('flowData', {})
print(f"  code={loc_resp.get('code')} currCompUrl={loc_fd.get('currCompUrl')}")
print(f"  producePdfVo={loc_bd.get('producePdfVo')}")
