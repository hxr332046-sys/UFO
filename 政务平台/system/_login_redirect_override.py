"""Login and use Fetch to override 6087 SSO redirect from ssc to 6087 portal."""
import json, time, requests, websocket, sys, base64, threading
from pathlib import Path

sys.path.insert(0, "g:/UFO/政务平台/system")
from cdp_auto_slider_login import CDPSession, auto_slide

port = 9225
pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
target = [p for p in pages if p.get("type") == "page"][0]
cdp = CDPSession(target["webSocketDebuggerUrl"])

# Clear all auth
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
print("Cleared all auth")

# Navigate to tyrz
cdp.navigate("about:blank")
time.sleep(1)
cdp.navigate("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone")
for i in range(15):
    time.sleep(3)
    href = cdp.evaluate("location.href") or ""
    if "tyrz" in href:
        print(f"At tyrz")
        break

# Login
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

# BEFORE clicking login: set up Fetch to intercept RESPONSE from 6087 SSO
# We want to intercept the 302 redirect that goes to ssc.mohrss.gov.cn
# and change it to go to 6087 portal instead
print("\nSetting up Fetch response interception...")
cdp.send("Fetch.enable", {
    "patterns": [
        {"urlPattern": "*ssc.mohrss.gov.cn*", "requestStage": "Request"},
    ]
})

time.sleep(0.5)
cdp.click_element('.form_button') or cdp.click_element('button[type="submit"]')
print("Login clicked. Monitoring...")

# Handle Fetch events in a separate thread  
intercepted = [False]
intercepted_url = [""]
ws2 = cdp._ws

def fetch_handler():
    while True:
        try:
            raw = ws2.recv()
            msg = json.loads(raw)
            if msg.get("method") == "Fetch.requestPaused":
                req = msg.get("params", {})
                url = req.get("request", {}).get("url", "")
                req_id = req.get("requestId", "")
                if "ssc.mohrss" in url:
                    intercepted[0] = True
                    intercepted_url[0] = url
                    print(f"\n  INTERCEPTED ssc request: {url[:80]}")
                    # Instead of blocking, fulfill with a redirect to 6087 portal
                    redirect_url = "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"
                    ws2.send(json.dumps({
                        "id": 88888,
                        "method": "Fetch.fulfillRequest",
                        "params": {
                            "requestId": req_id,
                            "responseCode": 302,
                            "responseHeaders": [
                                {"name": "Location", "value": redirect_url}
                            ],
                            "body": ""
                        }
                    }))
                    print(f"  Redirected to: {redirect_url}")
                else:
                    ws2.send(json.dumps({
                        "id": 88887,
                        "method": "Fetch.continueRequest", 
                        "params": {"requestId": req_id}
                    }))
        except:
            break

t = threading.Thread(target=fetch_handler, daemon=True)
t.start()

# Wait for interception
for i in range(20):
    time.sleep(2)
    if intercepted[0]:
        break

time.sleep(5)
try:
    cdp.send("Fetch.disable")
except:
    pass

time.sleep(3)

# Check where we landed
href = cdp.evaluate("location.href") or ""
print(f"\nFinal URL: {href[:80]}")

# Check cookies and localStorage
top_token = cdp.evaluate("localStorage.getItem('top-token') || ''") or ""
print(f"top-token: {top_token[:30] if top_token else 'none'}")

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

cdp.close()
