"""Test producePdf with current active matter"""
import json, sys, time
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient
import phase2_bodies as pb
from phase2_constants import establish_comp_load, establish_comp_op

client = ICPSPClient()

# First, search for any active matter
r = client.get_json("/icpsp-api/v4/pc/manager/mattermanager/matters/search",
                    params={"pageNo": "1", "pageSize": "50"})
items = (r.get("data") or {}).get("busiData") or []
active = [it for it in items if "100" in str(it.get("matterStateLangCode", ""))]
print(f"Active matters (status=100): {len(active)}")

if not active:
    print("No active matters to test producePdf. Need a fresh registration first.")
    sys.exit(0)

# Use the first active matter
it = active[0]
busi_id = it.get("id", "")
name_id = it.get("nameId", "")
ent_type = it.get("entType", "4540")
ent_name = it.get("entName", "")
print(f"Using: {ent_name} busiId={busi_id} nameId={name_id} entType={ent_type}")

REFERER = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html"
hdrs = {"Referer": REFERER}

# Step 1: probe current location
print("\n[1] Probe current location...")
probe_body = {
    "flowData": {
        "busiId": busi_id,
        "entType": ent_type,
        "busiType": "02",
        "ywlbSign": "4",
        "busiMode": None,
        "nameId": name_id,
        "marPrId": None,
        "secondId": None,
        "vipChannel": None,
    },
    "linkData": {"continueFlag": "continueFlag", "token": ""},
}
probe_resp = client.post_json("/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
                              probe_body, extra_headers=hdrs)
probe_data = probe_resp.get("data") or {}
probe_bd = probe_data.get("busiData") or {}
probe_fd = probe_bd.get("flowData") or {}
curr_comp = probe_fd.get("currCompUrl", "")
status = probe_fd.get("status", "")
print(f"  currCompUrl={curr_comp} status={status}")
print(f"  code={probe_resp.get('code')}")

# Step 2: Try producePdf with different body variants
print("\n[2] Testing producePdf variants...")

# Variant A: minimal body (just flowData + linkData)
body_a = {
    "flowData": pb._base_flow_data(ent_type, name_id, "YbbSelect", busi_id=busi_id),
    "linkData": {"compUrl": "YbbSelect", "compUrlPaths": ["YbbSelect"], "continueFlag": "", "token": ""},
}
print("\n  Variant A (base flowData):")
r_a = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body_a, extra_headers=hdrs)
print(f"    code={r_a.get('code')} msg={r_a.get('msg','')[:100]}")
if r_a.get("data"):
    print(f"    data.resultType={r_a['data'].get('resultType')}")

# Variant B: with busiId in flowData + status
body_b = {
    "flowData": {
        "busiId": busi_id,
        "entType": ent_type,
        "busiType": "02",
        "ywlbSign": "4",
        "nameId": name_id,
        "currCompUrl": "YbbSelect",
        "status": status or "10",
    },
    "linkData": {"compUrl": "YbbSelect", "compUrlPaths": ["YbbSelect"], "continueFlag": "", "token": ""},
}
print("\n  Variant B (busiId + status):")
r_b = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body_b, extra_headers=hdrs)
print(f"    code={r_b.get('code')} msg={r_b.get('msg','')[:100]}")
if r_b.get("data"):
    print(f"    data.resultType={r_b['data'].get('resultType')}")

# Variant C: with signInfo
body_c = {
    "flowData": {
        "busiId": busi_id,
        "entType": ent_type,
        "busiType": "02",
        "ywlbSign": "4",
        "nameId": name_id,
        "currCompUrl": "YbbSelect",
        "status": status or "10",
    },
    "linkData": {"compUrl": "YbbSelect", "compUrlPaths": ["YbbSelect"], "continueFlag": "", "token": ""},
    "signInfo": "-1607173598",
    "itemId": "",
}
print("\n  Variant C (with signInfo):")
r_c = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body_c, extra_headers=hdrs)
print(f"    code={r_c.get('code')} msg={r_c.get('msg','')[:100]}")
if r_c.get("data"):
    print(f"    data.resultType={r_c['data'].get('resultType')}")

# Variant D: using full flowData from probe response
if probe_fd:
    body_d = {
        "flowData": probe_fd,
        "linkData": {"compUrl": "YbbSelect", "compUrlPaths": ["YbbSelect"], "continueFlag": "", "token": ""},
        "signInfo": probe_bd.get("signInfo", ""),
        "itemId": "",
    }
    print("\n  Variant D (full probe flowData):")
    r_d = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body_d, extra_headers=hdrs)
    print(f"    code={r_d.get('code')} msg={r_d.get('msg','')[:100]}")
    if r_d.get("data"):
        print(f"    data.resultType={r_d['data'].get('resultType')}")
