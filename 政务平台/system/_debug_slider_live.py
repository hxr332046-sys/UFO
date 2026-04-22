"""Live debug: do a slider drag and check what happens, including network requests."""
import json, sys, time, base64, io, random, requests, websocket
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
port = 9225
pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
target = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=30)
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

def mouse(typ, x, y, btn="left"):
    send_cdp("Input.dispatchMouseEvent", {"type": typ, "x": x, "y": y, "button": btn, "clickCount": 1})

# Ensure we're on tyrz
href = ev("location.href")
print(f"Page: {href[:80]}")
if "tyrz" not in str(href):
    print("Not on tyrz, navigating...")
    # Clear cookies & navigate
    ev("localStorage.removeItem('Authorization'); localStorage.removeItem('top-token'); true")
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
        print(f"  [{i+1}] {href[:80]}")
        if "tyrz" in str(href):
            break
    time.sleep(2)

# Enable network monitoring
send_cdp("Network.enable")
_events.clear()

# Check current slider state
state = ev("""(function(){
    var bars = document.querySelectorAll('.verify-bar-area');
    var bar = null;
    bars.forEach(function(el){ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; });
    if (!bar) return {hasBar: false};
    var parent = bar.parentElement;
    while (parent && !parent.querySelector('.verify-move-block')) { parent = parent.parentElement; if (!parent || parent === document.body) return {hasBar: true, noParent: true}; }
    var mb = parent.querySelector('.verify-move-block');
    var br = bar.getBoundingClientRect();
    var mr = mb.getBoundingClientRect();
    return {hasBar: true, barX: br.x, barW: br.width, moveX: mr.x, moveW: mr.width, moveY: mr.y, moveH: mr.height};
})()""")
print(f"\nSlider state: {json.dumps(state)}")

if not state or not state.get("hasBar"):
    print("No slider bar found!")
    ws.close()
    sys.exit(1)

cx = state["moveX"] + state["moveW"] / 2
cy = state["moveY"] + state["moveH"] / 2
bar_w = state["barW"]
print(f"Click at ({cx:.0f}, {cy:.0f}), bar_w={bar_w:.0f}")

# Step 1: Check if page has anti-bot flags
checks = ev("""(function(){
    return {
        webdriver: navigator.webdriver,
        languages: navigator.languages,
        plugins: navigator.plugins.length,
        headless: /HeadlessChrome/.test(navigator.userAgent),
    };
})()""")
print(f"\nAnti-bot checks: {json.dumps(checks)}")

# Step 2: Mouse down
print("\n--- Mouse down ---")
mouse("mouseMoved", cx, cy)
time.sleep(0.3)
mouse("mousePressed", cx, cy)
time.sleep(0.5)
mouse("mouseMoved", cx + 2, cy)
time.sleep(0.8)

# Read slider images
imgs = ev("""(function(){
    var bars = document.querySelectorAll('.verify-bar-area');
    var bar = null;
    bars.forEach(function(el){ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; });
    if (!bar) return null;
    var parent = bar.parentElement;
    while (parent && !parent.querySelector('img.backImg')) { parent = parent.parentElement; if (!parent || parent === document.body) return null; }
    var bg = parent.querySelector('img.backImg');
    var block = parent.querySelector('img.bock-backImg');
    var sb = parent.querySelector('.verify-sub-block');
    return {
        bgSrc: bg ? bg.src.substring(0, 50) : null,
        blockSrc: block ? block.src.substring(0, 50) : null,
        bgW: bg ? bg.naturalWidth : 0,
        bgDispW: bg ? bg.getBoundingClientRect().width : 0,
        subBlockLeft: sb ? sb.style.left : '(no style)',
        subBlockVis: sb ? sb.offsetParent !== null : false,
        subBlockRect: sb ? (function(r){return {x:r.x,y:r.y,w:r.width,h:r.height};})(sb.getBoundingClientRect()) : null,
    };
})()""")
print(f"Images after mousedown: {json.dumps(imgs, ensure_ascii=False)}")

