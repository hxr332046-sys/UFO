"""Debug the actual HTTP request headers being sent."""
import sys, json
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
headers = client._headers()
print("Headers being sent:")
for k, v in headers.items():
    # Mask sensitive values
    if k == 'Authorization':
        print(f"  {k}: {v[:8]}...")
    elif k == 'Cookie':
        # Show cookie names
        cookies = v.split('; ')
        print(f"  {k}: {len(cookies)} cookies")
        for c in cookies[:5]:
            name = c.split('=')[0]
            print(f"    {name}=...")
    else:
        print(f"  {k}: {v}")

# Try loadCurrentLocationInfo with verbose output
busi_id = "2048388847616139266"
print(f"\nTrying loadCurrentLocationInfo with busiId={busi_id}")
resp = client.get_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    params={"busiId": busi_id}
)
print(f"Response: code={resp.get('code')} msg={resp.get('msg')}")
print(f"Full response: {json.dumps(resp, ensure_ascii=False)[:500]}")
