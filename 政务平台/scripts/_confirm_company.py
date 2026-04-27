"""Confirm which company this busi_id belongs to."""
import sys, json
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()

# busi_id we've been working with
target_busi_id = "2048544858885832706"

# Try different matters list endpoints
endpoints = [
    "/icpsp-api/v4/pc/manager/manager/matters/list",
    "/icpsp-api/v4/pc/manager/personalbusiness/getBusinessList",
    "/icpsp-api/v4/pc/manager/personalbusiness/getMyBusinessList",
]

# Just try loadCurrentLocationInfo with a different approach
# and load BasicInfo with full server-returned linkData
loc_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    {"flowData": {"busiId": target_busi_id, "busiType": "02", "entType": "4540", "nameId": "2048544825345122306"},
     "linkData": {"continueFlag": "continueFlag", "token": "824032604"}},
)

bd = (loc_resp.get('data') or {}).get('busiData') or {}
clv = bd.get('currentLocationVo', {})
fd = bd.get('flowData', {})

print("=== Business Info ===")
print(f"busiId: {fd.get('busiId')}")
print(f"entType: {fd.get('entType')}")
print(f"busiType: {fd.get('busiType')}")
print(f"nameId: {fd.get('nameId')}")
print(f"status: {fd.get('status')}")
print(f"")
print(f"entName: {clv.get('entName')}")
print(f"uniScId: {clv.get('uniScId')}")
print(f"")
print(f"Process state:")
pvo = bd.get('processVo', {})
print(f"  currentComp: {pvo.get('currentComp')}")
print(f"  currentStep: {pvo.get('currentStep')}")
print(f"  maxSaveStep: {pvo.get('maxSaveStep')}")
print(f"  lastOperStep: {pvo.get('lastOperStep')}")

# Also load BasicInfo with full link from loc
import copy
bi_body = {
    "flowData": copy.deepcopy(fd),
    "linkData": copy.deepcopy(bd.get('linkData', {})),
    "itemId": "",
}
bi_body["flowData"]["currCompUrl"] = "BasicInfo"
bi_body["linkData"]["compUrl"] = "BasicInfo"
bi_body["linkData"]["opeType"] = "load"
bi_body["linkData"]["compUrlPaths"] = ["BasicInfo"]

bi_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/component/BasicInfo/loadBusinessDataInfo",
    bi_body,
)
bi_bd = (bi_resp.get('data') or {}).get('busiData') or {}
print(f"\n=== BasicInfo (full linkData) ===")
print(f"  entName: {bi_bd.get('entName')}")
print(f"  regCap: {bi_bd.get('regCap')}")
print(f"  domDistCode: {bi_bd.get('domDistCode')}")
print(f"  dom: {bi_bd.get('dom')}")
print(f"  ywqyFlag: {bi_bd.get('ywqyFlag')}")
print(f"  cerNo: {bi_bd.get('cerNo')}")
