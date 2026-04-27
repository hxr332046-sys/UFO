"""Test loadCurrentLocationInfo with explicit Cookie header."""
import sys, json, requests
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
busi_id = "2048388847616139266"

# Method 1: Normal client call
print("=== Method 1: Normal client call ===")
resp1 = client.get_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    params={"busiId": busi_id}
)
print(f"  code={resp1.get('code')} msg={resp1.get('msg')}")

# Method 2: With explicit Cookie header
print("\n=== Method 2: With explicit Cookie header ===")
h = client._headers()
# Build cookie string from session
cookie_str = "; ".join(f"{c.name}={c.value}" for c in client.s.cookies)
h["Cookie"] = cookie_str
print(f"  Cookie length: {len(cookie_str)}")

url = f"https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo?busiId={busi_id}&t=1234567890"
r = requests.get(url, headers=h, verify=False, timeout=30)
resp2 = r.json()
print(f"  code={resp2.get('code')} msg={resp2.get('msg')}")

# Method 3: Check response headers for clues
print(f"\n  Response status: {r.status_code}")
print(f"  Response headers: {dict(r.headers)[:200] if len(str(dict(r.headers))) > 200 else dict(r.headers)}")
