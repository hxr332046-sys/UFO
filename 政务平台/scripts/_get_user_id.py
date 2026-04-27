"""Get current user ID for linkData.token"""
import sys, json
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
r = client.get_json("/icpsp-api/v4/pc/manager/usermanager/getUserInfo")
print(json.dumps(r, ensure_ascii=False, indent=2)[:1000])

# Extract user ID
data = r.get("data") or {}
user = data.get("user") or data.get("busiData") or {}
uid = user.get("id") or data.get("id") or ""
print(f"\nUser ID: {uid}")
