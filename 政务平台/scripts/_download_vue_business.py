"""Download vue-business JS which likely contains the flow-control framework."""
import sys, re, os
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
session = client.s
headers = client._headers()
base = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc"
out_dir = "packet_lab/out/frontend"

# Download vue-business JS (contains flow-control framework)
js_files = [
    "common/npm/topnet/vue-business~76eadadb.js",
]

for js_path in js_files:
    url = f"{base}/{js_path}"
    print(f"Downloading {js_path}...")
    try:
        r = session.get(url, headers=headers, verify=False, timeout=30)
        if r.status_code == 200:
            local_path = os.path.join(out_dir, js_path.split("/")[-1])
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(r.text)
            print(f"  Saved: {local_path} ({len(r.text)} chars)")
            
            # Search for producePdf and trigger:auto
            for pat in ["producePdf", "trigger", "auto", "flow-control", "flowControl", "fc.save", "handleNext", "noAutoNav"]:
                count = r.text.count(pat)
                if count > 0:
                    print(f"  '{pat}' found {count} times")
        else:
            print(f"  Failed: status={r.status_code}")
    except Exception as e:
        print(f"  Error: {e}")
