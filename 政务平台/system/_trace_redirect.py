"""Precisely trace the SSO redirect chain to find where 6087 session breaks."""
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
_events.clear()

# Navigate to 6087 SSO endpoint - this should trigger the full chain
print("=== Navigate to 6087 SSO ===")
send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/sso/oauth2?authType=zwfw_guangxi"})

# Wait and collect all redirect events
time.sleep(12)

# Analyze all redirect events in order
print("\n=== Redirect chain ===")
redirect_chain = []
all_nav_requests = []
for evt in _events:
    method = evt.get("method", "")
    if method == "Network.requestWillBeSent":
        params = evt.get("params", {})
        url = params.get("request", {}).get("url", "")
        redirect_resp = params.get("redirectResponse")
        req_id = params.get("requestId", "")
        
        if redirect_resp:
            from_status = redirect_resp.get("status", 0)
            from_headers = redirect_resp.get("headers", {})
            location = from_headers.get("Location", from_headers.get("location", ""))
            set_cookie = from_headers.get("Set-Cookie", from_headers.get("set-cookie", ""))
            redirect_chain.append({
                "status": from_status,
                "to": url[:120],
                "location": location[:120],
                "set_cookie": set_cookie[:100] if set_cookie else "",
            })
        else:
            all_nav_requests.append(url[:120])
    
    elif method == "Network.responseReceived":
        params = evt.get("params", {})
        resp = params.get("response", {})
        url = resp.get("url", "")
        status = resp.get("status", 0)
        headers = resp.get("headers", {})
        set_cookie = headers.get("Set-Cookie", headers.get("set-cookie", ""))
        if set_cookie:
            print(f"  SET-COOKIE at {url[:60]}: {set_cookie[:80]}")

print(f"\nInitial requests ({len(all_nav_requests)}):")
for r in all_nav_requests:
    print(f"  → {r}")

print(f"\nRedirects ({len(redirect_chain)}):")
for i, r in enumerate(redirect_chain):
    print(f"  [{i+1}] {r['status']} → {r['to']}")
    if r['set_cookie']:
        print(f"       SET-COOKIE: {r['set_cookie']}")

# Final state
href = ev("location.href")
print(f"\nFinal URL: {href[:100]}")

# Check cookies now
cookies = send_cdp("Network.getCookies", {"urls": [
    "https://zhjg.scjdglj.gxzf.gov.cn:6087",
    "https://zhjg.scjdglj.gxzf.gov.cn:9087",
    "https://zhjg.scjdglj.gxzf.gov.cn",
    "https://tyrz.zwfw.gxzf.gov.cn",
]})
print(f"\nCookies ({len(cookies.get('cookies', []))}):")
for c in cookies.get("cookies", []):
    print(f"  {c['name']}={c['value'][:30]} domain={c['domain']} httpOnly={c['httpOnly']} path={c.get('path','/')}")

# Check if on tyrz login
if "tyrz" in str(href):
    has_form = ev("!!document.querySelector('#username, .form_button')")
    print(f"\ntyrz has login form: {has_form}")
    # If no form, tyrz might still be processing
    if not has_form:
        time.sleep(5)
        href2 = ev("location.href")
        print(f"After 5s: {href2[:100]}")

ws.close()
