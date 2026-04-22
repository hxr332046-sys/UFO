"""Set token in 9087 localStorage, navigate, and watch what happens."""
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

# Get 6087 token
href = ev("location.href")
if "6087" not in str(href):
    send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"})
    time.sleep(3)
top_token = ev("localStorage.getItem('top-token') || ''")
print(f"6087 top-token: {top_token}")

# Navigate to 9087 about:blank first to set localStorage on 9087 origin
print("\n=== Setting up 9087 localStorage ===")
send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"})
time.sleep(2)

# Wait for origin to be 9087
for _ in range(5):
    origin = ev("location.origin")
    if "9087" in str(origin):
        break
    time.sleep(1)

# Set the token BEFORE the SPA router runs
ev(f"localStorage.setItem('Authorization', '{top_token}')")
ev(f"localStorage.setItem('top-token', '{top_token}')")
print(f"Set Authorization={top_token}")

# Now enable network monitoring and navigate to enterprise-zone
send_cdp("Network.enable")
_events.clear()

print("\n=== Navigating to enterprise-zone ===")
# Use location.replace to trigger full SPA reinit
ev("window.location.replace('https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone')")
time.sleep(8)

# Collect results
api_calls = []
for evt in _events:
    method = evt.get("method", "")
    if method == "Network.requestWillBeSent":
        req = evt.get("params", {})
        url = req.get("request", {}).get("url", "")
        req_method = req.get("request", {}).get("method", "GET")
        if not url.endswith(('.js', '.css', '.png', '.jpg', '.svg', '.woff', '.woff2', '.ttf', '.ico', '.gif')):
            headers = req.get("request", {}).get("headers", {})
            api_calls.append(f"  REQ {req_method} {url[:100]} Auth={headers.get('Authorization','')[:20]}")
    elif method == "Network.responseReceived":
        resp = evt.get("params", {}).get("response", {})
        url = resp.get("url", "")
        status = resp.get("status", 0)
        if not url.endswith(('.js', '.css', '.png', '.jpg', '.svg', '.woff', '.woff2', '.ttf', '.ico', '.gif')):
            api_calls.append(f"  RESP {status} {url[:100]}")

print(f"\nNetwork events ({len(api_calls)}):")
for a in api_calls:
    print(a)

# Check final state
try:
    final_href = ev("location.href")
    final_auth = ev("localStorage.getItem('Authorization') || ''")
    print(f"\nFinal URL: {final_href[:80]}")
    print(f"Final Auth: {final_auth[:36] if final_auth else 'none'}")
except:
    print("Could not check final state")

# Check if SPA made XHR calls
xhr_log = ev("""(function(){
    // Intercept future XHRs
    if (!window._xhrLog) {
        window._xhrLog = [];
        var origOpen = XMLHttpRequest.prototype.open;
        var origSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.open = function(method, url) {
            this._logUrl = url;
            this._logMethod = method;
            return origOpen.apply(this, arguments);
        };
        XMLHttpRequest.prototype.send = function() {
            window._xhrLog.push({method: this._logMethod, url: this._logUrl, time: Date.now()});
            return origSend.apply(this, arguments);
        };
    }
    return window._xhrLog;
})()""")
print(f"\nXHR log: {json.dumps(xhr_log, ensure_ascii=False)[:500]}")

ws.close()
