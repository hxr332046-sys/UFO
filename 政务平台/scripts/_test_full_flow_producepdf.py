"""Test producePdf with full flowData from loadCurrentLocationInfo."""
import sys, json, copy
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
user_id = "824032604"
busi_id = "2048544858885832706"
name_id = "2048544825345122306"

# Step 1: loadCurrentLocationInfo to get FULL flowData/linkData
print("=== Step 1: loadCurrentLocationInfo ===")
loc_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    {"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id},
     "linkData": {"continueFlag": "continueFlag", "token": user_id}},
)
loc_bd = (loc_resp.get('data') or {}).get('busiData') or {}
loc_fd = loc_bd.get('flowData', {})
loc_ld = loc_bd.get('linkData', {})
print(f"  code={loc_resp.get('code')} currCompUrl={loc_fd.get('currCompUrl')}")

# Step 2: YbbSelect load with full flowData/linkData from loc
print("\n=== Step 2: YbbSelect/loadBusinessDataInfo ===")
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
print(f"  code={ybb_resp.get('code')} signInfo={ybb_bd.get('signInfo')}")

# Step 3: YbbSelect save
print("\n=== Step 3: YbbSelect save ===")
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
save_rt = str(save_data.get('resultType', ''))
print(f"  code={save_resp.get('code')} rt={save_rt}")

# Step 4: producePdf with full flowData from save response or YbbSelect load
if save_resp.get('code') == '00000':
    # Use the save response's flowData (which should be updated)
    pdf_fd = copy.deepcopy(save_bd.get('flowData') or ybb_fd)
    pdf_ld = copy.deepcopy(save_bd.get('linkData') or ybb_ld)
    
    # If save response has no flowData, use the YbbSelect load flowData
    if not pdf_fd.get('busiId'):
        pdf_fd = copy.deepcopy(ybb_fd)
    if not pdf_ld.get('busiCompComb'):
        pdf_ld = copy.deepcopy(ybb_ld)
    
    pdf_ld["token"] = user_id
    pdf_ld["continueFlag"] = ""
    pdf_ld["opeType"] = ""
    
    print(f"\n=== Step 4: producePdf ===")
    print(f"  flowData.busiId={pdf_fd.get('busiId')}")
    print(f"  flowData.currCompUrl={pdf_fd.get('currCompUrl')}")
    print(f"  flowData.status={pdf_fd.get('status')}")
    print(f"  linkData.busiCompComb type={type(pdf_ld.get('busiCompComb')).__name__}")
    
    pdf_resp = client.post_json(
        "/icpsp-api/v4/pc/register/establish/producePdf",
        {"flowData": pdf_fd, "linkData": pdf_ld},
    )
    print(f"  code={pdf_resp.get('code')} msg={pdf_resp.get('msg')}")
    pdf_data = pdf_resp.get('data') or {}
    print(f"  resultType={pdf_data.get('resultType')} msg={pdf_data.get('msg')}")
    
    # Save for analysis
    out = {
        "save_response": save_resp,
        "producePdf_response": pdf_resp,
        "producePdf_flowData": pdf_fd,
        "producePdf_linkData": pdf_ld,
    }
    with open("packet_lab/out/producepdf_full_flow_test.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
else:
    print(f"  Save failed, skipping producePdf")
    print(f"  Full response: {json.dumps(save_resp, ensure_ascii=False)[:300]}")
