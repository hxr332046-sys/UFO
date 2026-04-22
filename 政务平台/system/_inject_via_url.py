"""Navigate to 9087 with Authorization in URL query parameter."""
import json, time, requests, websocket
from pathlib import Path

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

# Get 6087 top-token
href = ev("location.href")
if "6087" not in str(href):
    send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"})
    time.sleep(4)

top_token = ev("localStorage.getItem('top-token') || ''")
print(f"6087 top-token: {top_token}")

if not top_token:
    print("ERROR: no top-token!")
    ws.close()
    exit(1)

# Navigate to 9087 with Authorization in hash query
# The SPA reads from $route.query.Authorization
url = f"https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone?Authorization={top_token}"
print(f"\nNavigating to: {url[:100]}...")
send_cdp("Page.navigate", {"url": url})
time.sleep(6)

for i in range(15):
    try:
        href = ev("location.href")
        auth = ev("localStorage.getItem('Authorization') || ''")
        body = ev("(document.body && document.body.innerText || '').substring(0, 200)")
    except:
        print(f"  [{i+1}] (loading...)")
        time.sleep(2)
        continue
    
    is_ent = "enterprise" in str(href)
    has_auth = bool(auth) and len(auth) > 10
    print(f"  [{i+1}] enterprise={is_ent} auth={auth[:30] if auth else 'none'}")
    
    if has_auth and is_ent:
        print(f"\n>>> SUCCESS! Auth={auth}")
        print(f"Body preview: {body[:150]}")
        # Save token
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
            "source": "cdp_auto_slider_login (url inject)",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Token saved to {out}")
        break
    
    if "tyrz" in str(href):
        print("  Redirected to tyrz - token not accepted")
        break
    
    if "6087" in str(href):
        print(f"  Redirected to 6087 - SSO redirect")
        break
    
    time.sleep(3)

ws.close()
