"""Intercept 9087 network traffic to find the auth token exchange API."""
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

# Get 6087 top-token first
href = ev("location.href")
if "6087" not in str(href):
    send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"})
    time.sleep(3)
top_token = ev("localStorage.getItem('top-token') || ''")
print(f"6087 top-token: {top_token}")

# Navigate to 9087 and enable network monitoring
print("\n=== Navigating to 9087 with network interception ===")
send_cdp("Network.enable")
_events.clear()

# Navigate to 9087 portal.html#/login/authPage (the login/auth page)
send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/login/authPage"})

# Collect all network requests for 10 seconds
print("Monitoring network for 10 seconds...")
time.sleep(10)

# Analyze collected events
api_calls = []
for evt in _events:
    method = evt.get("method", "")
    if method == "Network.requestWillBeSent":
        req = evt.get("params", {})
        url = req.get("request", {}).get("url", "")
        req_method = req.get("request", {}).get("method", "GET")
        headers = req.get("request", {}).get("headers", {})
        if "icpsp-api" in url or "TopIP" in url or "sso" in url.lower():
            api_calls.append({
                "url": url[:120],
                "method": req_method,
                "auth": headers.get("Authorization", headers.get("token", ""))[:30],
                "requestId": req.get("requestId", ""),
            })
    elif method == "Network.responseReceived":
        resp = evt.get("params", {}).get("response", {})
        url = resp.get("url", "")
        status = resp.get("status", 0)
        if "icpsp-api" in url or "TopIP" in url or "sso" in url.lower():
            api_calls.append({
                "url": url[:120],
                "status": status,
                "requestId": evt.get("params", {}).get("requestId", ""),
            })

print(f"\nCaptured {len(api_calls)} API events:")
for a in api_calls:
    print(f"  {json.dumps(a)}")

# Check ALL network requests (not just API)
all_requests = []
for evt in _events:
    if evt.get("method") == "Network.requestWillBeSent":
        url = evt.get("params", {}).get("request", {}).get("url", "")
        if not url.endswith(('.js', '.css', '.png', '.jpg', '.svg', '.woff', '.woff2', '.ttf', '.ico')):
            req_method = evt.get("params", {}).get("request", {}).get("method", "GET")
            all_requests.append(f"  {req_method} {url[:100]}")

print(f"\nAll non-static requests ({len(all_requests)}):")
for r in all_requests:
    print(r)

# Also check: what URL did the page redirect to?
try:
    final_href = ev("location.href")
    print(f"\nFinal URL: {final_href[:100]}")
except:
    print("\nCouldn't get final URL")

# Check cookies via CDP
cookies = send_cdp("Network.getCookies", {"urls": [
    "https://zhjg.scjdglj.gxzf.gov.cn:9087",
    "https://zhjg.scjdglj.gxzf.gov.cn:6087",
    "https://zhjg.scjdglj.gxzf.gov.cn",
]})
print(f"\nAll cookies ({len(cookies.get('cookies', []))}):")
for c in cookies.get("cookies", []):
    print(f"  {c.get('name')}={c.get('value','')[:40]} domain={c.get('domain')} path={c.get('path')} httpOnly={c.get('httpOnly')} secure={c.get('secure')}")

ws.close()
