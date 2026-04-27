"""Fetch and analyze the frontend JS to understand producePdf flow."""
import sys, re
sys.path.insert(0, 'system')
from login_qrcode_pure_http import ensure_token
from icpsp_api_client import ICPSPClient

client = ICPSPClient()

# Try to fetch the core JS file that contains producePdf
# The JS filename pattern is core~hash.js
# First, let's try to find it from the main page HTML
import requests

# Get the main page HTML
base_url = "https://zhjg.scjdglj.gxzf.gov.cn"
session = client.s  # reuse the authenticated session

# Try fetching the index page to find JS references
try:
    r = session.get(f"{base_url}/", verify=False, timeout=10)
    print(f"Core page status: {r.status_code}")
    print(f"HTML length: {len(r.text)}")
    # Print first 2000 chars
    print(r.text[:2000])
except Exception as e:
    print(f"Error: {e}")

# Try direct URL patterns for the core JS
for hash_suffix in ["40cc254d", ""]:
    url = f"{base_url}/static/js/core~{hash_suffix}.js" if hash_suffix else f"{base_url}/static/js/core.js"
    try:
        r = session.get(url, verify=False, timeout=10)
        if r.status_code == 200:
            print(f"\nFound JS at {url} ({len(r.text)} chars)")
            # Search for producePdf
            idx = r.text.find("producePdf")
            if idx >= 0:
                # Get surrounding context
                start = max(0, idx - 500)
                end = min(len(r.text), idx + 500)
                print(f"producePdf context: ...{r.text[start:end]}...")
            break
    except Exception as e:
        print(f"  {url}: {e}")
