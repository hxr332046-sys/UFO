"""Search for active matters using different API parameters."""
import sys, json
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()

# Try different search params
for params in [
    {'pageNo': '1', 'pageSize': '50'},
    {'pageNo': '1', 'pageSize': '50', 'matterStateCode': '101'},
    {'pageNo': '1', 'pageSize': '50', 'matterStateCode': '104'},
    {'pageNo': '1', 'pageSize': '50', 'useType': '0'},
    {'pageNo': '1', 'pageSize': '50', 'useType': '1'},
    {'pageNo': '1', 'pageSize': '50', 'searchText': ''},
]:
    resp = client.get_json('/icpsp-api/v4/pc/manager/mattermanager/matters/search', params=params)
    items = (resp.get('data') or {}).get('busiData') or []
    code = resp.get('code')
    if items:
        print(f"\nParams {params}: code={code} found={len(items)}")
        for it in items[:5]:
            print(f"  {it.get('entName','')} id={it.get('id','')} state={it.get('matterStateLangCode','')} nameId={it.get('nameId','')}")
    elif code != '00000':
        print(f"Params {params}: code={code} msg={resp.get('msg','')}")

# Also try the operate API with different btnCodes to find the blocking matter
# The error mentioned 450921198812051251 which looks like an ID card number
# Let's try getUserInfo to confirm our user
print("\n=== getUserInfo ===")
user_resp = client.get_json('/icpsp-api/v4/pc/manager/usermanager/getUserInfo')
user_bd = (user_resp.get('data') or {}).get('busiData') or {}
print(f"  id={user_bd.get('id')} name={user_bd.get('name')} cerNo={user_bd.get('cerNo','')[:6]}...")

# Try the matters/operate with the old busiId to see its state
print("\n=== Check old busiId state ===")
for bid in ["2048388847616139266", "2048039612892766209", "2048387710974500865"]:
    for btn in ["101", "102"]:
        try:
            r = client.post_json(
                "/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
                {"busiId": bid, "btnCode": btn, "dealFlag": "before"},
            )
            rt = str((r.get("data") or {}).get("resultType", ""))
            msg = (r.get("data") or {}).get("msg") or r.get("msg") or ""
            if r.get("code") == "00000":
                print(f"  busiId={bid} btn={btn}: rt={rt} msg={msg[:80]}")
        except Exception as e:
            print(f"  busiId={bid} btn={btn}: error={str(e)[:80]}")
