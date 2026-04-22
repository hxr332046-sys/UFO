"""Navigate to 6087 SSO endpoint to get 9087 Authorization token via redirect."""
import json, time, requests, websocket
from pathlib import Path

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

# Step 1: Navigate to 6087 SSO endpoint with redirect back to 9087
# The SSO endpoint should: validate session → generate token → redirect to 9087
sso_url = "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/sso/oauth2?authType=zwfw_guangxi"
print(f"=== Navigating to 6087 SSO endpoint ===")
print(f"URL: {sso_url}")

send_cdp("Network.enable")
_events.clear()

send_cdp("Page.navigate", {"url": sso_url})

for i in range(20):
    time.sleep(2)
    try:
        href = ev("location.href")
    except:
        print(f"  [{i+1}] (redirecting...)")
        continue
    
    # Check for Authorization in URL
    auth_in_url = ""
    if "Authorization=" in str(href):
        import re
        m = re.search(r'Authorization=([^&]+)', str(href))
        if m:
            auth_in_url = m.group(1)
    
    # Check localStorage
    auth_ls = ""
    try:
        auth_ls = ev("localStorage.getItem('Authorization') || ''")
    except:
        pass
    
    print(f"  [{i+1}] {href[:80]}")
    if auth_in_url:
        print(f"    Auth in URL: {auth_in_url[:30]}...")
    if auth_ls:
        print(f"    Auth in localStorage: {auth_ls[:30]}...")
    
    if auth_ls and "9087" in str(href):
        print(f"\n>>> SUCCESS! 9087 with Auth={auth_ls[:30]}...")
        out = Path("g:/UFO/政务平台/packet_lab/out/runtime_auth_headers.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "headers": {
                "Authorization": auth_ls,
                "top-token": auth_ls,
                "language": "CH",
                "Content-Type": "application/json",
            }, "ts": int(time.time()), "source": "6087_sso_redirect"
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        break
    
    if "tyrz" in str(href):
        print("  → Redirected to tyrz (session expired)")
        break
    
    # Check network redirects
    for evt in _events[-30:]:
        method = evt.get("method", "")
        if method == "Network.requestWillBeSent":
            url = evt.get("params", {}).get("request", {}).get("url", "")
            rtype = evt.get("params", {}).get("type", "")
            redirectUrl = evt.get("params", {}).get("redirectResponse", {}).get("headers", {}).get("Location", "")
            if "9087" in url or "Authorization" in url or redirectUrl:
                print(f"    NET: {url[:80]} type={rtype}")
                if redirectUrl:
                    print(f"    REDIRECT: {redirectUrl[:80]}")
        elif method == "Network.responseReceived":
            resp = evt.get("params", {}).get("response", {})
            url = resp.get("url", "")
            status = resp.get("status", 0)
            if status in (301, 302, 303, 307) or "9087" in url:
                headers = resp.get("headers", {})
                loc = headers.get("Location", headers.get("location", ""))
                print(f"    RESP: {url[:60]} → {status} Location={loc[:60]}")
    _events.clear()

ws.close()
