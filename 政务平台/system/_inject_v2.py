"""Inject token into 9087 then full-reload enterprise-zone."""
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

# Step 1: Get 6087 top-token
href = ev("location.href")
if "6087" not in str(href):
    send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"})
    time.sleep(3)
top_token = ev("localStorage.getItem('top-token') || ''")
print(f"6087 top-token: {top_token}")
if not top_token:
    print("ERROR: no top-token!")
    ws.close()
    exit(1)

# Step 2: Navigate to a MINIMAL 9087 page (avoid SPA routing)
# Use Page.navigate for a full navigation (not hash change)
print("\nNavigating to 9087 (minimal)...")
send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"})
time.sleep(3)

# Wait for origin to be 9087
for _ in range(5):
    h = ev("location.origin")
    if "9087" in str(h):
        break
    time.sleep(1)

# Step 3: Inject token into 9087 localStorage
print(f"Injecting into 9087 localStorage...")
ev(f"""(function(){{
    localStorage.setItem('Authorization', '{top_token}');
    localStorage.setItem('top-token', '{top_token}');
    return 'ok';
}})()""")

# Verify
auth = ev("localStorage.getItem('Authorization')")
print(f"9087 Authorization: {auth}")

# Step 4: Full-page navigation to enterprise-zone (with cache bust)
# Using Page.navigate forces a full page load, not SPA hash routing
ezone_url = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone"
print(f"\nFull-navigate to enterprise-zone...")
send_cdp("Page.navigate", {"url": ezone_url})
time.sleep(6)

# Step 5: Monitor result
for i in range(15):
    try:
        href = ev("location.href")
        auth = ev("localStorage.getItem('Authorization') || ''")
        body = ev("(document.body && document.body.innerText || '').substring(0, 200)")
    except:
        print(f"  [{i+1}] (loading...)")
        time.sleep(2)
        continue
    
    print(f"\n[{i+1}] URL: {href[:80]}")
    print(f"  Auth: {auth[:36] if auth else '(empty)'}")
    has_login_text = "登录" in str(body)[:50] if body else False
    has_enterprise = "经营主体" in str(body) or "企业" in str(body) if body else False
    print(f"  登录文字: {has_login_text}, 企业文字: {has_enterprise}")
    
    if "enterprise" in str(href) and auth and not has_login_text:
        print(f"\n>>> SUCCESS! Enterprise zone loaded with auth!")
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
            "source": "cdp_auto_slider_login",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Token saved to {out}")
        break
    
    if "tyrz" in str(href):
        print("  Redirected to SSO! Token not accepted by router guard.")
        break
    
    if "6087" in str(href):
        print("  Redirected to 6087!")
        break
    
    time.sleep(3)

ws.close()
