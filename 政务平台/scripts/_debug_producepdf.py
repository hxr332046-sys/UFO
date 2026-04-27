"""Debug producePdf: compare our request body vs what the frontend sends."""
import sys, json
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient
from phase2_protocol_driver import Phase2Context, _establish_busi_id

client = ICPSPClient()

# Load latest context
with open('dashboard/data/records/phase2_establish_latest.json', 'r', encoding='utf-8') as f:
    latest = json.load(f)

ctx_state = latest.get('context_state', {})
snap = ctx_state.get('phase2_driver_snapshot', {})

busi_id = snap.get('establish_busiId') or ctx_state.get('establish_busi_id')
name_id = ctx_state.get('name_id')
user_id = "824032604"

print(f"busi_id={busi_id}")
print(f"name_id={name_id}")
print(f"user_id={user_id}")

# Try producePdf with minimal body
body = {
    "flowData": {
        "busiId": busi_id,
        "entType": "4540",
        "busiType": "02",
        "ywlbSign": "4",
        "busiMode": None,
        "nameId": name_id,
        "marPrId": None,
        "secondId": None,
        "vipChannel": None,
        "currCompUrl": "YbbSelect",
        "status": "10",
        "matterCode": None,
        "interruptControl": None,
    },
    "linkData": {
        "compUrl": "YbbSelect",
        "compUrlPaths": ["YbbSelect"],
        "continueFlag": "",
        "token": user_id,
    },
}

print("\n=== producePdf attempt 1 (minimal flowData) ===")
resp = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body)
print(f"code={resp.get('code')} msg={resp.get('msg')}")

# Try with full flowData from last save response
last_save_fd = snap.get('last_save_flowData')
if last_save_fd:
    print("\n=== producePdf attempt 2 (last_save_flowData) ===")
    import copy
    body2 = {
        "flowData": copy.deepcopy(last_save_fd),
        "linkData": {
            "compUrl": "YbbSelect",
            "compUrlPaths": ["YbbSelect"],
            "continueFlag": "",
            "token": user_id,
        },
    }
    body2["flowData"]["currCompUrl"] = "YbbSelect"
    resp2 = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body2)
    print(f"code={resp2.get('code')} msg={resp2.get('msg')}")
    if resp2.get('data'):
        d = resp2['data']
        print(f"  resultType={d.get('resultType')} msg={d.get('msg')}")

# Try with linkData from YbbSelect save response
last_save_ld = snap.get('last_save_linkData')
if last_save_ld:
    print("\n=== producePdf attempt 3 (full linkData from save) ===")
    import copy
    body3 = {
        "flowData": copy.deepcopy(last_save_fd or {}),
        "linkData": copy.deepcopy(last_save_ld),
    }
    if not body3["flowData"].get("busiId"):
        body3["flowData"]["busiId"] = busi_id
    body3["flowData"]["currCompUrl"] = "YbbSelect"
    body3["linkData"]["token"] = user_id
    body3["linkData"]["continueFlag"] = ""
    resp3 = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body3)
    print(f"code={resp3.get('code')} msg={resp3.get('msg')}")
    if resp3.get('data'):
        d = resp3['data']
        print(f"  resultType={d.get('resultType')} msg={d.get('msg')}")

# Try loading YbbSelect first to get fresh flowData
print("\n=== Load YbbSelect for fresh flowData ===")
load_resp = client.get_json(
    "/icpsp-api/v4/pc/register/establish/component/YbbSelect/loadBusinessDataInfo",
    params={"busiId": busi_id, "entType": "4540", "busiType": "02", "nameId": name_id}
)
print(f"load code={load_resp.get('code')}")
if load_resp.get('code') == '00000':
    bd = load_resp.get('data', {}).get('busiData', {})
    fd = bd.get('flowData', {})
    ld = bd.get('linkData', {})
    print(f"  flowData keys: {list(fd.keys())[:10]}")
    print(f"  linkData keys: {list(ld.keys())[:10]}")
    print(f"  flowData.busiId={fd.get('busiId')}")
    print(f"  linkData.token={ld.get('token')}")
    
    import copy
    body4 = {
        "flowData": copy.deepcopy(fd),
        "linkData": copy.deepcopy(ld),
    }
    body4["linkData"]["token"] = user_id
    body4["linkData"]["continueFlag"] = ""
    print("\n=== producePdf attempt 4 (fresh load data) ===")
    resp4 = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body4)
    print(f"code={resp4.get('code')} msg={resp4.get('msg')}")
    if resp4.get('data'):
        d = resp4['data']
        print(f"  resultType={d.get('resultType')} msg={d.get('msg')}")
