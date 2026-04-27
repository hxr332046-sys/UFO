"""Fetch frontend JS to analyze producePdf flow."""
import sys, re, requests
sys.path.insert(0, 'system')
from login_qrcode_pure_http import ensure_token
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
session = client.s
headers = client._headers()

base_url = "https://zhjg.scjdglj.gxzf.gov.cn"

# Try the SPA entry point
for path in ["/core.html", "/index.html", "/icpsp/", "/icpsp/core.html"]:
    try:
        r = session.get(f"{base_url}{path}", headers=headers, verify=False, timeout=10, allow_redirects=False)
        print(f"{path}: status={r.status_code} len={len(r.text)}")
        if r.status_code == 200 and len(r.text) > 100:
            # Find JS script references
            js_refs = re.findall(r'src=["\']([^"\']*\.js)["\']', r.text)
            print(f"  JS refs: {js_refs[:10]}")
            if not js_refs:
                print(f"  Content: {r.text[:500]}")
    except Exception as e:
        print(f"{path}: Error {e}")

# Try the icpsp-web context path
for path in ["/icpsp-web/core.html", "/icpsp-web/", "/register/core.html"]:
    try:
        r = session.get(f"{base_url}{path}", headers=headers, verify=False, timeout=10, allow_redirects=False)
        print(f"{path}: status={r.status_code} len={len(r.text)}")
    except Exception as e:
        print(f"{path}: Error {e}")

# The SPA URL from memory: core.html#/flow/base
# So the SPA is served from some static path. Let's try common Vue SPA paths
for path in ["/static/core.html", "/dist/core.html", "/pc/core.html", "/h5/core.html"]:
    try:
        r = session.get(f"{base_url}{path}", headers=headers, verify=False, timeout=10, allow_redirects=False)
        print(f"{path}: status={r.status_code} len={len(r.text)}")
        if r.status_code == 200 and len(r.text) > 100:
            js_refs = re.findall(r'src=["\']([^"\']*\.js)["\']', r.text)
            print(f"  JS refs: {js_refs[:10]}")
    except Exception as e:
        print(f"{path}: Error {e}")
