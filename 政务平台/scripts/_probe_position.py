"""Probe current position for the active matter."""
import sys, json
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()

# Load latest context
with open('dashboard/data/records/phase2_establish_latest.json', 'r', encoding='utf-8') as f:
    latest = json.load(f)

ctx_state = latest.get('context_state', {})
busi_id = ctx_state.get('phase2_driver_snapshot', {}).get('establish_busiId')
print(f"busi_id={busi_id}")

# Probe current position
resp = client.get_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    params={"busiId": busi_id}
)
print(f"code={resp.get('code')}")
bd = resp.get('data', {}).get('busiData', {})
fd = bd.get('flowData', {})
print(f"  currCompUrl={fd.get('currCompUrl')}")
print(f"  status={fd.get('status')}")
print(f"  busiId={fd.get('busiId')}")
print(f"  busiType={fd.get('busiType')}")

# Try load PreElectronicDoc
print("\n=== Try load PreElectronicDoc ===")
resp2 = client.get_json(
    "/icpsp-api/v4/pc/register/establish/component/PreElectronicDoc/loadBusinessDataInfo",
    params={"busiId": busi_id, "entType": "4540", "busiType": "02"}
)
print(f"code={resp2.get('code')} msg={resp2.get('msg')}")
if resp2.get('code') == '00000':
    bd2 = resp2.get('data', {}).get('busiData', {})
    fd2 = bd2.get('flowData', {})
    ld2 = bd2.get('linkData', {})
    print(f"  currCompUrl={fd2.get('currCompUrl')}")
    print(f"  status={fd2.get('status')}")
    print(f"  linkData.token={ld2.get('token')}")
    print(f"  linkData keys: {list(ld2.keys())}")

# Try producePdf with PreElectronicDoc context
print("\n=== producePdf with PreElectronicDoc context ===")
import copy
body = {
    "flowData": copy.deepcopy(fd2) if resp2.get('code') == '00000' else {"busiId": busi_id, "entType": "4540", "busiType": "02", "nameId": ctx_state.get('name_id'), "currCompUrl": "PreElectronicDoc", "status": "10"},
    "linkData": {
        "compUrl": "PreElectronicDoc",
        "compUrlPaths": ["PreElectronicDoc"],
        "continueFlag": "",
        "token": "824032604",
    },
}
resp3 = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body)
print(f"code={resp3.get('code')} msg={resp3.get('msg')}")
