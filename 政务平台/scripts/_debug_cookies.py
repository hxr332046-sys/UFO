"""Debug session cookies."""
import sys
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()

print("Session cookies:")
for c in client.s.cookies:
    print(f"  {c.name}={c.value[:20]}... domain={c.domain} path={c.path}")

# Check if we have the 6087 SESSION
has_6087 = any('6087' in c.domain or 'zhjg.scjdglj.gxzf.gov.cn' in c.domain for c in client.s.cookies)
print(f"\nHas zhjg domain cookies: {has_6087}")

# Check the pkl file
from pathlib import Path
pkl_path = Path("packet_lab/out/http_session_cookies.pkl")
if pkl_path.exists():
    import pickle
    with open(pkl_path, 'rb') as f:
        cj = pickle.load(f)
    print(f"\nPkl cookies ({len(list(cj))} items):")
    for c in cj:
        print(f"  {c.name}={c.value[:20]}... domain={c.domain}")