# Step 3: Read bg+block, detect gap
bg_src = ev("""(function(){
    var bars = document.querySelectorAll('.verify-bar-area');
    var bar = null;
    bars.forEach(function(el){ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; });
    if (!bar) return null;
    var parent = bar.parentElement;
    while (parent && !parent.querySelector('img.backImg')) { parent = parent.parentElement; if (!parent || parent === document.body) return null; }
    return parent.querySelector('img.backImg').src;
})()""")
block_src = ev("""(function(){
    var bars = document.querySelectorAll('.verify-bar-area');
    var bar = null;
    bars.forEach(function(el){ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; });
    if (!bar) return null;
    var parent = bar.parentElement;
    while (parent && !parent.querySelector('img.bock-backImg')) { parent = parent.parentElement; if (!parent || parent === document.body) return null; }
    return parent.querySelector('img.bock-backImg').src;
})()""")

if bg_src and block_src and bg_src.startswith("data:"):
    _, bg_b64 = bg_src.split(",", 1)
    bg_bytes = base64.b64decode(bg_b64)
    _, bl_b64 = block_src.split(",", 1)
    bl_bytes = base64.b64decode(bl_b64)
    
    # Save for debug
    (ROOT / "dashboard/data/records/slider_bg_live.png").write_bytes(bg_bytes)
    (ROOT / "dashboard/data/records/slider_block_live.png").write_bytes(bl_bytes)
    
    # Detect gap
    import cv2, numpy as np
    bg = cv2.imdecode(np.frombuffer(bg_bytes, np.uint8), cv2.IMREAD_COLOR)
    block_rgba = cv2.imdecode(np.frombuffer(bl_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
    bg_gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)
    block_gray = cv2.cvtColor(block_rgba[:,:,:3], cv2.COLOR_BGR2GRAY)
    mask = block_rgba[:,:,3]
    result = cv2.matchTemplate(bg_gray, block_gray, cv2.TM_CCORR_NORMED, mask=mask)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    gap_x = max_loc[0]
    print(f"\nGap detection: x={gap_x} conf={max_val:.4f}")
    
    # Calculate drag
    bg_w = bg.shape[1]
    scale = bar_w / bg_w
    drag_px = gap_x * scale
    print(f"bg_w={bg_w} scale={scale:.4f} drag={drag_px:.1f}px")
    
    # Step 4: Drag with human-like trajectory
    print(f"\n--- Dragging {drag_px:.0f}px ---")
    steps = 40
    for i in range(steps + 1):
        t = i / steps
        # Ease in-out
        ease = t * t * (3 - 2 * t)
        x = cx + drag_px * ease + random.uniform(-1.5, 1.5)
        y = cy + random.uniform(-2, 2)
        mouse("mouseMoved", x, y)
        time.sleep(0.015 + random.random() * 0.025)
    
    # Final precise position
    end_x = cx + drag_px
    mouse("mouseMoved", end_x, cy)
    time.sleep(0.05)
    
    # Step 5: Mouse up
    print("--- Mouse up ---")
    mouse("mouseReleased", end_x, cy)
    
    # Step 6: Wait and check
    time.sleep(2)
    
    # Check state
    after = ev("""(function(){
        var success = document.querySelectorAll('.slider_success');
        var vis = false;
        success.forEach(function(s){ if(s.offsetParent !== null) vis = true; });
        var bars = document.querySelectorAll('.verify-bar-area');
        var barVis = false;
        bars.forEach(function(el){ if(el.offsetParent !== null) barVis = true; });
        var bodySnip = (document.body.innerText || '').substring(0, 300);
        return {success: vis, barVisible: barVis, body: bodySnip};
    })()""")
    print(f"\nAfter drag: {json.dumps(after, ensure_ascii=False)}")
    
    # Check for any network verification requests
    verify_reqs = [e for e in _events if e.get("method") == "Network.requestWillBeSent"]
    print(f"\nNetwork requests during drag: {len(verify_reqs)}")
    for req in verify_reqs[-5:]:
        url = req.get("params", {}).get("request", {}).get("url", "")
        method = req.get("params", {}).get("request", {}).get("method", "")
        print(f"  {method} {url[:100]}")
else:
    print("No valid image data")

ws.close()
