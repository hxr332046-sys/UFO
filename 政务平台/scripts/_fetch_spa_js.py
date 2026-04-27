"""Download and analyze frontend JS to find producePdf call chain."""
import sys, re, os
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
session = client.s
headers = client._headers()

base = "https://zhjg.scjdglj.gxzf.gov.cn:9087"

# Step 1: Fetch the SPA HTML to find JS file references
print("=== Fetching SPA HTML ===")
r = session.get(f"{base}/icpsp-web-pc/core.html", headers=headers, verify=False, timeout=15)
print(f"Status: {r.status_code}, Length: {len(r.text)}")

if r.status_code == 200 and len(r.text) > 100:
    # Save HTML for reference
    os.makedirs("packet_lab/out/frontend", exist_ok=True)
    with open("packet_lab/out/frontend/core.html", "w", encoding="utf-8") as f:
        f.write(r.text)
    
    # Find all JS references
    js_refs = re.findall(r'src=["\']([^"\']*\.js)["\']', r.text)
    print(f"Found {len(js_refs)} JS references:")
    for ref in js_refs:
        print(f"  {ref}")
    
    # Also find CSS and other resources
    css_refs = re.findall(r'href=["\']([^"\']*\.css)["\']', r.text)
    print(f"Found {len(css_refs)} CSS references:")
    for ref in css_refs:
        print(f"  {ref}")
else:
    print(f"Failed to fetch SPA HTML: {r.text[:500]}")
    
    # Try alternative paths
    for alt_path in ["/icpsp-web-pc/", "/icpsp-web-pc/index.html", "/pc/core.html"]:
        r2 = session.get(f"{base}{alt_path}", headers=headers, verify=False, timeout=10, allow_redirects=False)
        print(f"  {alt_path}: status={r2.status_code} len={len(r2.text)}")
        if r2.status_code == 200 and len(r2.text) > 100:
            js_refs = re.findall(r'src=["\']([^"\']*\.js)["\']', r2.text)
            if js_refs:
                print(f"    JS refs: {js_refs[:5]}")
