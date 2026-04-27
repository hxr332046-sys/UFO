"""Test loadCurrentLocationInfo without busiId."""
import sys, json
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()

# Test without busiId
print("=== loadCurrentLocationInfo without busiId ===")
resp = client.get_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    params={}
)
print(f"  code={resp.get('code')} msg={resp.get('msg')}")
if resp.get('data'):
    bd = resp.get('data', {}).get('busiData', {})
    fd = bd.get('flowData', {})
    print(f"  currCompUrl={fd.get('currCompUrl')}")
    print(f"  status={fd.get('status')}")

# Test with nameId instead
print("\n=== loadCurrentLocationInfo with nameId ===")
resp2 = client.get_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    params={"nameId": "2048387710974500865"}
)
print(f"  code={resp2.get('code')} msg={resp2.get('msg')}")

# Test getUserInfo
print("\n=== getUserInfo ===")
resp3 = client.get_json("/icpsp-api/v4/pc/manager/usermanager/getUserInfo")
print(f"  code={resp3.get('code')}")
bd3 = resp3.get('data', {}).get('busiData', {})
print(f"  id={bd3.get('id')} name={bd3.get('name')}")

# Test matters search
print("\n=== matters search ===")
resp4 = client.get_json('/icpsp-api/v4/pc/manager/mattermanager/matters/search', params={'pageNo':'1','pageSize':'5'})
print(f"  code={resp4.get('code')}")
items = (resp4.get('data') or {}).get('busiData') or []
for it in items[:3]:
    print(f"  {it.get('entName')} id={it.get('id')} state={it.get('matterStateLangCode')}")
