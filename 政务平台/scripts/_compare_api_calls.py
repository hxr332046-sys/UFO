"""Compare headers and cookies between successful and failing API calls."""
import sys, json, copy, requests
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
busi_id = "2048544858885832706"
name_id = "2048544825345122306"
user_id = "824032604"

# Get the session and headers
s = client.s
headers = client._headers()

# Print all cookies in the session
print("=== Session Cookies ===")
for c in s.cookies:
    print(f"  {c.name}={c.value[:20]}... domain={c.domain} path={c.path}")

# 1. Successful call: loadCurrentLocationInfo
print("\n=== loadCurrentLocationInfo (should succeed) ===")
r1 = s.post(
    "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    json={"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id},
          "linkData": {"continueFlag": "continueFlag", "token": user_id}},
    headers=headers,
    verify=False,
    timeout=30,
)
resp1 = r1.json()
print(f"  HTTP status: {r1.status_code}")
print(f"  code: {resp1.get('code')}")
print(f"  Response cookies: {dict(r1.cookies)}")

# 2. Failing call: YbbSelect/loadBusinessDataInfo
print("\n=== YbbSelect/loadBusinessDataInfo (should fail) ===")
r2 = s.post(
    "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/v4/pc/register/establish/component/YbbSelect/loadBusinessDataInfo",
    json={"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id, "currCompUrl": "YbbSelect"},
          "linkData": {"compUrl": "YbbSelect", "compUrlPaths": ["YbbSelect"], "busiCompComb": True, "opeType": "load", "token": user_id}},
    headers=headers,
    verify=False,
    timeout=30,
)
resp2 = r2.json()
print(f"  HTTP status: {r2.status_code}")
print(f"  code: {resp2.get('code')}")
print(f"  Response cookies: {dict(r2.cookies)}")

# 3. Try with explicit Referer header for core.html
print("\n=== YbbSelect/loadBusinessDataInfo with Referer=core.html ===")
headers2 = copy.deepcopy(headers)
headers2["Referer"] = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html"
r3 = s.post(
    "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/v4/pc/register/establish/component/YbbSelect/loadBusinessDataInfo",
    json={"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id, "currCompUrl": "YbbSelect"},
          "linkData": {"compUrl": "YbbSelect", "compUrlPaths": ["YbbSelect"], "busiCompComb": True, "opeType": "load", "token": user_id}},
    headers=headers2,
    verify=False,
    timeout=30,
)
resp3 = r3.json()
print(f"  HTTP status: {r3.status_code}")
print(f"  code: {resp3.get('code')}")

# 4. Try the earlier component that worked (BasicInfo)
print("\n=== BasicInfo/loadBusinessDataInfo (should work?) ===")
r4 = s.post(
    "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/v4/pc/register/establish/component/BasicInfo/loadBusinessDataInfo",
    json={"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id, "currCompUrl": "BasicInfo"},
          "linkData": {"compUrl": "BasicInfo", "compUrlPaths": ["BasicInfo"], "busiCompComb": True, "opeType": "load", "token": user_id}},
    headers=headers,
    verify=False,
    timeout=30,
)
resp4 = r4.json()
print(f"  HTTP status: {r4.status_code}")
print(f"  code: {resp4.get('code')}")

# 5. Try BusinessLicenceWay (the component right before YbbSelect)
print("\n=== BusinessLicenceWay/loadBusinessDataInfo ===")
r5 = s.post(
    "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/v4/pc/register/establish/component/BusinessLicenceWay/loadBusinessDataInfo",
    json={"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id, "currCompUrl": "BusinessLicenceWay"},
          "linkData": {"compUrl": "BusinessLicenceWay", "compUrlPaths": ["BusinessLicenceWay"], "busiCompComb": True, "opeType": "load", "token": user_id}},
    headers=headers,
    verify=False,
    timeout=30,
)
resp5 = r5.json()
print(f"  HTTP status: {r5.status_code}")
print(f"  code: {resp5.get('code')}")
