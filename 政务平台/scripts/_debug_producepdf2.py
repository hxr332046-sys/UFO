"""Debug producePdf: try with full save response data."""
import sys, json, copy
sys.path.insert(0, 'system')
from login_qrcode_pure_http import ensure_token
from icpsp_api_client import ICPSPClient

# Refresh token
token = ensure_token()
print(f"Token: {token[:8]}...")

client = ICPSPClient()

# Load latest result to get the YbbSelect save response
with open('dashboard/data/records/phase2_establish_latest.json', 'r', encoding='utf-8') as f:
    latest = json.load(f)

# Find step23 result
step_history = latest.get('step_history', [])
step23_result = None
for s in step_history:
    if s.get('step_number') == 23:
        step23_result = s
        break

if not step23_result:
    print("No step23 result found!")
    sys.exit(1)

print(f"Step23 code={step23_result.get('code')}")

# Get the raw response
raw = step23_result.get('raw_response')
if raw:
    print(f"Raw response keys: {list(raw.keys()) if isinstance(raw, dict) else type(raw)}")
    # The save response contains flowData and linkData
    save_data = raw.get('data', {}).get('busiData', {})
    save_fd = save_data.get('flowData', {})
    save_ld = save_data.get('linkData', {})
    print(f"  save flowData keys: {list(save_fd.keys())[:15]}")
    print(f"  save linkData keys: {list(save_ld.keys())[:15]}")
    print(f"  save flowData.busiId={save_fd.get('busiId')}")
    print(f"  save linkData.token={save_ld.get('token')}")
    print(f"  save linkData.busiCompComb={save_ld.get('busiCompComb')}")
    print(f"  save linkData.busiCompUrlPaths={save_ld.get('busiCompUrlPaths')}")
else:
    print("No raw_response in step23")
    # Try from snapshot
    snap = latest.get('context_state', {}).get('phase2_driver_snapshot', {})
    save_fd = snap.get('last_save_flowData', {})
    save_ld = snap.get('last_save_linkData', {})
    print(f"  snap flowData keys: {list(save_fd.keys())[:15]}")
    print(f"  snap linkData keys: {list(save_ld.keys())[:15]}")

busi_id = save_fd.get('busiId') or latest.get('context_state', {}).get('phase2_driver_snapshot', {}).get('establish_busiId')
name_id = save_fd.get('nameId') or latest.get('context_state', {}).get('name_id')
user_id = "824032604"

print(f"\nbusi_id={busi_id}")
print(f"name_id={name_id}")

# Attempt 1: producePdf with full save response data + token override
print("\n=== producePdf with full save data ===")
body1 = {
    "flowData": copy.deepcopy(save_fd),
    "linkData": copy.deepcopy(save_ld),
}
body1["linkData"]["token"] = user_id
body1["linkData"]["continueFlag"] = ""
body1["flowData"]["currCompUrl"] = "YbbSelect"
print(f"  flowData.busiId={body1['flowData'].get('busiId')}")
print(f"  linkData.token={body1['linkData'].get('token')}")
print(f"  linkData.busiCompComb={body1['linkData'].get('busiCompComb')}")
print(f"  linkData.busiCompUrlPaths={body1['linkData'].get('busiCompUrlPaths')}")
resp1 = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body1)
print(f"  code={resp1.get('code')} msg={resp1.get('msg')}")
if resp1.get('data'):
    d = resp1['data']
    print(f"  resultType={d.get('resultType')} msg={d.get('msg')}")

# Attempt 2: producePdf with minimal body like the JS does
# The JS just sets token on the existing t object and sends it
# t = { flowData: {...}, linkData: {...} } from the current form state
print("\n=== producePdf with minimal body (only busiId in flowData) ===")
body2 = {
    "flowData": {
        "busiId": busi_id,
        "entType": "4540",
        "busiType": "02",
        "nameId": name_id,
    },
    "linkData": {
        "token": user_id,
    },
}
resp2 = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", body2)
print(f"  code={resp2.get('code')} msg={resp2.get('msg')}")
if resp2.get('data'):
    d = resp2['data']
    print(f"  resultType={d.get('resultType')} msg={d.get('msg')}")

# Attempt 3: Check if the matter still exists
print("\n=== Check matters ===")
matters_resp = client.get_json('/icpsp-api/v4/pc/manager/mattermanager/matters/search', params={'pageNo':'1','pageSize':'50'})
items = (matters_resp.get('data') or {}).get('busiData') or []
for it in items:
    mid = it.get("id", "")
    mname = it.get("entName", "")
    mstate = it.get("matterStateLangCode", "")
    print(f"  {mname} id={mid} state={mstate}")
