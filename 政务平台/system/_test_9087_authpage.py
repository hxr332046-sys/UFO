"""After 6087 has tokens, navigate to 9087 authPage and check if it auto-picks up auth."""
import json, sys, time, requests, websocket

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

# First check current URL
href = ev("location.href")
print(f"Current: {href[:80]}")

# Enable network monitoring
send_cdp("Network.enable")
_events.clear()

# Navigate to 9087 authPage
print("\n=== Navigating to 9087 authPage ===")
send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/login/authPage"})

for i in range(20):
    time.sleep(2)
    try:
        href = ev("location.href")
        auth = ev("localStorage.getItem('Authorization') || ''")
    except:
        print(f"  [{i+1}] (redirecting)")
        continue
    
    print(f"  [{i+1}] {href[:80]} auth={auth[:20] if auth else '(empty)'}")
    
    if auth:
        print(f"\n>>> AUTH FOUND: {auth[:30]}... (len={len(auth)})")
        break
    
    if "tyrz" in str(href):
        print(f"  Redirected to tyrz - need to re-login")
        break
    
    # Check for XHR requests to interesting endpoints
    for evt in _events:
        if evt.get("method") == "Network.responseReceived":
            url = evt.get("params", {}).get("response", {}).get("url", "")
            status = evt.get("params", {}).get("response", {}).get("status", 0)
            if ("sso" in url.lower() or "auth" in url.lower() or "login" in url.lower() or "token" in url.lower()) and "6087" in url:
                print(f"    API: {url[:80]} → {status}")
    _events.clear()

# Also try: navigate to enterprise-zone directly  
if not auth:
    print("\n=== Trying enterprise-zone ===")
    send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone"})
    for i in range(10):
        time.sleep(2)
        try:
            href = ev("location.href")
            auth = ev("localStorage.getItem('Authorization') || ''")
        except:
            continue
        print(f"  [{i+1}] {href[:80]} auth={auth[:20] if auth else '(empty)'}")
        if auth:
            print(f"\n>>> AUTH FOUND: {auth[:30]}...")
            break

# Check cookies visible from 9087
print("\n=== 9087 Cookies (via CDP) ===")
cookies = send_cdp("Network.getCookies", {"urls": [
    "https://zhjg.scjdglj.gxzf.gov.cn:9087",
    "https://zhjg.scjdglj.gxzf.gov.cn:6087",
]})
for c in cookies.get("cookies", []):
    print(f"  {c.get('name')}={c.get('value','')[:40]} domain={c.get('domain')} httpOnly={c.get('httpOnly')}")

ws.close()
