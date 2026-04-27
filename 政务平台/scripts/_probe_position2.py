"""Probe current position with fresh token."""
import sys, json
sys.path.insert(0, 'system')
from login_qrcode_pure_http import ensure_token
from icpsp_api_client import ICPSPClient

# Refresh token first
token = ensure_token()
print(f"Token: {token[:8]}...")

client = ICPSPClient()

# Load latest context
with open('dashboard/data/records/phase2_establish_latest.json', 'r', encoding='utf-8') as f:
    latest = json.load(f)

ctx_state = latest.get('context_state', {})
busi_id = ctx_state.get('phase2_driver_snapshot', {}).get('establish_busiId')
name_id = ctx_state.get('name_id')
print(f"busi_id={busi_id}")
print(f"name_id={name_id}")

# Probe current position
resp = client.get_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    params={"busiId": busi_id}
)
print(f"loadCurrentLocationInfo: code={resp.get('code')} msg={resp.get('msg')}")
if resp.get('code') == '00000':
    bd = resp.get('data', {}).get('busiData', {})
    fd = bd.get('flowData', {})
    print(f"  currCompUrl={fd.get('currCompUrl')}")
    print(f"  status={fd.get('status')}")
    print(f"  busiId={fd.get('busiId')}")
else:
    print("  No data - session may be expired or busiId invalid")

# Try load PreElectronicDoc
print("\n=== Try load PreElectronicDoc ===")
resp2 = client.get_json(
    "/icpsp-api/v4/pc/register/establish/component/PreElectronicDoc/loadBusinessDataInfo",
    params={"busiId": busi_id, "entType": "4540", "busiType": "02"}
)
print(f"code={resp2.get('code')} msg={resp2.get('msg')}")

# Try producePdf with PreElectronicDoc
print("\n=== producePdf with PreElectronicDoc ===")
import copy
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
        "currCompUrl": "PreElectronicDoc",
        "status": "10",
        "matterCode": None,
        "interruptControl": None,
    },
    "linkData": {
        "compUrl": "PreElectronicDoc",
        "compUrlPaths": ["PreElectronicDoc"],
        "continueFlag": "",
        "token": "824032604",
    },
}
resp3 = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body)
print(f"code={resp3.get('code')} msg={resp3.get('msg')}")
if resp3.get('data'):
    d = resp3['data']
    print(f"  resultType={d.get('resultType')} msg={d.get('msg')}")
