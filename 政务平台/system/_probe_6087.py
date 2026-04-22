"""Probe 6087 TopIP page for auth tokens after SSO login."""
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

# Navigate to tyrz + login + slider
print("=== Step 1: Navigate to tyrz ===")
ev("localStorage.removeItem('Authorization'); localStorage.removeItem('top-token');")
# DON'T clear cookies this time - let the session cookies work
send_cdp("Page.navigate", {"url": "about:blank"})
time.sleep(1)
send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone"})
for i in range(12):
    time.sleep(3)
    href = ev("location.href")
    print(f"  [{i+1}] {href[:80]}")
    if "tyrz" in str(href):
        break
    if "6087" in str(href):
        print("  Already at 6087 (SSO session still valid)")
        break
    if "9087" in str(href) and i > 5:
        # Check if we have auth
        auth = ev("localStorage.getItem('Authorization') || ''")
        if auth:
            print(f"  Already logged in! token={auth[:16]}...")
            ws.close()
            sys.exit(0)
        break
time.sleep(2)

href = ev("location.href")
print(f"\nLanded at: {href[:100]}")

# If on tyrz, do slider + login
if "tyrz" in str(href):
    print("\n=== Step 2: Slider + Login ===")
    # Fill credentials
    ev("""(function(){
        var u = document.querySelector('#username');
        if (u) { u.value = '450921198812051251'; u.dispatchEvent(new Event('input', {bubbles:true})); }
        var p = document.querySelector('#password');
        if (p) { p.value = ''; p.dispatchEvent(new Event('input', {bubbles:true})); }
    })()""")
    time.sleep(0.3)
    for ch in "AAaa18977514335":
        send_cdp("Input.dispatchKeyEvent", {"type": "keyDown", "text": ch})
        time.sleep(0.04)
        send_cdp("Input.dispatchKeyEvent", {"type": "keyUp", "text": ch})
    time.sleep(0.5)
    
    # Solve slider
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
    
    if info:
        _, bg_b64 = info["bgSrc"].split(",", 1)
        bg_bytes = base64.b64decode(bg_b64)
        _, bl_b64 = info["blockSrc"].split(",", 1)
        bl_bytes = base64.b64decode(bl_b64)
        import cv2, numpy as np
        bg = cv2.imdecode(np.frombuffer(bg_bytes, np.uint8), cv2.IMREAD_COLOR)
        block_rgba = cv2.imdecode(np.frombuffer(bl_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
        mask = block_rgba[:,:,3]
        result = cv2.matchTemplate(cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY), cv2.cvtColor(block_rgba[:,:,:3], cv2.COLOR_BGR2GRAY), cv2.TM_CCORR_NORMED, mask=mask)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        gap_x = max_loc[0]
        disp_w = info["bgDispW"] if info["bgDispW"] > 0 else info["barW"]
        drag = gap_x * disp_w / bg.shape[1]
        sx, sy = info["startX"], info["startY"]
        print(f"  Slider: gap={gap_x} conf={max_val:.4f} drag={drag:.0f}")
        
        ev(f"""(function(){{
            var bar=null; document.querySelectorAll('.verify-bar-area').forEach(function(el){{ if(el.offsetParent!==null&&el.getBoundingClientRect().width>100) bar=el; }});
            var s=bar.closest('.slider')||bar.parentElement; while(s&&!s.querySelector('.verify-move-block'))s=s.parentElement;
            var mb=s.querySelector('.verify-move-block');
            mb.dispatchEvent(new MouseEvent('mousedown',{{bubbles:true,cancelable:true,clientX:{sx},clientY:{sy},button:0,buttons:1,view:window}}));
        }})()""")
        time.sleep(0.3)
        for i in range(36):
            t=i/35; ease=t*t*(3-2*t)
            x=sx+drag*ease+random.uniform(-1,1); y=sy+random.uniform(-1.5,1.5)
            ev(f"document.dispatchEvent(new MouseEvent('mousemove',{{bubbles:true,cancelable:true,clientX:{x},clientY:{y},button:0,buttons:1,view:window}}))")
            time.sleep(0.015+random.random()*0.02)
        ev(f"document.dispatchEvent(new MouseEvent('mouseup',{{bubbles:true,cancelable:true,clientX:{sx+drag},clientY:{sy},button:0,view:window}}))")
        time.sleep(1.5)
        
        success = ev("(function(){var s=document.querySelectorAll('.slider_success');for(var i=0;i<s.length;i++)if(s[i].offsetParent!==null)return true;return false;})()")
        print(f"  Slider: {'PASS' if success else 'FAIL'}")
        
        if success:
            time.sleep(0.5)
            ev("document.querySelector('.form_button').click()")
            print("  Login clicked")

print("\n=== Step 3: Monitor redirects (focus on 6087) ===")
for i in range(30):
    time.sleep(2)
    try:
        href = ev("location.href")
    except:
        print(f"  [{i+1}] (redirecting...)")
        continue
    
    print(f"  [{i+1}] {href[:80]}")
    
    # If on 6087, probe for auth tokens
    if "6087" in str(href):
        tokens = ev("""(function(){
            var result = {};
            // Check localStorage
            for (var j=0; j<localStorage.length; j++) {
                var k = localStorage.key(j);
                var v = localStorage.getItem(k);
                if (v && v.length < 200) result['ls_'+k] = v;
                else if (v) result['ls_'+k] = v.substring(0, 80) + '...(len='+v.length+')';
            }
            // Check cookies
            result.cookies = document.cookie;
            // Check Vue store
            try {
                var app = document.getElementById('app');
                var vm = app && app.__vue__;
                var store = vm && vm.$store;
                if (store && store.state) {
                    var s = store.state;
                    result.vuex_token = (s.common || s.user || {}).token || '';
                    result.vuex_auth = (s.common || s.user || {}).Authorization || '';
                    result.vuex_keys = Object.keys(s).join(',');
                }
            } catch(e) { result.vuex_error = e.message; }
            return result;
        })()""")
        print(f"  6087 tokens: {json.dumps(tokens, ensure_ascii=False)[:500]}")
    
    # If on 9087, check auth
    if "9087" in str(href):
        auth = ev("localStorage.getItem('Authorization') || ''")
        if auth:
            print(f"  >>> 9087 AUTH: {auth[:20]}... (len={len(auth)})")
            break
        else:
            print(f"  9087 但无 auth")

ws.close()
