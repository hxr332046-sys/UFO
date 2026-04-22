"""Full login test: tyrz login, handle ssc, navigate to 6087, get 9087 token."""
import json, time, requests, websocket, base64

port = 9225
pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
target = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=60)
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

# Step 1: Check if we need to login
href = ev("location.href") or ""
print(f"Current: {href[:80]}")

# Check if tyrz login page
has_form = ev("!!document.querySelector('#username, .login-form, .form_button')")
is_tyrz = "tyrz" in href

if not is_tyrz:
    # Navigate to tyrz via 6087 SSO
    print("\n=== Navigating to tyrz via enterprise-zone ===")
    # Clear 9087 localStorage
    send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"})
    time.sleep(2)
    ev("localStorage.removeItem('Authorization'); localStorage.removeItem('top-token')")
    send_cdp("Page.navigate", {"url": "about:blank"})
    time.sleep(1)
    send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone"})
    for i in range(15):
        time.sleep(3)
        href = ev("location.href") or ""
        print(f"  [{i+1}] {href[:80]}")
        if "tyrz" in href:
            break

# Step 2: Login on tyrz
href = ev("location.href") or ""
has_form = ev("!!document.querySelector('#username, .form_button')")
print(f"\ntyrz page: {href[:60]} hasForm={has_form}")

if has_form or "tyrz" in href:
    # Load credentials
    import pathlib
    creds = json.loads(pathlib.Path("g:/UFO/政务平台/config/credentials.json").read_text(encoding="utf-8"))
    username = creds["username"]
    password = creds["password"]
    
    print("Filling credentials...")
    ev(f"""(function(){{
        var u = document.querySelector('#username');
        if (!u) {{ var inputs = document.querySelectorAll('input'); for(var i=0;i<inputs.length;i++) if(inputs[i].type==='text'&&inputs[i].offsetParent) {{u=inputs[i];break;}} }}
        if (u) {{ u.focus(); u.value=''; u.dispatchEvent(new Event('input',{{bubbles:true}})); }}
    }})()""")
    time.sleep(0.3)
    # Type username character by character
    for ch in username:
        send_cdp("Input.dispatchKeyEvent", {"type": "keyDown", "text": ch, "key": ch})
        send_cdp("Input.dispatchKeyEvent", {"type": "keyUp", "key": ch})
        time.sleep(0.03)
    time.sleep(0.5)
    
    ev(f"""(function(){{
        var p = document.querySelector('#password');
        if (!p) {{ var inputs = document.querySelectorAll('input[type="password"]'); for(var i=0;i<inputs.length;i++) if(inputs[i].offsetParent) {{p=inputs[i];break;}} }}
        if (p) {{ p.focus(); p.value=''; p.dispatchEvent(new Event('input',{{bubbles:true}})); }}
    }})()""")
    time.sleep(0.3)
    for ch in password:
        send_cdp("Input.dispatchKeyEvent", {"type": "keyDown", "text": ch, "key": ch})
        send_cdp("Input.dispatchKeyEvent", {"type": "keyUp", "key": ch})
        time.sleep(0.03)
    time.sleep(0.5)
    
    # Slider - just use the main script's approach
    print("Running slider verification...")
    # Import and use the slider from the main script
    import sys
    sys.path.insert(0, "g:/UFO/政务平台/system")
    from cdp_auto_slider_login import CDPSession, auto_slide
    
    cdp = CDPSession(target["webSocketDebuggerUrl"])
    # Note: CDPSession opens its own WS connection
    slide_ok = auto_slide(cdp, max_attempts=5)
    print(f"Slider result: {slide_ok}")
    
    if slide_ok:
        time.sleep(1)
        # Click login button
        clicked = cdp.click_element('.form_button')
        if not clicked:
            clicked = cdp.click_element('button[type="submit"]')
        print(f"Login button clicked: {clicked}")
        
        # Wait for redirect
        print("\nWaiting for redirect...")
        for i in range(30):
            time.sleep(2)
            href = cdp.evaluate("location.href") or ""
            
            if ":6087" in href:
                print(f"  [{i+1}] LANDED ON 6087: {href[:60]}")
                break
            elif ":9087" in href:
                auth = cdp.evaluate("localStorage.getItem('Authorization') || ''") or ""
                if auth and len(auth) >= 16:
                    print(f"  [{i+1}] GOT 9087 TOKEN: {auth[:20]}")
                    break
                print(f"  [{i+1}] On 9087 but no auth: {href[:60]}")
            elif "ssc.mohrss" in href:
                if i < 15:
                    print(f"  [{i+1}] ssc page... waiting")
                else:
                    print(f"  [{i+1}] ssc stuck for {i*2}s, checking cookies...")
                    cookies = cdp.send("Network.getCookies", {"urls": [
                        "https://zhjg.scjdglj.gxzf.gov.cn:6087",
                        "https://zhjg.scjdglj.gxzf.gov.cn",
                    ]})
                    for c in cookies.get("cookies", []):
                        print(f"       Cookie: {c['name']}={c['value'][:20]} domain={c['domain']}")
                    
                    # Try navigating to 6087 SSO endpoint
                    print(f"  [{i+1}] Navigating to 6087 SSO...")
                    cdp.navigate("https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/sso/oauth2?authType=zwfw_guangxi")
                    time.sleep(10)
                    href2 = cdp.evaluate("location.href") or ""
                    print(f"  After 6087 SSO: {href2[:80]}")
                    
                    if ":6087" in href2 and "TopIP" in href2:
                        print("  LANDED ON 6087!")
                        break
                    elif "tyrz" in href2:
                        # tyrz again - need full re-login
                        print("  Back at tyrz. Session fully expired.")
                        # Try the entservice anyway
                        cdp.navigate("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/sso/entservice?targetUrlKey=02_0002")
                        time.sleep(10)
                        href3 = cdp.evaluate("location.href") or ""
                        auth3 = cdp.evaluate("localStorage.getItem('Authorization') || ''") or ""
                        print(f"  entservice result: {href3[:60]} auth={auth3[:20] if auth3 else 'none'}")
                    break
            else:
                print(f"  [{i+1}] {href[:60]}")
        
        # Final check
        href = cdp.evaluate("location.href") or ""
        print(f"\nFinal: {href[:80]}")
        
        # Try entservice if on 6087
        if ":6087" in href:
            print("\n=== Trying SSO entservice ===")
            cdp.navigate("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/sso/entservice?targetUrlKey=02_0002")
            time.sleep(10)
            href2 = cdp.evaluate("location.href") or ""
            auth = cdp.evaluate("localStorage.getItem('Authorization') || ''") or ""
            print(f"Result: {href2[:60]} auth={auth[:20] if auth else 'none'}")
    
    cdp.close()
else:
    print("No tyrz login form found")

ws.close()
