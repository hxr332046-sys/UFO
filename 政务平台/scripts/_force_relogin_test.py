"""Force refresh auth by re-login and update runtime_auth_headers.json."""
import sys, json
sys.path.insert(0, 'system')
from login_qrcode_pure_http import ensure_token
from icpsp_api_client import ICPSPClient

# Force re-login
print("Force re-login...")
token = ensure_token()
print(f"New token: {token}")

# Recreate client to pick up new auth
client = ICPSPClient()

# Verify
headers = client._headers()
print(f"Authorization: {headers.get('Authorization', 'N/A')}")

resp = client.get_json('/icpsp-api/v4/pc/manager/usermanager/getUserInfo')
bd = (resp.get('data') or {}).get('busiData') or {}
print(f"getUserInfo: id={bd.get('id')} name={bd.get('name')}")

# Test YbbSelect load
busi_id = "2048544858885832706"
name_id = "2048544825345122306"
user_id = "824032604"

resp2 = client.post_json(
    "/icpsp-api/v4/pc/register/establish/component/YbbSelect/loadBusinessDataInfo",
    {"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id, "currCompUrl": "YbbSelect"},
     "linkData": {"compUrl": "YbbSelect", "compUrlPaths": ["YbbSelect"], "busiCompComb": True, "opeType": "load", "token": user_id}},
)
print(f"\nYbbSelect load: code={resp2.get('code')}")
if resp2.get('code') == '00000':
    bd2 = (resp2.get('data') or {}).get('busiData') or {}
    print(f"  flowData keys: {list(bd2.get('flowData', {}).keys())}")
    print(f"  signInfo={bd2.get('signInfo')}")
