"""Navigate to 9087 SSO entservice endpoint to get Authorization token."""
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

# Enable network monitoring
send_cdp("Network.enable")
_events.clear()

# Navigate to the SSO entservice endpoint
sso_url = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/sso/entservice?targetUrlKey=02_0002"
print(f"=== Navigating to: {sso_url} ===")
send_cdp("Page.navigate", {"url": sso_url})

for i in range(20):
    time.sleep(2)
    
    # Check redirects in network events
    for evt in _events:
        method = evt.get("method", "")
        if method == "Network.requestWillBeSent":
            req = evt.get("params", {})
            url = req.get("request", {}).get("url", "")
            redirect_resp = req.get("redirectResponse")
            if redirect_resp:
                status = redirect_resp.get("status", 0)
                loc = redirect_resp.get("headers", {}).get("Location", redirect_resp.get("headers", {}).get("location", ""))
                print(f"  REDIRECT {status}: {url[:80]}")
                print(f"    Location: {loc[:120]}")
    _events.clear()
    
    try:
        href = ev("location.href")
        auth = ev("localStorage.getItem('Authorization') || ''")
    except:
        print(f"  [{i+1}] (loading...)")
        continue
    
    print(f"  [{i+1}] URL: {href[:80]} auth={'YES:'+auth[:20] if auth else 'none'}")
    
    # Check if Authorization was set via URL param
    if "Authorization=" in str(href):
        import re
        m = re.search(r'Authorization=([^&]+)', href)
        if m:
            url_auth = m.group(1)
            print(f"    AUTH IN URL: {url_auth[:30]}...")
    
    if auth and "9087" in str(href):
        print(f"\n>>> SUCCESS! Auth={auth[:30]}...")
        # Verify it works
        import urllib3; urllib3.disable_warnings()
        r = requests.get(
            "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/v4/pc/manager/usermanager/getUserInfo",
            headers={"Authorization": auth, "language": "CH"},
            verify=False, timeout=10
        )
        print(f"getUserInfo: {r.status_code} → {r.text[:200]}")
        
        # Save
        out = Path("g:/UFO/政务平台/packet_lab/out/runtime_auth_headers.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "headers": {
                "Authorization": auth,
                "top-token": auth,
                "language": "CH",
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://zhjg.scjdglj.gxzf.gov.cn:9087",
                "Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html",
            },
            "ts": int(time.time()),
            "source": "sso_entservice",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Token saved!")
        break
    
    if "tyrz" in str(href):
        print("  → Redirected to tyrz SSO!")
        break

ws.close()
