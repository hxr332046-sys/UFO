"""Check current full state - status changed to 90."""
import sys, json, copy
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
busi_id = "2048544858885832706"
name_id = "2048544825345122306"
user_id = "824032604"

# Full loadCurrentLocationInfo response
loc_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    {"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id},
     "linkData": {"continueFlag": "continueFlag", "token": user_id}},
)
loc_bd = (loc_resp.get('data') or {}).get('busiData') or {}
loc_fd = loc_bd.get('flowData', {})
pvo = loc_bd.get('processVo', {})

print(f"=== Current State ===")
print(f"flowData.currCompUrl={loc_fd.get('currCompUrl')}")
print(f"flowData.status={loc_fd.get('status')}")
print(f"processVo.currentComp={pvo.get('currentComp')}")
print(f"processVo.currentStep={pvo.get('currentStep')}")
print(f"processVo.maxSaveStep={pvo.get('maxSaveStep')}")
print(f"processVo.lastOperStep={pvo.get('lastOperStep')}")
print(f"producePdfVo={loc_bd.get('producePdfVo')}")
print(f"preSubmitVo={loc_bd.get('preSubmitVo')}")
print(f"submitVo={loc_bd.get('submitVo')}")
print(f"returnModifyVo={loc_bd.get('returnModifyVo')}")

# Check matters list
print("\n=== Check matters ===")
matters_resp = client.post_json(
    "/icpsp-api/v4/pc/manager/mattermanager/matters/list",
    {"pageNum": 1, "pageSize": 10, "state": "", "busiType": "", "tabId": "underway"},
)
matters_data = matters_resp.get('data') or {}
items = matters_data.get('list') or []
for item in items:
    if item.get('busiId') == busi_id:
        print(f"  busiId={item.get('busiId')}")
        print(f"  state={item.get('state')} stateName={item.get('stateName')}")
        print(f"  busiTypeName={item.get('busiTypeName')}")
        print(f"  curComp={item.get('curComp')} currCompName={item.get('currCompName')}")
        print(f"  buttonList={[b.get('btnCode') for b in (item.get('buttonList') or [])]}")
        break

# Save full response
with open("packet_lab/out/current_state_after_relogin.json", "w", encoding="utf-8") as f:
    json.dump({"loc": loc_resp, "matters": matters_resp}, f, ensure_ascii=False, indent=2)
print("\nFull response saved to packet_lab/out/current_state_after_relogin.json")
