"""Probe ssc.mohrss.gov.cn page content after SSO login."""
import json, sys, time, base64, random, requests, websocket

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

# Navigate to tyrz, login, and observe what happens
# Step 1: Go to tyrz
ev("localStorage.removeItem('Authorization'); localStorage.removeItem('top-token');")
send_cdp("Network.enable")
cookies = send_cdp("Network.getCookies", {"urls": ["https://tyrz.zwfw.gxzf.gov.cn", "https://zhjg.scjdglj.gxzf.gov.cn:9087"]})
for c in cookies.get("cookies", []):
    send_cdp("Network.deleteCookies", {"name": c["name"], "domain": c["domain"]})
send_cdp("Page.navigate", {"url": "about:blank"})
time.sleep(1.5)
send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone"})
for i in range(10):
    time.sleep(3)
    href = ev("location.href")
    if "tyrz" in str(href):
        print(f"On tyrz: {href[:80]}")
        break
time.sleep(2)

# Step 2: Fill credentials
ev("""(function(){
    var u = document.querySelector('#username');
    if (u) { u.value = '450921198812051251'; u.dispatchEvent(new Event('input', {bubbles:true})); }
    var p = document.querySelector('#password');
    if (p) { p.value = ''; p.dispatchEvent(new Event('input', {bubbles:true})); }
})()""")
time.sleep(0.3)
# Type password
for ch in "AAaa18977514335":
    send_cdp("Input.dispatchKeyEvent", {"type": "keyDown", "text": ch})
    time.sleep(0.05 + random.random() * 0.05)
    send_cdp("Input.dispatchKeyEvent", {"type": "keyUp", "text": ch})
time.sleep(0.5)

# Step 3: Solve slider
info = ev("""(function(){
    var bar = null;
    document.querySelectorAll('.verify-bar-area').forEach(function(el){
        if (el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el;
    });
    if (!bar) return null;
    var slider = bar.closest('.slider') || bar.parentElement;
    while (slider && !slider.querySelector('img.backImg')) slider = slider.parentElement;
    var bgImg = slider.querySelector('img.backImg');
    var blockImg = slider.querySelector('img.bock-backImg');
    var mb = slider.querySelector('.verify-move-block');
    var imgOut = slider.querySelector('.verify-img-out');
    if (imgOut) { imgOut.style.display = 'block'; imgOut.style.position = 'absolute'; imgOut.style.bottom = '65px'; }
    var br = bar.getBoundingClientRect();
    var mr = mb.getBoundingClientRect();
    return { bgSrc: bgImg.src, blockSrc: blockImg.src, bgW: bgImg.naturalWidth, bgDispW: bgImg.getBoundingClientRect().width, barW: br.width, startX: mr.x + mr.width/2, startY: mr.y + mr.height/2 };
})()""")

if not info:
    print("No slider found!")
    ws.close()
    sys.exit(1)

# Detect gap
_, bg_b64 = info["bgSrc"].split(",", 1)
bg_bytes = base64.b64decode(bg_b64)
_, bl_b64 = info["blockSrc"].split(",", 1)
bl_bytes = base64.b64decode(bl_b64)

import cv2, numpy as np
bg = cv2.imdecode(np.frombuffer(bg_bytes, np.uint8), cv2.IMREAD_COLOR)
block_rgba = cv2.imdecode(np.frombuffer(bl_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
bg_gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)
block_gray = cv2.cvtColor(block_rgba[:,:,:3], cv2.COLOR_BGR2GRAY)
mask = block_rgba[:,:,3]
result = cv2.matchTemplate(bg_gray, block_gray, cv2.TM_CCORR_NORMED, mask=mask)
_, max_val, _, max_loc = cv2.minMaxLoc(result)
gap_x = max_loc[0]

bg_w = bg.shape[1]
bar_w = info["barW"]
disp_w = info["bgDispW"] if info["bgDispW"] > 0 else bar_w
scale = disp_w / bg_w
drag = gap_x * scale
print(f"Gap: x={gap_x} conf={max_val:.4f} drag={drag:.0f}px")

# Dispatch mousedown + mousemove + mouseup
sx, sy = info["startX"], info["startY"]
ev(f"""(function(){{
    var bar = null;
    document.querySelectorAll('.verify-bar-area').forEach(function(el){{ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; }});
    var slider = bar.closest('.slider') || bar.parentElement;
    while (slider && !slider.querySelector('.verify-move-block')) slider = slider.parentElement;
    var mb = slider.querySelector('.verify-move-block');
    mb.dispatchEvent(new MouseEvent('mousedown', {{ bubbles:true, cancelable:true, clientX:{sx}, clientY:{sy}, button:0, buttons:1, view:window }}));
}})()""")
time.sleep(0.3)

steps = 35
for i in range(steps+1):
    t = i/steps
    ease = t*t*(3-2*t)
    x = sx + drag*ease + random.uniform(-1, 1)
    y = sy + random.uniform(-1.5, 1.5)
    ev(f"document.dispatchEvent(new MouseEvent('mousemove', {{bubbles:true, cancelable:true, clientX:{x}, clientY:{y}, button:0, buttons:1, view:window}}))")
    time.sleep(0.015 + random.random() * 0.02)

ex = sx + drag
ev(f"document.dispatchEvent(new MouseEvent('mouseup', {{bubbles:true, cancelable:true, clientX:{ex}, clientY:{sy}, button:0, view:window}}))")
time.sleep(1.5)

success = ev("""(function(){ var s = document.querySelectorAll('.slider_success'); for(var i=0;i<s.length;i++) if(s[i].offsetParent !== null) return true; return false; })()""")
print(f"Slider success: {success}")

if not success:
    print("Slider failed, aborting")
    ws.close()
    sys.exit(1)

# Step 4: Click login
time.sleep(0.5)
ev("""(function(){
    var btn = document.querySelector('.form_button');
    if (btn) btn.click();
})()""")
print("Login clicked, monitoring redirects...")

# Step 5: Monitor redirects for 60 seconds
for i in range(30):
    time.sleep(2)
    try:
        href = ev("location.href")
        body = ev("(document.body && document.body.innerText || '').substring(0, 500)")
        auth = ev("localStorage.getItem('Authorization') || ''")
    except:
        print(f"  [{i+1}] (redirect in progress)")
        continue
    
    print(f"\n  [{i+1}] URL: {href[:100]}")
    if auth:
        print(f"  [{i+1}] AUTH: {auth[:20]}... (len={len(auth)})")
    
    if "ssc.mohrss" in str(href):
        print(f"  [{i+1}] SSC PAGE CONTENT:")
        print(f"  {body[:300]}")
        # Check for buttons/links
        btns = ev("""(function(){
            var r = [];
            document.querySelectorAll('a,button,div,span,input').forEach(function(el){
                var t = el.textContent.trim();
                if (t && t.length < 20 && el.offsetParent !== null) {
                    var rect = el.getBoundingClientRect();
                    if (rect.width > 0) r.push({tag: el.tagName, text: t, x: rect.x, y: rect.y, w: rect.width, h: rect.height});
                }
            });
            return r.slice(0, 20);
        })()""")
        if btns:
            print(f"  Visible elements: {json.dumps(btns[:10], ensure_ascii=False)}")
    
    if "9087" in str(href) and auth:
        print(f"\n>>> LOGGED IN! token={auth[:16]}...")
        break

ws.close()
