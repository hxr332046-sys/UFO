"""Login with redirect interception: capture 6087 cookies, bypass ssc."""
import json, time, requests, websocket, sys
from pathlib import Path

sys.path.insert(0, "g:/UFO/政务平台/system")
from cdp_auto_slider_login import CDPSession, auto_slide

port = 9225
pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
target = [p for p in pages if p.get("type") == "page"][0]

cdp = CDPSession(target["webSocketDebuggerUrl"])

# Step 0: Clear ALL cookies for fresh session
print("=== Clearing all cookies ===")
cdp.send("Network.enable")
all_c = cdp.send("Network.getAllCookies")
for c in all_c.get("cookies", []):
    if "scjdglj" in c.get("domain", "") or "zwfw" in c.get("domain", ""):
        cdp.send("Network.deleteCookies", {
            "name": c["name"], "domain": c["domain"], "path": c.get("path", "/")
        })
        print(f"  Deleted: {c['name']} @ {c['domain']}{c.get('path','/')}")

# Also clear 6087 and 9087 localStorage
cdp.navigate("https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html")
time.sleep(2)
cdp.evaluate("localStorage.clear()")
cdp.navigate("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html")
time.sleep(2)
cdp.evaluate("localStorage.clear()")
print("Cleared all localStorage")

# Step 1: Navigate to enterprise-zone to trigger SSO redirect
print("\n=== Navigating to enterprise-zone ===")
cdp.navigate("about:blank")
time.sleep(1)
cdp.navigate("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone")
for i in range(15):
    time.sleep(3)
    href = cdp.evaluate("location.href") or ""
    if "tyrz" in href:
        print(f"  [{i+1}] At tyrz SSO")
        break
    print(f"  [{i+1}] {href[:60]}")

# Step 2: Login
href = cdp.evaluate("location.href") or ""
if "tyrz" not in href:
    print("ERROR: Not on tyrz page")
    cdp.close()
    exit(1)

creds = json.loads(Path("g:/UFO/政务平台/config/credentials.json").read_text(encoding="utf-8"))
print("\n=== Filling credentials ===")
cdp.evaluate(f"""(function(){{
    var u = document.querySelector('#username');
    if (!u) {{ var inputs = document.querySelectorAll('input'); for(var i=0;i<inputs.length;i++) if(inputs[i].type==='text'&&inputs[i].offsetParent) {{u=inputs[i];break;}} }}
    if (u) {{ u.focus(); u.value=''; u.dispatchEvent(new Event('input',{{bubbles:true}})); }}
}})()""")
time.sleep(0.3)
cdp.type_text(creds["username"], delay_ms=30)
time.sleep(0.5)

cdp.evaluate(f"""(function(){{
    var p = document.querySelector('#password');
    if (!p) {{ var inputs = document.querySelectorAll('input[type="password"]'); for(var i=0;i<inputs.length;i++) if(inputs[i].offsetParent) {{p=inputs[i];break;}} }}
    if (p) {{ p.focus(); p.value=''; p.dispatchEvent(new Event('input',{{bubbles:true}})); }}
}})()""")
time.sleep(0.3)
cdp.type_text(creds["password"], delay_ms=30)
time.sleep(0.5)

print("=== Slider ===")
ok = auto_slide(cdp, max_attempts=5)
print(f"Slider: {ok}")
if not ok:
    cdp.close()
    exit(1)

time.sleep(1)
cdp.click_element('.form_button') or cdp.click_element('button[type="submit"]')
print("Login button clicked")

# Step 3: Monitor cookies during redirect chain
print("\n=== Monitoring redirect chain ===")
for i in range(20):
    time.sleep(2)
    href = cdp.evaluate("location.href") or ""
    
    # Check cookies on each iteration
    cookies = cdp.send("Network.getAllCookies")
    session_cookies = [c for c in cookies.get("cookies", []) if c.get("name") == "SESSION" and "scjdglj" in c.get("domain", "")]
    
    if ":6087" in href:
        print(f"  [{i+1}] ON 6087! {href[:60]}")
        print(f"  SESSION cookies: {len(session_cookies)}")
        for sc in session_cookies:
            print(f"    {sc['name']}={sc['value'][:25]} path={sc.get('path','/')}")
        break
    
    if "ssc.mohrss" in href:
        if session_cookies:
            print(f"  [{i+1}] ssc page. SESSION cookies found ({len(session_cookies)})!")
            for sc in session_cookies:
                print(f"    {sc['name']}={sc['value'][:25]} path={sc.get('path','/')}")
            
            # We have cookies! Try the SSO entservice now
            print("\n  === Bypassing ssc → SSO entservice ===")
            cdp.navigate("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/sso/entservice?targetUrlKey=02_0002")
            time.sleep(10)
            href2 = cdp.evaluate("location.href") or ""
            auth = cdp.evaluate("localStorage.getItem('Authorization') || ''") or ""
            print(f"  Result: {href2[:60]} auth={auth[:20] if auth else 'none'}")
            if auth and len(auth) >= 16:
                print(f"\n>>> SUCCESS! Token: {auth}")
            break
        else:
            if i < 5:
                print(f"  [{i+1}] ssc page. No SESSION cookies yet...")
            elif i >= 5:
                print(f"  [{i+1}] ssc stuck, no 6087 cookies. Redirect chain broken.")
                # Check ALL cookies
                all_c2 = cookies.get("cookies", [])
                relevant = [c for c in all_c2 if "scjdglj" in c.get("domain", "") or "zwfw" in c.get("domain", "")]
                print(f"  Relevant cookies ({len(relevant)}):")
                for c in relevant:
                    print(f"    {c['name']}={c['value'][:25]} domain={c['domain']} path={c.get('path','/')}")
                break
    elif ":9087" in href:
        auth = cdp.evaluate("localStorage.getItem('Authorization') || ''") or ""
        if auth and len(auth) >= 16:
            print(f"  [{i+1}] ON 9087 with token: {auth[:20]}")
            break
        print(f"  [{i+1}] On 9087 no auth: {href[:60]}")
    else:
        print(f"  [{i+1}] {href[:60]}")

cdp.close()
