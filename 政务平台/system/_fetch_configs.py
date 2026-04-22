"""Fetch 9087 config files to find SSO auth mechanism."""
import requests, re
import urllib3
urllib3.disable_warnings()

base = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/common/config"
files = ["port.js", "envConfig.js", "header.js", "footer.js", "theme.js"]

for f in files:
    try:
        r = requests.get(f"{base}/{f}", timeout=10, verify=False)
        print(f"\n{'='*60}")
        print(f"=== {f} ({len(r.text)} bytes) ===")
        print(f"{'='*60}")
        print(r.text[:3000])
    except Exception as e:
        print(f"\n=== {f}: ERROR {e} ===")

# Also check the page JS files
page_base = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal/js"
# The key files
for f in ["index~31ecd969.js", "page~21833f8f.js"]:
    try:
        r = requests.get(f"{page_base}/{f}", timeout=10, verify=False)
        js = r.text
        print(f"\n{'='*60}")
        print(f"=== {f} ({len(js)} bytes) ===")
        # Search for auth/SSO patterns
        patterns = [
            (r'6087', 'Contains 6087'),
            (r'TopIP', 'Contains TopIP'),
            (r'ssoLogin|sso_login|ssoUrl|loginUrl', 'SSO login URL'),
            (r'Authorization', 'Authorization'),
            (r'top.token|top-token|topToken', 'top-token'),
            (r'getToken|setToken|removeToken', 'token functions'),
            (r'router\.beforeEach|beforeRouteEnter', 'router guards'),
            (r'window\.location.*=.*http', 'window.location redirect'),
        ]
        for pat, label in patterns:
            matches = list(re.finditer(pat, js, re.IGNORECASE))
            if matches:
                print(f"\n  [{label}] {len(matches)} matches:")
                for m in matches[:5]:
                    start = max(0, m.start() - 100)
                    end = min(len(js), m.end() + 100)
                    ctx = js[start:end].replace('\n', ' ')
                    print(f"    ...{ctx}...")
    except Exception as e:
        print(f"\n=== {f}: ERROR {e} ===")
