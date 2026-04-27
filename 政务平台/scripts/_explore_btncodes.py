"""Test different btnCode values for matters/operate"""
import json, sys
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()

# Get a matter to test with
r = client.get_json("/icpsp-api/v4/pc/manager/mattermanager/matters/search",
                    params={"pageNo": "1", "pageSize": "50"})
items = (r.get("data") or {}).get("busiData") or []

# Use the first matter with state 101 (in progress)
test_matter = None
for it in items:
    if "101" in str(it.get("matterStateLangCode", "")):
        test_matter = it
        break

if not test_matter:
    print("No matter with state 101 found. Testing with first matter.")
    test_matter = items[0] if items else None

if not test_matter:
    print("No matters at all!")
    sys.exit(0)

busi_id = test_matter.get("id", "")
name = test_matter.get("entName", "")
state = test_matter.get("matterStateLangCode", "")
print(f"Testing with: {name} id={busi_id} state={state}")

# Test various btnCode values with dealFlag="before" (just probe, don't execute)
btn_codes = ["101", "102", "103", "104", "105", "106", "107", "108", "109", "110"]
for code in btn_codes:
    try:
        r = client.post_json("/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
                             {"busiId": busi_id, "btnCode": code, "dealFlag": "before"})
        resp_code = r.get("code", "")
        data = r.get("data") or {}
        rt = data.get("resultType", "")
        msg = data.get("msg", "")[:80]
        print(f"  btnCode={code}: code={resp_code} rt={rt} msg={msg}")
    except Exception as e:
        print(f"  btnCode={code}: ERROR {e}")
