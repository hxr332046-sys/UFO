"""Direct test: load current state and try producePdf with full flowData."""
import sys, json, copy
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
user_id = "824032604"
busi_id = "2048544858885832706"
name_id = "2048544825345122306"

# 1. Load current location
print("=== loadCurrentLocationInfo ===")
loc_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    {"flowData": {"busiId": busi_id, "busiType": "02_4", "entType": "4540", "nameId": name_id},
     "linkData": {"continueFlag": "continueFlag", "token": user_id}},
)
loc_bd = (loc_resp.get('data') or {}).get('busiData') or {}
loc_fd = loc_bd.get('flowData', {})
pvo = loc_bd.get('processVo', {})
print(f"  code={loc_resp.get('code')} currCompUrl={loc_fd.get('currCompUrl')} status={loc_fd.get('status')}")
print(f"  currentComp={pvo.get('currentComp')} currentStep={pvo.get('currentStep')}")
print(f"  producePdfVo={loc_bd.get('producePdfVo')}")
print(f"  flowData keys: {list(loc_fd.keys())}")
print(f"  linkData keys: {list((loc_bd.get('linkData') or {}).keys())}")

# 2. Load YbbSelect component
print("\n=== YbbSelect/loadBusinessDataInfo ===")
ybb_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/component/YbbSelect/loadBusinessDataInfo",
    {"flowData": {"busiId": busi_id, "busiType": "02_4", "entType": "4540", "nameId": name_id, "currCompUrl": "YbbSelect"},
     "linkData": {"compUrl": "YbbSelect", "compUrlPaths": ["YbbSelect"], "busiCompComb": True, "opeType": "load", "token": user_id}},
)
ybb_bd = (ybb_resp.get('data') or {}).get('busiData') or {}
ybb_fd = ybb_bd.get('flowData', {})
ybb_ld = ybb_bd.get('linkData', {})
print(f"  code={ybb_resp.get('code')} currCompUrl={ybb_fd.get('currCompUrl')}")
print(f"  flowData keys: {list(ybb_fd.keys())}")
print(f"  linkData keys: {list(ybb_ld.keys())}")
print(f"  signInfo={ybb_bd.get('signInfo')}")

# 3. Try producePdf with the FULL flowData from load
print("\n=== producePdf (with full flowData from load) ===")
pdf_body = {
    "flowData": copy.deepcopy(ybb_fd),
    "linkData": copy.deepcopy(ybb_ld),
}
pdf_body["linkData"]["token"] = user_id
pdf_body["linkData"]["continueFlag"] = ""
pdf_body["linkData"]["opeType"] = ""  # producePdf doesn't use opeType

# Print the full body for comparison
print(f"  flowData.busiId={pdf_body['flowData'].get('busiId')}")
print(f"  flowData.currCompUrl={pdf_body['flowData'].get('currCompUrl')}")
print(f"  flowData.status={pdf_body['flowData'].get('status')}")
print(f"  flowData.entType={pdf_body['flowData'].get('entType')}")
print(f"  flowData.busiType={pdf_body['flowData'].get('busiType')}")
print(f"  flowData.nameId={pdf_body['flowData'].get('nameId')}")
print(f"  linkData.token={pdf_body['linkData'].get('token')}")
print(f"  linkData.compUrl={pdf_body['linkData'].get('compUrl')}")
print(f"  linkData.opeType={pdf_body['linkData'].get('opeType')}")

pdf_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/producePdf",
    pdf_body,
)
print(f"  code={pdf_resp.get('code')} msg={pdf_resp.get('msg')}")
pdf_data = pdf_resp.get('data') or {}
print(f"  resultType={pdf_data.get('resultType')} msg={pdf_data.get('msg')}")

# Save the full flowData for analysis
out = {
    "busi_id": busi_id,
    "loc_response": loc_resp,
    "ybb_load_response": ybb_resp,
    "producePdf_body": pdf_body,
    "producePdf_response": pdf_resp,
}
with open("packet_lab/out/producepdf_debug_state.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f"\nSaved to packet_lab/out/producepdf_debug_state.json")
