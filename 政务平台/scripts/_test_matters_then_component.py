"""Test: does loadCurrentLocationInfo establish a session state needed for component APIs?"""
import sys, json, copy, requests, time, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
busi_id = "2048544858885832706"
name_id = "2048544825345122306"
user_id = "824032604"

# The key insight: loadCurrentLocationInfo succeeds but component APIs fail.
# Maybe loadCurrentLocationInfo sets a server-side session that component APIs need.
# But our requests are stateless (REST)...
# 
# Wait - maybe the issue is that the establish flow hasn't been properly "entered" yet.
# The runner did step10/11 (matters/operate 108) at the beginning, which establishes
# the server-side session for this busiId.
#
# Let's try: matters/operate 108 first, then component API

print("=== Step 1: matters/operate 108 before ===")
r1 = client.post_json(
    "/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
    {"busiId": busi_id, "btnCode": "108", "dealFlag": "before"},
)
print(f"  code={r1.get('code')} rt={str((r1.get('data') or {}).get('resultType',''))}")

print("\n=== Step 2: matters/operate 108 operate ===")
r2 = client.post_json(
    "/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
    {"busiId": busi_id, "btnCode": "108", "dealFlag": "operate"},
)
print(f"  code={r2.get('code')} rt={str((r2.get('data') or {}).get('resultType',''))}")

print("\n=== Step 3: loadCurrentLocationInfo ===")
r3 = client.post_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    {"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id},
     "linkData": {"continueFlag": "continueFlag", "token": user_id}},
)
r3_bd = (r3.get('data') or {}).get('busiData') or {}
r3_fd = r3_bd.get('flowData', {})
print(f"  code={r3.get('code')} currCompUrl={r3_fd.get('currCompUrl')} status={r3_fd.get('status')}")

print("\n=== Step 4: YbbSelect/loadBusinessDataInfo (after matters/operate) ===")
r4 = client.post_json(
    "/icpsp-api/v4/pc/register/establish/component/YbbSelect/loadBusinessDataInfo",
    {"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id, "currCompUrl": "YbbSelect"},
     "linkData": {"compUrl": "YbbSelect", "compUrlPaths": ["YbbSelect"], "busiCompComb": True, "opeType": "load", "token": user_id}},
)
r4_bd = (r4.get('data') or {}).get('busiData') or {}
print(f"  code={r4.get('code')}")
if r4.get('code') == '00000':
    print(f"  flowData keys: {list(r4_bd.get('flowData', {}).keys())}")
    print(f"  signInfo={r4_bd.get('signInfo')}")
    print(f"  producePdfVo={r4_bd.get('producePdfVo')}")

# If still A0002, try with the flowData from loadCurrentLocationInfo
if r4.get('code') != '00000':
    print("\n=== Step 5: YbbSelect/load with flowData from loadCurrentLocationInfo ===")
    r5 = client.post_json(
        "/icpsp-api/v4/pc/register/establish/component/YbbSelect/loadBusinessDataInfo",
        {"flowData": copy.deepcopy(r3_fd),
         "linkData": {"compUrl": "YbbSelect", "compUrlPaths": ["YbbSelect"], "busiCompComb": True, "opeType": "load", "token": user_id}},
    )
    print(f"  code={r5.get('code')}")
    if r5.get('code') == '00000':
        r5_bd = (r5.get('data') or {}).get('busiData') or {}
        print(f"  flowData keys: {list(r5_bd.get('flowData', {}).keys())}")
        print(f"  signInfo={r5_bd.get('signInfo')}")
