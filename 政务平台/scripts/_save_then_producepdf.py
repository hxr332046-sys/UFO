"""Save YbbSelect first, then try producePdf - to test if save is prerequisite."""
import sys, json, copy
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient
import phase2_bodies as pb

client = ICPSPClient()
user_id = "824032604"
busi_id = "2048388847616139266"
name_id = "2048387710974500865"

# Load YbbSelect first
print("=== Step 1: Load YbbSelect ===")
loc_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    {
        "flowData": {"busiId": busi_id, "busiType": "02_4", "entType": "4540", "nameId": name_id},
        "linkData": {"continueFlag": "continueFlag", "token": user_id},
    },
    extra_headers={"Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html"},
)
loc_bd = loc_resp.get('data', {}).get('busiData', {})
loc_fd = loc_bd.get('flowData', {})
loc_ld = loc_bd.get('linkData', {})
print(f"  currCompUrl={loc_fd.get('currCompUrl')} currentComp={loc_bd.get('processVo',{}).get('currentComp')}")

# Load YbbSelect component
print("\n=== Step 2: Load YbbSelect component ===")
ybb_load_body = {
    "flowData": copy.deepcopy(loc_fd),
    "linkData": {
        "compUrl": "YbbSelect",
        "opeType": "load",
        "compUrlPaths": ["YbbSelect"],
        "busiCompUrlPaths": loc_ld.get("busiCompUrlPaths", "%5B%5D"),
        "continueFlag": "",
        "token": user_id,
    },
    "itemId": "",
}
ybb_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/component/YbbSelect/loadBusinessDataInfo",
    ybb_load_body,
    extra_headers={"Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html"},
)
print(f"  code={ybb_resp.get('code')}")
ybb_bd = (ybb_resp.get('data') or {}).get('busiData') or {}
ybb_fd = ybb_bd.get('flowData', {})
ybb_ld = ybb_bd.get('linkData', {})
ybb_si = ybb_bd.get('signInfo')
print(f"  signInfo={ybb_si}")
print(f"  isSelectYbb={ybb_bd.get('isSelectYbb')}")

# Save YbbSelect
print("\n=== Step 3: Save YbbSelect ===")
save_body = pb.build_ybb_select_save_body(
    {"isOptional": "1", "preAuditSign": "0", "isSelectYbb": "0"},
    base=ybb_bd,
    ent_type="4540", name_id=name_id,
    busi_id=busi_id, user_id=user_id,
)
save_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/component/YbbSelect/operationBusinessDataInfo",
    save_body,
    extra_headers={"Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html"},
)
save_code = save_resp.get('code')
save_data = save_resp.get('data') or {}
save_rt = str(save_data.get('resultType') or "")
save_msg = save_data.get('msg') or save_resp.get('msg') or ""
print(f"  code={save_code} rt={save_rt} msg={save_msg}")

# Save the save response
save_bd = save_data.get('busiData') or {}
save_fd = save_bd.get('flowData') or {}
save_ld = save_bd.get('linkData') or {}
print(f"  save flowData.currCompUrl={save_fd.get('currCompUrl')}")
print(f"  save flowData.status={save_fd.get('status')}")
print(f"  save linkData keys={list(save_ld.keys())}")

# Now try producePdf immediately after save
print("\n=== Step 4: producePdf after save ===")
pdf_body = {
    "flowData": copy.deepcopy(save_fd) if (save_fd and save_fd.get('busiId')) else copy.deepcopy(ybb_fd),
    "linkData": copy.deepcopy(save_ld) if save_ld else copy.deepcopy(ybb_ld),
}
pdf_body["linkData"]["token"] = user_id
pdf_body["linkData"]["continueFlag"] = ""
pdf_body["flowData"]["currCompUrl"] = pdf_body["flowData"].get("currCompUrl") or "YbbSelect"

pdf_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/producePdf",
    pdf_body,
    extra_headers={"Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html"},
)
print(f"  code={pdf_resp.get('code')} msg={pdf_resp.get('msg')}")
if pdf_resp.get('data'):
    d = pdf_resp['data']
    print(f"  resultType={d.get('resultType')} msg={d.get('msg')}")

# Also check loadCurrentLocationInfo after save
print("\n=== Step 5: loadCurrentLocationInfo after save ===")
loc_resp2 = client.post_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    {
        "flowData": {"busiId": busi_id, "busiType": "02_4", "entType": "4540", "nameId": name_id},
        "linkData": {"continueFlag": "continueFlag", "token": user_id},
    },
    extra_headers={"Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html"},
)
loc_bd2 = loc_resp2.get('data', {}).get('busiData', {})
loc_fd2 = loc_bd2.get('flowData', {})
pvo2 = loc_bd2.get('processVo', {})
print(f"  currCompUrl={loc_fd2.get('currCompUrl')}")
print(f"  currentComp={pvo2.get('currentComp')}")
print(f"  producePdfVo={loc_bd2.get('producePdfVo')}")
