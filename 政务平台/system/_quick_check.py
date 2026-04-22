"""Quick check: navigate to 6087, check session, try entservice."""
import json, time, requests, websocket

port = 9225
pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
target = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=30)
_id = [0]
_events = []
def send_cdp(method, params=None):
    _id[0] += 1
    ws.send(json.dumps({"id": _id[0], "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("method"):
            _events.append(msg)
        if msg.get("id") == _id[0]:
            return msg.get("result", {})
def ev(expr):
    r = send_cdp("Runtime.evaluate", {"expression": expr, "returnByValue": True, "timeout": 20000})
    return r.get("result", {}).get("value")

send_cdp("Network.enable")

# Navigate to 6087 portal
print("=== Navigate to 6087 ===")
send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"})
time.sleep(5)

href = ev("location.href")
print(f"URL: {href[:80]}")

# Check 6087 state
top_token = ev("localStorage.getItem('top-token') || ''")
user_name = ev("""(function(){
    try {
        var app = document.getElementById('app');
        if (!app || !app.__vue__) return '';
        var vm = app.__vue__;
        function find(v) {
            if (v.$store && v.$store.state) {
                var login = v.$store.state.login || {};
                return login.userInfo ? JSON.stringify(login.userInfo).substring(0, 100) : '';
            }
            for (var i = 0; i < (v.$children||[]).length; i++) {
                var r = find(v.$children[i]);
                if (r) return r;
            }
            return '';
        }
        return find(vm);
    } catch(e) { return 'error: ' + e.message; }
})()""")
print(f"top-token: {top_token[:30] if top_token else 'none'}")
print(f"userInfo: {user_name}")

# Check ALL cookies
cookies = send_cdp("Network.getCookies", {"urls": [
    "https://zhjg.scjdglj.gxzf.gov.cn:6087",
    "https://zhjg.scjdglj.gxzf.gov.cn:9087",
    "https://zhjg.scjdglj.gxzf.gov.cn",
    "https://tyrz.zwfw.gxzf.gov.cn",
]})
print(f"\nAll cookies ({len(cookies.get('cookies', []))}):")
for c in cookies.get("cookies", []):
    print(f"  {c.get('name')}={c.get('value','')[:30]} domain={c.get('domain')} httpOnly={c.get('httpOnly')}")

# If 6087 has a session, try entservice
if top_token or ":6087" in str(href):
    print("\n=== Trying SSO entservice ===")
    _events.clear()
    send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/sso/entservice?targetUrlKey=02_0002"})
    time.sleep(8)
    
    for evt in _events:
        if evt.get("method") == "Network.requestWillBeSent":
            req = evt.get("params", {})
            rr = req.get("redirectResponse")
            if rr:
                url = req.get("request", {}).get("url", "")
                status = rr.get("status", 0)
                print(f"  REDIRECT {status} → {url[:100]}")
    
    href2 = ev("location.href")
    auth = ev("localStorage.getItem('Authorization') || ''")
    print(f"After entservice: {href2[:80]}")
    print(f"Auth: {auth[:30] if auth else 'none'}")

ws.close()
