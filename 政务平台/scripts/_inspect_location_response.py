"""Deep inspect loadCurrentLocationInfo response to understand server state."""
import sys, json, copy
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
user_id = "824032604"
busi_id = "2048388847616139266"
name_id = "2048387710974500865"

# loadCurrentLocationInfo with POST
loc_body = {
    "flowData": {
        "busiId": busi_id,
        "busiType": "02_4",
        "entType": "4540",
        "nameId": name_id,
    },
    "linkData": {
        "continueFlag": "continueFlag",
        "token": user_id,
    },
}
loc_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    loc_body,
    extra_headers={"Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html"},
)
print(f"code={loc_resp.get('code')}")

# Save full response
with open("packet_lab/out/loadlocation_full_response.json", "w", encoding="utf-8") as f:
    json.dump(loc_resp, f, ensure_ascii=False, indent=2)

# Print the full busiData structure
bd = loc_resp.get('data', {}).get('busiData', {})
print(f"\nbusiData keys: {list(bd.keys())}")
fd = bd.get('flowData', {})
print(f"flowData: {json.dumps(fd, ensure_ascii=False)[:500]}")
ld = bd.get('linkData', {})
print(f"linkData: {json.dumps(ld, ensure_ascii=False)[:500]}")

# Check processVo and currentLocationVo
pvo = bd.get('processVo')
clvo = bd.get('currentLocationVo')
print(f"\nprocessVo: {json.dumps(pvo, ensure_ascii=False)[:500] if pvo else 'None'}")
print(f"currentLocationVo: {json.dumps(clvo, ensure_ascii=False)[:500] if clvo else 'None'}")

# Check all top-level keys in busiData
for k in bd:
    v = bd[k]
    if v is not None and v != "" and v != [] and v != {}:
        if isinstance(v, dict):
            print(f"  {k}: dict with keys {list(v.keys())[:10]}")
        elif isinstance(v, list):
            print(f"  {k}: list with {len(v)} items")
        else:
            val_str = str(v)[:100]
            print(f"  {k}: {val_str}")
