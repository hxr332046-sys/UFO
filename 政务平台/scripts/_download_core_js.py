"""Download and search core JS files for producePdf."""
import re, json, sys
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
session = client.s
headers = client._headers()

base = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc"
out_dir = "packet_lab/out/frontend"
os.makedirs(out_dir, exist_ok=True)

# Download the core JS files that likely contain producePdf
core_js_files = [
    "core/js/core~40cc254d.js",  # Known to contain producePdf
    "core/js/core~002699c4.js",
    "core/js/core~25b9f56b.js",
    "core/js/core~67d7b2e2.js",
    "core/js/core~0c65a408.js",
    "core/js/vendors~core~253ae210.js",
]

for js_path in core_js_files:
    url = f"{base}/{js_path}"
    print(f"Downloading {js_path}...")
    try:
        r = session.get(url, headers=headers, verify=False, timeout=30)
        if r.status_code == 200:
            local_path = os.path.join(out_dir, js_path.split("/")[-1])
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(r.text)
            print(f"  Saved: {local_path} ({len(r.text)} chars)")
            
            # Search for producePdf
            if "producePdf" in r.text:
                print(f"  ★★★ FOUND producePdf! ★★★")
                # Find all occurrences with context
                for m in re.finditer(r'.{0,200}producePdf.{0,200}', r.text):
                    ctx = m.group()
                    print(f"  Context: ...{ctx}...")
                    print()
        else:
            print(f"  Failed: status={r.status_code}")
    except Exception as e:
        print(f"  Error: {e}")

# Also search for related keywords in all downloaded files
print("\n=== Searching all downloaded JS for key patterns ===")
for fname in os.listdir(out_dir):
    if fname.endswith(".js"):
        fpath = os.path.join(out_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        
        patterns = ["producePdf", "YbbSelect", "isSelectYbb", "preSubmit", "linkData.token",
                     "customError", "flowControl", "fc.save", "handleNext"]
        for pat in patterns:
            if pat in content:
                count = content.count(pat)
                print(f"  {fname}: '{pat}' found {count} times")
