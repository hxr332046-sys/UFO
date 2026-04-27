"""Test producePdf with FULL linkData from YbbSelect load (including busiCompComb)."""
import sys, json, copy
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
user_id = "824032604"
busi_id = "2048544858885832706"
name_id = "2048544825345122306"

# Get the full linkData from snapshot (this is what YbbSelect load returned)
from pathlib import Path
p = Path(r'dashboard\data\records\phase2_establish_latest.json')
d = json.load(open(p, 'r', encoding='utf-8'))
cs = d.get('context_state', {})
snap = cs.get('phase2_driver_snapshot', {})

# Use the YbbSelect load linkData (has full busiCompComb)
ybb_bd = snap.get('YbbSelect_busiData', {})
ybb_ld = ybb_bd.get('linkData', {})
ybb_fd = ybb_bd.get('flowData', {})

print(f"YbbSelect load linkData has busiCompComb: {bool(ybb_ld.get('busiCompComb'))}")
print(f"YbbSelect load linkData keys: {list(ybb_ld.keys())}")

# Build producePdf body with FULL linkData from load
pdf_body = {
    "flowData": copy.deepcopy(ybb_fd),
    "linkData": copy.deepcopy(ybb_ld),
}
pdf_body["linkData"]["token"] = user_id
pdf_body["linkData"]["continueFlag"] = ""
pdf_body["linkData"]["opeType"] = ""  # producePdf doesn't use opeType

# Ensure flowData has all required fields
if not pdf_body["flowData"].get("busiId"):
    pdf_body["flowData"]["busiId"] = busi_id
if not pdf_body["flowData"].get("nameId"):
    pdf_body["flowData"]["nameId"] = name_id
if not pdf_body["flowData"].get("entType"):
    pdf_body["flowData"]["entType"] = "4540"
if not pdf_body["flowData"].get("busiType"):
    pdf_body["flowData"]["busiType"] = "02"
if not pdf_body["flowData"].get("currCompUrl"):
    pdf_body["flowData"]["currCompUrl"] = "YbbSelect"

print(f"\nproducePdf body:")
print(f"  flowData.busiId={pdf_body['flowData'].get('busiId')}")
print(f"  flowData.currCompUrl={pdf_body['flowData'].get('currCompUrl')}")
print(f"  flowData.status={pdf_body['flowData'].get('status')}")
print(f"  linkData.token={pdf_body['linkData'].get('token')}")
print(f"  linkData.compUrl={pdf_body['linkData'].get('compUrl')}")
print(f"  linkData.busiCompComb type={type(pdf_body['linkData'].get('busiCompComb')).__name__}")
print(f"  linkData.busiCompComb keys={list(pdf_body['linkData'].get('busiCompComb', {}).keys()) if isinstance(pdf_body['linkData'].get('busiCompComb'), dict) else 'N/A'}")

pdf_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/producePdf",
    pdf_body,
)
print(f"\nproducePdf result:")
print(f"  code={pdf_resp.get('code')} msg={pdf_resp.get('msg')}")
pdf_data = pdf_resp.get('data') or {}
print(f"  resultType={pdf_data.get('resultType')} msg={pdf_data.get('msg')}")

# Save for analysis
out = {"producePdf_body": pdf_body, "producePdf_response": pdf_resp}
with open("packet_lab/out/producepdf_full_linkdata_test.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
