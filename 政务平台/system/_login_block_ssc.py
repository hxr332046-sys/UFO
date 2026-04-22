"""Login and block ssc.mohrss.gov.cn redirect - let 6087 session complete."""
import json, time, requests, websocket, sys, base64
from pathlib import Path

sys.path.insert(0, "g:/UFO/政务平台/system")
from cdp_auto_slider_login import CDPSession, auto_slide

port = 9225
pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
target = [p for p in pages if p.get("type") == "page"][0]
cdp = CDPSession(target["webSocketDebuggerUrl"])

# Clear all auth state
print("=== Clear auth ===")
cdp.send("Network.enable")
all_c = cdp.send("Network.getAllCookies")
for c in all_c.get("cookies", []):
    if "scjdglj" in c.get("domain", "") or "zwfw" in c.get("domain", ""):
        cdp.send("Network.deleteCookies", {"name": c["name"], "domain": c["domain"], "path": c.get("path", "/")})
cdp.navigate("https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html")
time.sleep(2)
cdp.evaluate("localStorage.clear()")
cdp.navigate("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html")
time.sleep(2)
cdp.evaluate("localStorage.clear()")

# Navigate to tyrz
print("\n=== Navigate to tyrz ===")
cdp.navigate("about:blank")
time.sleep(1)
cdp.navigate("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone")
for i in range(15):
    time.sleep(3)
    href = cdp.evaluate("location.href") or ""
    if "tyrz" in href:
        print(f"  At tyrz")
        break

# Fill credentials
creds = json.loads(Path("g:/UFO/政务平台/config/credentials.json").read_text(encoding="utf-8"))
print("\n=== Login ===")
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

# BEFORE clicking login, set up Fetch interception to BLOCK ssc.mohrss.gov.cn
print("\n=== Setting up ssc redirect interception ===")
# Use Fetch to intercept requests and block ssc
cdp.send("Fetch.enable", {
    "patterns": [
        {"urlPattern": "*ssc.mohrss.gov.cn*", "requestStage": "Request"}
    ]
})

time.sleep(1)
cdp.click_element('.form_button') or cdp.click_element('button[type="submit"]')
print("Login clicked. Monitoring with Fetch interception...")

# Handle Fetch.requestPaused events
import threading
ssc_blocked = [False]
ssc_url = [""]

def handle_events():
    """Read WS messages and handle Fetch.requestPaused."""
    while True:
        try:
            raw = cdp._ws.recv()
            msg = json.loads(raw)
            method = msg.get("method", "")
            if method == "Fetch.requestPaused":
                req = msg.get("params", {})
                url = req.get("request", {}).get("url", "")
                req_id = req.get("requestId", "")
                if "ssc.mohrss" in url:
                    print(f"  BLOCKED ssc request: {url[:80]}")
                    ssc_blocked[0] = True
                    ssc_url[0] = url
                    # Fail the request - browser stays on current page
                    cdp._ws.send(json.dumps({
                        "id": 99999,
                        "method": "Fetch.failRequest",
                        "params": {"requestId": req_id, "reason": "BlockedByClient"}
                    }))
                else:
                    # Continue other requests
                    cdp._ws.send(json.dumps({
                        "id": 99998,
                        "method": "Fetch.continueRequest",
                        "params": {"requestId": req_id}
                    }))
        except Exception as e:
            break

# Run event handler in background
t = threading.Thread(target=handle_events, daemon=True)
t.start()

# Wait for the login redirect chain to complete
for i in range(20):
    time.sleep(2)
    if ssc_blocked[0]:
        print(f"  ssc was blocked at iter {i+1}!")
        break
    
time.sleep(3)
# Disable Fetch
try:
    cdp.send("Fetch.disable")
except:
    pass

# Now check where we are and what cookies we have
time.sleep(2)
href = cdp.evaluate("location.href") or ""
print(f"\nAfter blocking ssc: URL={href[:80]}")

# Check cookies
all_c = cdp.send("Network.getAllCookies")
sessions = [c for c in all_c.get("cookies", []) if c.get("name") == "SESSION" and "scjdglj" in c.get("domain", "")]
print(f"SESSION cookies: {len(sessions)}")
for sc in sessions:
    print(f"  {sc['name']}={sc['value'][:25]} path={sc.get('path','/')}")

# Try SSO entservice
if sessions:
    print("\n=== Trying SSO entservice ===")
    cdp.navigate("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/sso/entservice?targetUrlKey=02_0002")
    time.sleep(10)
    href2 = cdp.evaluate("location.href") or ""
    auth = cdp.evaluate("localStorage.getItem('Authorization') || ''") or ""
    print(f"Result: {href2[:80]}")
    print(f"Auth: {auth[:30] if auth else 'none'}")
    
    if auth and len(auth) >= 16:
        print(f"\n>>> SUCCESS! Token: {auth}")
    elif "tyrz" in href2:
        print("Session still invalid. ssc completion IS required.")
        
        # Last resort: navigate TO ssc to let it complete
        if ssc_url[0]:
            print(f"\n=== Letting ssc load naturally ===")
            cdp.navigate(ssc_url[0])
            time.sleep(30)
            href3 = cdp.evaluate("location.href") or ""
            print(f"After 30s on ssc: {href3[:80]}")

cdp.close()
