"""Search 9087 JS files for SSO redirect URL construction."""
import requests, re, urllib3
urllib3.disable_warnings()

base = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc"

# Fetch port.js
r = requests.get(f"{base}/common/config/port.js", verify=False, timeout=10)
print("=== port.js ===")
print(r.text[:2000])

# Fetch the page JS and search for sso/redirect logic
for js_file in ["portal/js/page~21833f8f.js", "portal/js/index~31ecd969.js",
                "portal/js/vendors~portal~253ae210.js", "portal/js/portal~002699c4.js"]:
    try:
        r = requests.get(f"{base}/{js_file}", verify=False, timeout=10)
        js = r.text
        fname = js_file.split("/")[-1]
        
        # Search for redirect/sso URL construction
        patterns = [
            (r'sso/oauth2', 'sso/oauth2 ref'),
            (r'redirect[_u]ri|redirectUrl|callbackUrl|redirect_url', 'redirect URI'),
            (r'login\.path|loginPath|loginUrl', 'login path'),
            (r'window\.location\s*[=.]', 'window.location'),
            (r'window\.open', 'window.open'),
        ]
        
        for pat, label in patterns:
            matches = list(re.finditer(pat, js, re.IGNORECASE))
            if matches:
                print(f"\n[{fname}] {label}: {len(matches)} matches")
                for m in matches[:5]:
                    start = max(0, m.start() - 150)
                    end = min(len(js), m.end() + 150)
                    ctx = js[start:end].replace('\n', ' ').strip()
                    print(f"  ...{ctx}...")
    except Exception as e:
        print(f"\n{js_file}: ERROR {e}")

# Also check topnet npm packages
for f in ["common/npm/topnet/vue-business~76eadadb.js", "common/npm/topnet/tools~6ad69f03.js"]:
    try:
        r = requests.get(f"{base}/{f}", verify=False, timeout=10)
        js = r.text
        fname = f.split("/")[-1]
        for pat, label in [(r'sso/oauth2|login\.path', 'sso'), (r'redirect', 'redirect'),
                           (r'window\.location', 'location')]:
            matches = list(re.finditer(pat, js, re.IGNORECASE))
            if matches:
                print(f"\n[{fname}] {label}: {len(matches)} matches")
                for m in matches[:3]:
                    start = max(0, m.start() - 150)
                    end = min(len(js), m.end() + 150)
                    ctx = js[start:end].replace('\n', ' ')
                    print(f"  ...{ctx[:300]}...")
    except Exception as e:
        print(f"\n{f}: ERROR {e}")
