"""Force full login and test producePdf."""
import sys, json, copy
sys.path.insert(0, 'system')
from login_qrcode_pure_http import full_login
from icpsp_api_client import ICPSPClient

# Force full login
print("Forcing full login...")
token = full_login()
print(f"Token: {token[:8]}...")

client = ICPSPClient()
user_id = "824032604"

busi_id = "2048388847616139266"
name_id = "2048387710974500865"

# Test if session is valid
pos_resp = client.get_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    params={"busiId": busi_id}
)
print(f"loadCurrentLocationInfo: code={pos_resp.get('code')} msg={pos_resp.get('msg')}")
if pos_resp.get('code') == '00000':
    bd = pos_resp.get('data', {}).get('busiData', {})
    fd = bd.get('flowData', {})
    print(f"  currCompUrl={fd.get('currCompUrl')}")
    print(f"  status={fd.get('status')}")
