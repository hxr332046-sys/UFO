"""Download and search tools JS for flow-control logic."""
import sys, re, os
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
session = client.s
headers = client._headers()
base = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc"
out_dir = "packet_lab/out/frontend"

# Download tools JS
js_files = [
    "common/npm/topnet/tools~6ad69f03.js",
    "common/npm/topnet/vue-element~fa510715.js",
    "common/npm/topnet/outer-style~021312b9.js",
    "common/npm/topnet/vue-sign~bb0a325e.js",
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
            print(f"  Saved ({len(r.text)} chars)")
            
            for pat in ["producePdf", "noAutoNav", "autoNav", "trigger.*auto", "flowControl", "fc.save", "handleAutoBtn"]:
                count = len(re.findall(pat, content if 'content' in dir() else ''))
            # Search in downloaded content
            with open(local_path, "r", encoding="utf-8") as f:
                c = f.read()
            for pat in ["producePdf", "noAutoNav", "autoNav", "trigger", "flowControl", "fc.save", "autoBtn", "autoEvent"]:
                count = c.count(pat)
                if count > 0:
                    print(f"  '{pat}' found {count} times")
    except Exception as e:
        print(f"  Error: {e}")

# Now search ALL files for noAutoNav
print("\n\n=== Searching ALL files for noAutoNav ===")
for fname in sorted(os.listdir(out_dir)):
    if not fname.endswith(".js"):
        continue
    fpath = os.path.join(out_dir, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        c = f.read()
    for pat in ["noAutoNav", "autoNav", "autoNext", "autoAdvance", "autoTrigger", "autoFlow"]:
        count = c.count(pat)
        if count > 0:
            print(f"{fname}: '{pat}' found {count} times")
