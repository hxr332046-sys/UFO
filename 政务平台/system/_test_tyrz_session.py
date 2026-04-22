"""Test if tyrz OAuth2 authorize can auto-redirect with existing session."""
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

# Test 1: Try OAuth2 authorize endpoint directly
oauth2_url = "https://tyrz.zwfw.gxzf.gov.cn/am/oauth2/authorize?service=initService&client_id=zrythxt&redirect_uri=https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/sso/oauth2?authType=zwfw_guangxi&response_type=code&scope=uid+cn+sn+mail&tokenType=JWT"
print(f"=== Test 1: OAuth2 authorize ===")
_events.clear()
send_cdp("Page.navigate", {"url": oauth2_url})
time.sleep(8)

# Check redirects
for evt in _events:
    if evt.get("method") == "Network.requestWillBeSent":
        req = evt.get("params", {})
        rr = req.get("redirectResponse")
        if rr:
            url = req.get("request", {}).get("url", "")
            status = rr.get("status", 0)
            print(f"  REDIRECT {status} → {url[:100]}")
_events.clear()

href = ev("location.href")
print(f"Landed: {href[:100]}")

# Check if 6087 cookies got set
cookies = send_cdp("Network.getCookies", {"urls": ["https://zhjg.scjdglj.gxzf.gov.cn:6087", "https://zhjg.scjdglj.gxzf.gov.cn"]})
clist = cookies.get("cookies", [])
print(f"\n6087 cookies ({len(clist)}):")
for c in clist:
    print(f"  {c.get('name')}={c.get('value','')[:30]} domain={c.get('domain')} httpOnly={c.get('httpOnly')}")

# If we're on 6087, try SSO entservice
if ":6087" in str(href):
    print("\n=== On 6087! Trying SSO entservice ===")
    send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/sso/entservice?targetUrlKey=02_0002"})
    time.sleep(8)
    href2 = ev("location.href")
    auth = ev("localStorage.getItem('Authorization') || ''")
    print(f"After entservice: {href2[:80]}")
    print(f"Auth: {auth[:30] if auth else 'none'}")
elif "ssc.mohrss" in str(href):
    print("\n=== Stuck on ssc ===")
    # Check ssc page content
    body = ev("document.body ? document.body.innerText.substring(0, 500) : ''")
    print(f"ssc body: {body[:300]}")
    # Check for forms or redirects
    forms = ev("document.forms.length")
    meta_refresh = ev("document.querySelector('meta[http-equiv=refresh]') ? document.querySelector('meta[http-equiv=refresh]').content : 'none'")
    print(f"Forms: {forms}, meta-refresh: {meta_refresh}")
    
    # Try navigating to 6087 portal directly
    print("\n=== Try 6087 portal directly ===")
    send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"})
    time.sleep(5)
    href3 = ev("location.href")
    top_token = ev("localStorage.getItem('top-token') || ''")
    print(f"6087 portal: {href3[:80]}")
    print(f"top-token: {top_token[:30] if top_token else 'none'}")
elif "tyrz" in str(href):
    print("\n=== Still on tyrz - session not valid for OAuth2 ===")
    has_form = ev("!!document.querySelector('#username, .form_button')")
    print(f"Has login form: {has_form}")

ws.close()
