"""Check if there's a name registration blocking new business."""
import sys, json
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()

# Check name registration state
print("=== Check name registration state ===")
name_resp = client.post_json(
    "/icpsp-api/v4/pc/register/name/loadCurrentLocationInfo",
    {
        "flowData": {"busiType": "01_4", "entType": "4540"},
        "linkData": {"token": "824032604"},
    },
)
print(f"  code={name_resp.get('code')} msg={name_resp.get('msg')}")
if name_resp.get('code') == '00000':
    bd = (name_resp.get('data') or {}).get('busiData') or {}
    fd = bd.get('flowData', {})
    print(f"  flowData: busiId={fd.get('busiId')} currCompUrl={fd.get('currCompUrl')} status={fd.get('status')}")

# The error "450921198812051251@123账号正在办理设立登记" means:
# The system thinks this user already has an active 设立登记 business
# This might be from the establish busiId we just deleted
# Let's try to start fresh

# Try establish/loadCurrentLocationInfo without busiId
print("\n=== Check establish state (no busiId) ===")
est_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    {
        "flowData": {"busiType": "02_4", "entType": "4540"},
        "linkData": {"continueFlag": "continueFlag", "token": "824032604"},
    },
)
print(f"  code={est_resp.get('code')} msg={est_resp.get('msg')}")
if est_resp.get('code') == '00000':
    bd = (est_resp.get('data') or {}).get('busiData') or {}
    fd = bd.get('flowData', {})
    print(f"  flowData: busiId={fd.get('busiId')} currCompUrl={fd.get('currCompUrl')} status={fd.get('status')}")

# Try the selectBusinessModules API (the one that gives the error)
print("\n=== selectBusinessModules (reproduce the error) ===")
try:
    biz_resp = client.get_json('/icpsp-api/v4/pc/register/guide/home/selectBusinessModules')
    print(f"  code={biz_resp.get('code')} msg={biz_resp.get('msg')}")
    if biz_resp.get('data'):
        print(f"  data keys: {list(biz_resp['data'].keys())[:10]}")
except Exception as e:
    print(f"  Error: {e}")
