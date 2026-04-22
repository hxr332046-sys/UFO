"""Login with Fetch interception - redirect ssc to 6087 portal."""
import json, time, requests, websocket, sys, base64
from pathlib import Path

sys.path.insert(0, "g:/UFO/政务平台/system")

port = 9225
pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
target = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=60)
_id = [0]
intercepted_ssc = [False]

def raw_send(method, params=None):
    _id[0] += 1
    mid = _id[0]
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        # Handle Fetch.requestPaused events inline
        if msg.get("method") == "Fetch.requestPaused":
            req = msg.get("params", {})
            url = req.get("request", {}).get("url", "")
            req_id = req.get("requestId", "")
            if "ssc.mohrss" in url:
                intercepted_ssc[0] = True
                print(f"  >>> INTERCEPTED ssc: {url[:80]}")
                # Redirect to 6087 portal
                _id[0] += 1
                ws.send(json.dumps({
                    "id": _id[0],
                    "method": "Fetch.fulfillRequest",
                    "params": {
                        "requestId": req_id,
                        "responseCode": 302,
                        "responseHeaders": [
                            {"name": "Location", "value": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"}
                        ],
                        "body": ""
                    }
                }))
            else:
                _id[0] += 1
                ws.send(json.dumps({
                    "id": _id[0],
                    "method": "Fetch.continueRequest",
                    "params": {"requestId": req_id}
                }))
            continue
        if msg.get("id") == mid:
            return msg.get("result", {})

def ev(expr):
    r = raw_send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "timeout": 20000})
    return r.get("result", {}).get("value")

# Import slider
from cdp_auto_slider_login import CDPSession, auto_slide

# Clear all auth
raw_send("Network.enable")
all_c = raw_send("Network.getAllCookies")
for c in all_c.get("cookies", []):
    if "scjdglj" in c.get("domain", "") or "zwfw" in c.get("domain", ""):
        raw_send("Network.deleteCookies", {"name": c["name"], "domain": c["domain"], "path": c.get("path", "/")})

raw_send("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html"})
time.sleep(2)
ev("localStorage.clear()")
raw_send("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"})
time.sleep(2)
ev("localStorage.clear()")
print("Cleared all auth")

# Navigate to tyrz
raw_send("Page.navigate", {"url": "about:blank"})
time.sleep(1)
raw_send("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone"})
for i in range(15):
    time.sleep(3)
    href = ev("location.href") or ""
    if "tyrz" in href:
        print("At tyrz")
        break

# Login with a separate CDPSession for slider
ws.close()
cdp = CDPSession(target["webSocketDebuggerUrl"], timeout=60)
creds = json.loads(Path("g:/UFO/政务平台/config/credentials.json").read_text(encoding="utf-8"))

cdp.evaluate("""(function(){
    var u = document.querySelector('#username');
    if (!u) { var inputs = document.querySelectorAll('input'); for(var i=0;i<inputs.length;i++) if(inputs[i].type==='text'&&inputs[i].offsetParent) {u=inputs[i];break;} }
    if (u) { u.focus(); u.value=''; u.dispatchEvent(new Event('input',{bubbles:true})); }
})()""")
time.sleep(0.3)
cdp.type_text(creds["username"], delay_ms=30)
time.sleep(0.5)
cdp.evaluate("""(function(){
    var p = document.querySelector('#password');
    if (!p) { var inputs = document.querySelectorAll('input[type="password"]'); for(var i=0;i<inputs.length;i++) if(inputs[i].offsetParent) {p=inputs[i];break;} }
    if (p) { p.focus(); p.value=''; p.dispatchEvent(new Event('input',{bubbles:true})); }
})()""")
time.sleep(0.3)
cdp.type_text(creds["password"], delay_ms=30)
time.sleep(0.5)

ok = auto_slide(cdp, max_attempts=5)
print(f"Slider: {ok}")
if not ok:
    cdp.close()
    exit(1)

# Close CDPSession, reopen raw WS with Fetch interception
cdp.close()
time.sleep(0.5)

# Reconnect
ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=60)
_id[0] = 100

# Enable Fetch to intercept ssc redirects
raw_send("Fetch.enable", {
    "patterns": [
        {"urlPattern": "*ssc.mohrss.gov.cn*", "requestStage": "Request"},
    ]
})
print("\nFetch interception enabled. Clicking login...")

# Click login button via JS (since we can't use CDPSession click)
ev("""(function(){
    var btn = document.querySelector('.form_button');
    if (!btn) btn = document.querySelector('button[type="submit"]');
    if (btn) btn.click();
    return btn ? 'clicked' : 'not found';
})()""")

# Wait for interception - keep reading events 
print("Waiting for ssc interception...")
deadline = time.time() + 40
while time.time() < deadline:
    ws.settimeout(5)
    try:
        msg = json.loads(ws.recv())
        if msg.get("method") == "Fetch.requestPaused":
            req = msg.get("params", {})
            url = req.get("request", {}).get("url", "")
            req_id = req.get("requestId", "")
            if "ssc.mohrss" in url:
                intercepted_ssc[0] = True
                print(f"  >>> INTERCEPTED: {url[:80]}")
                # Redirect to 6087 portal
                _id[0] += 1
                ws.send(json.dumps({
                    "id": _id[0],
                    "method": "Fetch.fulfillRequest",
                    "params": {
                        "requestId": req_id,
                        "responseCode": 302,
                        "responseHeaders": [
                            {"name": "Location", "value": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"}
                        ],
                        "body": ""
                    }
                }))
                break
            else:
                _id[0] += 1
                ws.send(json.dumps({
                    "id": _id[0],
                    "method": "Fetch.continueRequest",
                    "params": {"requestId": req_id}
                }))
    except websocket.WebSocketTimeoutException:
        continue
    except Exception as e:
        print(f"Error: {e}")
        break

# Disable Fetch
try:
    raw_send("Fetch.disable")
except:
    pass

time.sleep(8)

# Check state
href = ev("location.href") or ""
print(f"\nURL: {href[:80]}")

# Check cookies
all_c = raw_send("Network.getAllCookies")
sessions = [c for c in all_c.get("cookies", []) if c.get("name") == "SESSION" and "scjdglj" in c.get("domain", "")]
print(f"SESSION cookies: {len(sessions)}")
for sc in sessions:
    print(f"  {sc['name']}={sc['value'][:25]} path={sc.get('path','/')}")

top_token = ev("localStorage.getItem('top-token') || ''") or ""
print(f"top-token: {top_token[:30] if top_token else 'none'}")

# Try entservice
if sessions:
    print("\n=== SSO entservice ===")
    raw_send("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/sso/entservice?targetUrlKey=02_0002"})
    time.sleep(10)
    href2 = ev("location.href") or ""
    auth = ev("localStorage.getItem('Authorization') || ''") or ""
    print(f"URL: {href2[:80]}")
    print(f"Auth: {auth[:30] if auth else 'none'}")
    if auth and len(auth) >= 16:
        print(f"\n>>> SUCCESS! Token: {auth}")

ws.close()
