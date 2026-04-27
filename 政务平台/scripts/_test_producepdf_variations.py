"""Deep debug: capture full producePdf request and response."""
import sys, json, copy, requests, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
user_id = "824032604"
busi_id = "2048544858885832706"
name_id = "2048544825345122306"

# Step 1: loadCurrentLocationInfo
loc_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    {"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id},
     "linkData": {"continueFlag": "continueFlag", "token": user_id}},
)
loc_bd = (loc_resp.get('data') or {}).get('busiData') or {}
loc_fd = loc_bd.get('flowData', {})
loc_ld = loc_bd.get('linkData', {})

# Step 2: YbbSelect load
ybb_load_body = {
    "flowData": copy.deepcopy(loc_fd),
    "linkData": copy.deepcopy(loc_ld),
    "itemId": "",
}
ybb_load_body["linkData"]["compUrl"] = "YbbSelect"
ybb_load_body["linkData"]["opeType"] = "load"
ybb_load_body["linkData"]["compUrlPaths"] = ["YbbSelect"]
ybb_load_body["flowData"]["currCompUrl"] = "YbbSelect"

ybb_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/component/YbbSelect/loadBusinessDataInfo",
    ybb_load_body,
)
ybb_bd = (ybb_resp.get('data') or {}).get('busiData') or {}
ybb_fd = ybb_bd.get('flowData', {})
ybb_ld = ybb_bd.get('linkData', {})

# Step 3: YbbSelect save
save_body = {
    "isOptional": "1",
    "preAuditSign": "0",
    "isSelectYbb": "0",
    "flowData": copy.deepcopy(ybb_fd),
    "linkData": copy.deepcopy(ybb_ld),
    "signInfo": str(ybb_bd.get('signInfo', '')),
    "itemId": ybb_bd.get('itemId', ''),
}
save_body["linkData"]["compUrl"] = "YbbSelect"
save_body["linkData"]["opeType"] = "save"
save_body["linkData"]["compUrlPaths"] = ["YbbSelect"]
save_body["linkData"]["token"] = user_id
save_body["linkData"]["continueFlag"] = ""

save_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/component/YbbSelect/operationBusinessDataInfo",
    save_body,
)
save_data = save_resp.get('data') or {}
save_bd = save_data.get('busiData') or {}
print(f"Save: code={save_resp.get('code')} rt={save_data.get('resultType')}")

# Step 4: producePdf - try MULTIPLE variations
# Variation A: Use save response flowData + YbbSelect load linkData
pdf_fd_a = copy.deepcopy(save_bd.get('flowData') or ybb_fd)
pdf_ld_a = copy.deepcopy(ybb_ld)  # Use YbbSelect load linkData (has full busiCompComb)
pdf_ld_a["token"] = user_id
pdf_ld_a["continueFlag"] = ""
pdf_ld_a["opeType"] = ""

print(f"\n=== Variation A: save flowData + load linkData ===")
pdf_resp_a = client.post_json(
    "/icpsp-api/v4/pc/register/establish/producePdf",
    {"flowData": pdf_fd_a, "linkData": pdf_ld_a},
)
print(f"  code={pdf_resp_a.get('code')} msg={pdf_resp_a.get('msg')}")

# Variation B: Use loc flowData + loc linkData (from loadCurrentLocationInfo)
pdf_fd_b = copy.deepcopy(loc_fd)
pdf_ld_b = copy.deepcopy(loc_ld)
pdf_ld_b["token"] = user_id
pdf_ld_b["continueFlag"] = ""
pdf_ld_b["opeType"] = ""

print(f"\n=== Variation B: loc flowData + loc linkData ===")
pdf_resp_b = client.post_json(
    "/icpsp-api/v4/pc/register/establish/producePdf",
    {"flowData": pdf_fd_b, "linkData": pdf_ld_b},
)
print(f"  code={pdf_resp_b.get('code')} msg={pdf_resp_b.get('msg')}")

# Variation C: Minimal body - just flowData.busiId + linkData.token
print(f"\n=== Variation C: minimal body ===")
pdf_resp_c = client.post_json(
    "/icpsp-api/v4/pc/register/establish/producePdf",
    {"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id},
     "linkData": {"token": user_id, "continueFlag": ""}},
)
print(f"  code={pdf_resp_c.get('code')} msg={pdf_resp_c.get('msg')}")

# Variation D: With compUrl in linkData
print(f"\n=== Variation D: with compUrl=YbbSelect ===")
pdf_resp_d = client.post_json(
    "/icpsp-api/v4/pc/register/establish/producePdf",
    {"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id, "currCompUrl": "YbbSelect"},
     "linkData": {"token": user_id, "continueFlag": "", "compUrl": "YbbSelect"}},
)
print(f"  code={pdf_resp_d.get('code')} msg={pdf_resp_d.get('msg')}")

# Save all responses
out = {
    "A_save_flowData_load_linkData": pdf_resp_a,
    "B_loc_flowData_loc_linkData": pdf_resp_b,
    "C_minimal": pdf_resp_c,
    "D_with_compUrl": pdf_resp_d,
    "save_response": save_resp,
}
with open("packet_lab/out/producepdf_variations.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
