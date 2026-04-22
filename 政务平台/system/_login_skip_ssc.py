"""Login and try to skip/bypass ssc page by clicking confirm button."""
import json, time, requests, websocket, sys
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

time.sleep(1)
cdp.click_element('.form_button') or cdp.click_element('button[type="submit"]')
print("Login clicked")

# Wait for ssc page
print("\nWaiting for ssc...")
for i in range(15):
    time.sleep(2)
    href = cdp.evaluate("location.href") or ""
    if "ssc.mohrss" in href:
        print(f"  On ssc: {href[:80]}")
        break
    if ":6087" in href:
        print(f"  On 6087! {href[:60]}")
        break
    print(f"  [{i+1}] {href[:60]}")

time.sleep(3)
href = cdp.evaluate("location.href") or ""
if "ssc.mohrss" not in href:
    print(f"Not on ssc, at: {href[:80]}")
    cdp.close()
    exit(0)

# Analyze ssc page with real dataToken
print("\n=== ssc page with real dataToken ===")
title = cdp.evaluate("document.title")
print(f"Title: {title}")

# Check visible elements
visible = cdp.evaluate("""(function(){
    var result = {};
    // Timeout message
    var timeout = document.querySelector('.pc-isIe_title');
    result.timeoutMsg = timeout ? timeout.textContent : 'none';
    result.timeoutVisible = timeout ? (timeout.offsetParent !== null || timeout.parentElement.style.visibility !== 'hidden') : false;
    
    // Confirm button
    var confirm = document.querySelector('.pc-isIe_esc');
    result.confirmBtn = confirm ? confirm.textContent : 'none';
    result.confirmVisible = confirm ? confirm.offsetParent !== null : false;
    
    // QR code
    var qr = document.querySelector('#qrcodeCanvas canvas');
    result.hasQRCode = !!qr;
    
    // authCertQuery visibility
    var authDiv = document.querySelector('.authCertQuery');
    result.authCertQueryDisplay = authDiv ? window.getComputedStyle(authDiv).display : 'none';
    result.authCertQueryVisibility = authDiv ? window.getComputedStyle(authDiv).visibility : 'none';
    
    // content-box visibility
    var contentBox = document.querySelector('.content-box');
    result.contentBoxDisplay = contentBox ? window.getComputedStyle(contentBox).display : 'none';
    
    return result;
})()""")
print(f"Page state: {json.dumps(visible, ensure_ascii=False, indent=2)}")

# Check for any redirect URL or callback in the page's JavaScript
callback_check = cdp.evaluate("""(function(){
    var result = {};
    // Check window variables
    if (typeof callbackUrl !== 'undefined') result.callbackUrl = callbackUrl;
    if (typeof redirectUrl !== 'undefined') result.redirectUrl = redirectUrl;
    if (typeof returnUrl !== 'undefined') result.returnUrl = returnUrl;
    if (typeof backUrl !== 'undefined') result.backUrl = backUrl;
    // Check URL params
    var params = new URLSearchParams(location.search);
    result.urlParams = {};
    params.forEach(function(v,k){ result.urlParams[k] = v.substring(0,80); });
    // Check global scope vars that might have redirect info
    if (typeof baseUrl !== 'undefined') result.baseUrl = baseUrl;
    if (typeof channelNo !== 'undefined') result.channelNo = channelNo;
    return result;
})()""")
print(f"\nCallbacks/redirects: {json.dumps(callback_check, ensure_ascii=False, indent=2)}")

# Try clicking the confirm button
print("\n=== Clicking '确定' button ===")
clicked = cdp.evaluate("""(function(){
    var btn = document.querySelector('.pc-isIe_esc');
    if (btn) {
        btn.click();
        return 'clicked: ' + btn.textContent;
    }
    // Try all visible buttons/divs with text
    var elems = document.querySelectorAll('div, button, a, span');
    for(var i=0;i<elems.length;i++){
        var t = elems[i].textContent.trim();
        if (t === '确定' && elems[i].offsetParent !== null) {
            elems[i].click();
            return 'clicked fallback: ' + t;
        }
    }
    return 'no button found';
})()""")
print(f"Click result: {clicked}")

time.sleep(3)
href2 = cdp.evaluate("location.href") or ""
print(f"After click: {href2[:80]}")

# Check if we went somewhere useful
if href2 != href:
    print(f"  Page changed!")
    time.sleep(5)
    href3 = cdp.evaluate("location.href") or ""
    print(f"  After 5s: {href3[:80]}")

# Also try history.back()
if "ssc" in href2:
    print("\n=== Trying history.back() ===")
    cdp.evaluate("history.back()")
    time.sleep(5)
    href4 = cdp.evaluate("location.href") or ""
    print(f"After back: {href4[:80]}")
    
    if ":6087" in href4:
        # Check if session is valid
        top_token = cdp.evaluate("localStorage.getItem('top-token') || ''") or ""
        print(f"top-token: {top_token[:30]}")
        
        # Try SSO entservice
        print("=== Trying SSO entservice ===")
        cdp.navigate("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/sso/entservice?targetUrlKey=02_0002")
        time.sleep(10)
        href5 = cdp.evaluate("location.href") or ""
        auth = cdp.evaluate("localStorage.getItem('Authorization') || ''") or ""
        print(f"Result: {href5[:60]} auth={auth[:20] if auth else 'none'}")

cdp.close()
