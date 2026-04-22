"""Find 9087 ICPSP portal's SSO/auth mechanism from its JavaScript source."""
import json, time, requests, websocket, re

port = 9225
pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
target = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=30)
_id = [0]
def send_cdp(method, params=None):
    _id[0] += 1
    ws.send(json.dumps({"id": _id[0], "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == _id[0]:
            return msg.get("result", {})
def ev(expr):
    r = send_cdp("Runtime.evaluate", {"expression": expr, "returnByValue": True, "timeout": 20000})
    return r.get("result", {}).get("value")

# Navigate to 9087 first
send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"})
time.sleep(3)

# Find all script tags
print("=== Script files on 9087 ===")
scripts = ev("""(function(){
    var scripts = document.querySelectorAll('script[src]');
    var result = [];
    for (var i = 0; i < scripts.length; i++) {
        result.push(scripts[i].src);
    }
    return result;
})()""")
for s in (scripts or []):
    print(f"  {s}")

# Look for main chunk/vendor files
print("\n=== Looking for auth-related code in loaded scripts ===")
auth_code = ev("""(function(){
    var result = [];
    // Search in all loaded script content for auth/login/sso patterns
    // Check performance entries for script URLs
    var entries = performance.getEntriesByType('resource');
    var jsUrls = [];
    for (var i = 0; i < entries.length; i++) {
        if (entries[i].initiatorType === 'script' || entries[i].name.endsWith('.js')) {
            jsUrls.push(entries[i].name);
        }
    }
    return jsUrls.slice(0, 20);
})()""")
for s in (auth_code or []):
    print(f"  {s}")

ws.close()

# Now fetch the main JS file and search for auth patterns
print("\n=== Searching main JS for auth/SSO logic ===")
import urllib3
urllib3.disable_warnings()

if scripts:
    # Look for app/chunk JS files
    for script_url in scripts:
        if 'app' in script_url.lower() or 'chunk' in script_url.lower() or 'index' in script_url.lower():
            try:
                r = requests.get(script_url, timeout=10, verify=False)
                js = r.text
                
                # Search for auth-related patterns
                patterns = [
                    r'Authorization["\']?\s*[,:=]',
                    r'top-token',
                    r'sso|SSO',
                    r'6087',
                    r'TopIP',
                    r'login\.redirect|authPage|loginUrl',
                    r'window\.location\s*[.=].*6087',
                    r'getToken|setToken|removeToken',
                ]
                
                for pat in patterns:
                    matches = list(re.finditer(pat, js))
                    if matches:
                        for m in matches[:3]:
                            start = max(0, m.start() - 80)
                            end = min(len(js), m.end() + 80)
                            context = js[start:end].replace('\n', ' ').strip()
                            print(f"\n  [{pat}] in {script_url.split('/')[-1][:30]}:")
                            print(f"    ...{context}...")
            except Exception as e:
                print(f"  Error fetching {script_url[:60]}: {e}")
