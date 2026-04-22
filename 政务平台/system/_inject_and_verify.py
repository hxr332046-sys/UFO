"""Inject 6087 top-token into 9087 localStorage and verify."""
import json, time, requests, websocket

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

# Step 1: Get to 6087 and read top-token
href = ev("location.href")
if "6087" not in str(href):
    send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"})
    time.sleep(3)

top_token = ev("localStorage.getItem('top-token') || ''")
print(f"6087 top-token: {top_token}")
if not top_token:
    print("No top-token on 6087!")
    ws.close()
    exit(1)

# Step 2: Navigate to 9087
print("\nNavigating to 9087...")
send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/login/authPage"})
time.sleep(3)

# Step 3: Inject the token
print(f"Injecting Authorization={top_token}")
ev(f"""(function(){{
    localStorage.setItem('Authorization', '{top_token}');
    localStorage.setItem('top-token', '{top_token}');
}})()""")
time.sleep(0.5)

# Verify injection
auth = ev("localStorage.getItem('Authorization')")
print(f"Verify: Authorization = {auth}")

# Step 4: Navigate to enterprise-zone
print("\nNavigating to enterprise-zone...")
ev('window.location.replace("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone")')
time.sleep(5)

# Step 5: Check result
for i in range(10):
    href = ev("location.href")
    auth = ev("localStorage.getItem('Authorization') || ''")
    body = ev("(document.body && document.body.innerText || '').substring(0, 300)")
    print(f"\n[{i+1}] URL: {href[:80]}")
    print(f"  Auth: {auth[:30] if auth else '(empty)'}")
    print(f"  Body: {body[:100] if body else '(empty)'}")
    
    if "enterprise" in str(href) and auth and "登录" not in str(body)[:50]:
        print("\n>>> SUCCESS! Logged in on 9087!")
        # Save token
        from pathlib import Path
        import json as j
        out = Path("g:/UFO/政务平台/packet_lab/out/runtime_auth_headers.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(j.dumps({
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
            "source": "cdp_auto_slider_login (6087→9087 inject)",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Token saved to {out}")
        break
    
    if "tyrz" in str(href):
        print("  Redirected to tyrz! Token might be invalid")
        break
    
    time.sleep(3)

ws.close()
