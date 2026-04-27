"""Systematic producePdf request body testing - binary search approach.
Tests different body compositions to find which field(s) cause A0002.
"""
import sys, json, copy, time
sys.path.insert(0, 'system')
from login_qrcode_pure_http import ensure_token
from icpsp_api_client import ICPSPClient

# Force fresh login
from login_qrcode_pure_http import full_login
print("Logging in...")
token = full_login()
print(f"Token: {token[:8]}...")

client = ICPSPClient()
user_id = "824032604"
busi_id = "2048388847616139266"
name_id = "2048387710974500865"

# Step 1: loadCurrentLocationInfo with POST (not GET!)
print("\n=== Step 1: loadCurrentLocationInfo (POST) ===")
loc_body = {
    "flowData": {
        "busiId": busi_id,
        "busiType": "02_4",
        "entType": "4540",
        "nameId": name_id,
    },
    "linkData": {
        "continueFlag": "continueFlag",
        "token": user_id,
    },
}
loc_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    loc_body,
    extra_headers={"Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html"},
)
print(f"  code={loc_resp.get('code')} msg={loc_resp.get('msg')}")
if loc_resp.get('code') != '00000':
    print("  Failed! Cannot proceed with testing.")
    sys.exit(1)

loc_bd = loc_resp.get('data', {}).get('busiData', {})
loc_fd = loc_bd.get('flowData', {})
loc_ld = loc_bd.get('linkData', {})
print(f"  currCompUrl={loc_fd.get('currCompUrl')}")
print(f"  status={loc_fd.get('status')}")
print(f"  linkData keys={list(loc_ld.keys()) if loc_ld else 'N/A'}")

# Step 2: Load YbbSelect
print("\n=== Step 2: Load YbbSelect ===")
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
print(f"  code={ybb_resp.get('code')} msg={ybb_resp.get('msg')}")
ybb_bd = (ybb_resp.get('data') or {}).get('busiData') or {}
ybb_fd = ybb_bd.get('flowData', {})
ybb_ld = ybb_bd.get('linkData', {})
print(f"  flowData keys={list(ybb_fd.keys())[:15]}")
print(f"  linkData keys={list(ybb_ld.keys())}")
print(f"  isSelectYbb={ybb_bd.get('isSelectYbb')}")
print(f"  signInfo={ybb_bd.get('signInfo')}")

# Save the YbbSelect load response for reference
with open("packet_lab/out/ybb_select_load_response.json", "w", encoding="utf-8") as f:
    json.dump(ybb_bd, f, ensure_ascii=False, indent=2)

# Step 3: Now test producePdf with different body compositions
print("\n" + "=" * 80)
print("SYSTEMATIC producePdf BODY TESTING")
print("=" * 80)

# Test A: Minimal body - just busiId and token
print("\n--- Test A: Minimal body ---")
body_a = {
    "flowData": {"busiId": busi_id},
    "linkData": {"token": user_id},
}
resp_a = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body_a)
print(f"  code={resp_a.get('code')} msg={resp_a.get('msg')}")

# Test B: With flowData from loadCurrentLocationInfo
print("\n--- Test B: With loc flowData ---")
body_b = {
    "flowData": copy.deepcopy(loc_fd),
    "linkData": {"token": user_id},
}
resp_b = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body_b)
print(f"  code={resp_b.get('code')} msg={resp_b.get('msg')}")

# Test C: With full YbbSelect load data
print("\n--- Test C: Full YbbSelect load data ---")
body_c = {
    "flowData": copy.deepcopy(ybb_fd),
    "linkData": copy.deepcopy(ybb_ld),
}
body_c["linkData"]["token"] = user_id
body_c["linkData"]["continueFlag"] = ""
resp_c = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body_c)
print(f"  code={resp_c.get('code')} msg={resp_c.get('msg')}")
if resp_c.get('data'):
    d = resp_c['data']
    print(f"  resultType={d.get('resultType')} msg={d.get('msg')}")

# Test D: With loc flowData + full YbbSelect linkData
print("\n--- Test D: loc flowData + YbbSelect linkData ---")
body_d = {
    "flowData": copy.deepcopy(loc_fd),
    "linkData": copy.deepcopy(ybb_ld),
}
body_d["linkData"]["token"] = user_id
body_d["linkData"]["continueFlag"] = ""
resp_d = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body_d)
print(f"  code={resp_d.get('code')} msg={resp_d.get('msg')}")

# Test E: YbbSelect flowData + minimal linkData
print("\n--- Test E: YbbSelect flowData + minimal linkData ---")
body_e = {
    "flowData": copy.deepcopy(ybb_fd),
    "linkData": {
        "compUrl": "YbbSelect",
        "compUrlPaths": ["YbbSelect"],
        "continueFlag": "",
        "token": user_id,
    },
}
resp_e = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body_e)
print(f"  code={resp_e.get('code')} msg={resp_e.get('msg')}")

# Test F: With isSelectYbb and other top-level fields from YbbSelect
print("\n--- Test F: With isSelectYbb etc ---")
body_f = {
    "isOptional": str(ybb_bd.get('isOptional', '1')),
    "preAuditSign": str(ybb_bd.get('preAuditSign', '0')),
    "isSelectYbb": str(ybb_bd.get('isSelectYbb', '0')),
    "flowData": copy.deepcopy(ybb_fd),
    "linkData": copy.deepcopy(ybb_ld),
}
body_f["linkData"]["token"] = user_id
body_f["linkData"]["continueFlag"] = ""
resp_f = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body_f)
print(f"  code={resp_f.get('code')} msg={resp_f.get('msg')}")

# Test G: With save body (like we send in step23)
print("\n--- Test G: Save-style body ---")
body_g = {
    "isOptional": "1",
    "preAuditSign": "0",
    "isSelectYbb": "0",
    "flowData": copy.deepcopy(ybb_fd),
    "linkData": {
        "compUrl": "YbbSelect",
        "opeType": "save",
        "compUrlPaths": ["YbbSelect"],
        "busiCompUrlPaths": "%5B%5D",
        "token": user_id,
    },
    "signInfo": str(ybb_bd.get('signInfo', '-1607173598')),
    "itemId": "",
}
resp_g = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body_g)
print(f"  code={resp_g.get('code')} msg={resp_g.get('msg')}")

# Save all responses
results = {
    "A_minimal": resp_a,
    "B_loc_flowData": resp_b,
    "C_full_ybb": resp_c,
    "D_loc_fd_ybb_ld": resp_d,
    "E_ybb_fd_minimal_ld": resp_e,
    "F_with_isSelectYbb": resp_f,
    "G_save_style": resp_g,
}
with open("packet_lab/out/producepdf_test_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("\nResults saved to packet_lab/out/producepdf_test_results.json")
