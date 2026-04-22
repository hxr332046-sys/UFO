"""Debug: try triggering slider via JavaScript events instead of CDP Input."""
import json, sys, time, base64, random, requests, websocket
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
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

# Navigate to tyrz if needed
href = ev("location.href")
if "tyrz" not in str(href):
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
            break
    time.sleep(2)

# Step 1: Understand the slider event binding
print("=== Probing slider event handlers ===")
handlers = ev("""(function(){
    var bars = document.querySelectorAll('.verify-bar-area');
    var bar = null;
    bars.forEach(function(el){ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; });
    if (!bar) return {error: 'no visible bar'};
    
    var parent = bar.parentElement;
    while (parent && !parent.querySelector('.verify-move-block')) {
        parent = parent.parentElement;
        if (!parent || parent === document.body) return {error: 'no parent'};
    }
    
    var mb = parent.querySelector('.verify-move-block');
    var r = mb.getBoundingClientRect();
    
    // Check which events are bound
    var events = {};
    ['mousedown', 'touchstart', 'mouseup', 'touchend', 'mousemove', 'touchmove'].forEach(function(evt){
        // Check via getEventListeners (Chrome DevTools only)
        events[evt] = 'unknown';
    });
    
    return {
        moveBlockTag: mb.tagName,
        moveBlockCls: mb.className,
        rect: {x: r.x, y: r.y, w: r.width, h: r.height},
        parentTag: parent.tagName,
        parentCls: parent.className.substring(0, 60),
        // Try synthetic mousedown
    };
})()""")
print(f"Handlers: {json.dumps(handlers, indent=2)}")

# Step 2: Try JS-based mousedown event dispatch
print("\n=== Dispatching JS mousedown ===")
result = ev("""(function(){
    var bars = document.querySelectorAll('.verify-bar-area');
    var bar = null;
    bars.forEach(function(el){ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; });
    if (!bar) return {error: 'no bar'};
    
    var parent = bar.parentElement;
    while (parent && !parent.querySelector('.verify-move-block')) {
        parent = parent.parentElement;
        if (!parent || parent === document.body) return {error: 'no parent'};
    }
    
    var mb = parent.querySelector('.verify-move-block');
    var r = mb.getBoundingClientRect();
    var cx = r.x + r.width/2;
    var cy = r.y + r.height/2;
    
    // Dispatch mousedown on the move-block element directly
    var evt = new MouseEvent('mousedown', {
        bubbles: true, cancelable: true,
        clientX: cx, clientY: cy,
        button: 0, buttons: 1
    });
    mb.dispatchEvent(evt);
    
    return {dispatched: true, x: cx, y: cy};
})()""")
print(f"Mousedown dispatch: {result}")
time.sleep(0.8)

# Check if images are now visible
visible = ev("""(function(){
    var imgs = document.querySelectorAll('img.backImg');
    var r = [];
    imgs.forEach(function(img){
        var br = img.getBoundingClientRect();
        r.push({w: br.width, h: br.height, visible: img.offsetParent !== null, natW: img.naturalWidth});
    });
    var sbs = document.querySelectorAll('.verify-sub-block');
    var sbInfo = [];
    sbs.forEach(function(sb){
        var br = sb.getBoundingClientRect();
        sbInfo.push({w: br.width, h: br.height, visible: sb.offsetParent !== null, left: sb.style.left});
    });
    return {backImgs: r, subBlocks: sbInfo};
})()""")
print(f"After JS mousedown: {json.dumps(visible, indent=2)}")

# Step 3: If images visible, try JS-based mousemove + mouseup
print("\n=== Dispatching JS mousemove ===")
# Read slider images for gap detection
bg_src = ev("""(function(){
    var bars = document.querySelectorAll('.verify-bar-area');
    var bar = null;
    bars.forEach(function(el){ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; });
    if (!bar) return null;
    var parent = bar.parentElement;
    while (parent && !parent.querySelector('img.backImg')) { parent = parent.parentElement; if (!parent || parent === document.body) return null; }
    return parent.querySelector('img.backImg').src;
})()""")

if bg_src and bg_src.startswith("data:"):
    block_src = ev("""(function(){
        var bars = document.querySelectorAll('.verify-bar-area');
        var bar = null;
        bars.forEach(function(el){ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; });
        if (!bar) return null;
        var parent = bar.parentElement;
        while (parent && !parent.querySelector('img.bock-backImg')) { parent = parent.parentElement; if (!parent || parent === document.body) return null; }
        return parent.querySelector('img.bock-backImg').src;
    })()""")
    
    _, bg_b64 = bg_src.split(",", 1)
    bg_bytes = base64.b64decode(bg_b64)
    _, bl_b64 = block_src.split(",", 1)
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
    bar_w = handlers.get("rect", {}).get("w", 585) if isinstance(handlers, dict) else 585
    # Use parent bar width
    bar_w = ev("""(function(){
        var bars = document.querySelectorAll('.verify-bar-area');
        var bar = null;
        bars.forEach(function(el){ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; });
        return bar ? bar.getBoundingClientRect().width : 585;
    })()""") or 585
    
    scale = bar_w / bg_w
    drag = gap_x * scale
    print(f"Gap: x={gap_x} conf={max_val:.4f} drag={drag:.0f}px")
    
    start_info = ev("""(function(){
        var bars = document.querySelectorAll('.verify-bar-area');
        var bar = null;
        bars.forEach(function(el){ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; });
        var r = bar.getBoundingClientRect();
        return {barX: r.x, barY: r.y, barW: r.width, barH: r.height};
    })()""")
    bar_x = start_info["barX"]
    bar_y = start_info["barY"]
    cx = bar_x + 42  # button center initial position
    cy = bar_y + 30
    
    # Simulate drag via JS events on document
    print(f"Dragging from ({cx:.0f},{cy:.0f}) by {drag:.0f}px via JS events...")
    
    # Use document-level events (common pattern for slider verifiers)
    steps = 35
    for i in range(steps + 1):
        t = i / steps
        ease = t * t * (3 - 2 * t)  # ease-in-out
        x = cx + drag * ease + random.uniform(-1, 1)
        y = cy + random.uniform(-1.5, 1.5)
        ev(f"""(function(){{
            var evt = new MouseEvent('mousemove', {{
                bubbles: true, cancelable: true,
                clientX: {x}, clientY: {y},
                button: 0, buttons: 1
            }});
            document.dispatchEvent(evt);
        }})()""")
        time.sleep(0.02 + random.random() * 0.03)
    
    # Final mouseup
    end_x = cx + drag
    print(f"Mouse up at ({end_x:.0f},{cy:.0f})")
    ev(f"""(function(){{
        var evt = new MouseEvent('mouseup', {{
            bubbles: true, cancelable: true,
            clientX: {end_x}, clientY: {cy},
            button: 0
        }});
        document.dispatchEvent(evt);
    }})()""")
    
    time.sleep(2)
    
    # Check result
    after = ev("""(function(){
        var bars = document.querySelectorAll('.verify-bar-area');
        var barVis = false;
        bars.forEach(function(el){ if(el.offsetParent !== null) barVis = true; });
        var success = false;
        document.querySelectorAll('.slider_success').forEach(function(s){ if(s.offsetParent !== null) success = true; });
        return {success: success, barVisible: barVis, href: location.href};
    })()""")
    print(f"\nResult: {json.dumps(after, ensure_ascii=False)}")
else:
    print("No valid bg image data")

ws.close()
