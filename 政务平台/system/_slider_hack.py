"""Hack slider: force show images, detect gap, simulate verification via JS."""
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

href = ev("location.href")
print(f"Page: {href[:80]}")
if "tyrz" not in str(href):
    print("Not on tyrz!")
    sys.exit(1)

# Step 1: Force show the image panel
print("\n=== Step 1: Force show images ===")
ev("""(function(){
    // Find the VISIBLE slider group (个人登录 tab)
    var bars = document.querySelectorAll('.verify-bar-area');
    var bar = null;
    bars.forEach(function(el){ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; });
    if (!bar) return 'no bar';
    
    // Walk up to the slider container
    var slider = bar.closest('.slider') || bar.parentElement;
    
    // Force show verify-img-out
    var imgOut = slider.querySelector('.verify-img-out');
    if (imgOut) {
        imgOut.style.display = 'block';
        imgOut.style.position = 'absolute';
        imgOut.style.bottom = '65px';
        imgOut.style.zIndex = '99999';
    }
})()""")
time.sleep(0.3)

# Step 2: Read images
print("\n=== Step 2: Read images ===")
imgs = ev("""(function(){
    var bars = document.querySelectorAll('.verify-bar-area');
    var bar = null;
    bars.forEach(function(el){ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; });
    var slider = bar.closest('.slider') || bar.parentElement;
    var bgImg = slider.querySelector('img.backImg');
    var blockImg = slider.querySelector('img.bock-backImg');
    return {
        bgSrc: bgImg ? bgImg.src : null,
        blockSrc: blockImg ? blockImg.src : null,
        bgW: bgImg ? bgImg.naturalWidth : 0,
        bgH: bgImg ? bgImg.naturalHeight : 0,
        bgDispW: bgImg ? bgImg.getBoundingClientRect().width : 0,
        barW: bar.getBoundingClientRect().width,
    };
})()""")
print(f"bg={imgs['bgW']}x{imgs['bgH']} disp={imgs['bgDispW']:.0f} bar={imgs['barW']:.0f}")

# Step 3: Detect gap with OpenCV
print("\n=== Step 3: Detect gap ===")
bg_src = imgs["bgSrc"]
block_src = imgs["blockSrc"]
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
print(f"gap_x={gap_x} conf={max_val:.4f}")

bg_w = bg.shape[1]
bar_w = imgs["barW"]
disp_w = imgs["bgDispW"] if imgs["bgDispW"] > 0 else bar_w
scale = disp_w / bg_w
drag_display = gap_x * scale
print(f"scale={scale:.4f} drag_display={drag_display:.0f}px")

# Step 4: Use JavaScript to simulate the ENTIRE slider interaction
# This bypasses CDP Input events entirely
print("\n=== Step 4: JS slider simulation ===")
result = ev(f"""(function(){{
    var bars = document.querySelectorAll('.verify-bar-area');
    var bar = null;
    bars.forEach(function(el){{ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; }});
    var slider = bar.closest('.slider') || bar.parentElement;
    
    var moveBlock = slider.querySelector('.verify-move-block');
    var leftBar = slider.querySelector('.verify-left-bar');
    var subBlock = slider.querySelector('.verify-sub-block');
    var imgOut = slider.querySelector('.verify-img-out');
    
    if (!moveBlock || !leftBar || !subBlock) return {{error: 'missing elements'}};
    
    var barRect = bar.getBoundingClientRect();
    var mbRect = moveBlock.getBoundingClientRect();
    var startX = mbRect.x + mbRect.width/2;
    var startY = mbRect.y + mbRect.height/2;
    
    // Show image panel
    imgOut.style.display = 'block';
    imgOut.style.position = 'absolute';
    
    // Dispatch a trusted-looking mousedown
    var downEvt = new MouseEvent('mousedown', {{
        bubbles: true, cancelable: true,
        clientX: startX, clientY: startY,
        button: 0, buttons: 1, view: window
    }});
    moveBlock.dispatchEvent(downEvt);
    
    return {{
        startX: startX,
        startY: startY,
        barX: barRect.x,
        barW: barRect.width,
        moveBlockStyle: moveBlock.style.cssText,
        leftBarStyle: leftBar.style.cssText,
        subBlockStyle: subBlock.style.cssText,
    }};
}})()""")
print(f"After JS mousedown: {json.dumps(result, indent=2)}")

time.sleep(0.3)

# Now simulate mousemove events on document
drag = drag_display
steps = 40
print(f"\nSimulating {steps} mousemove events, total drag={drag:.0f}px...")

start_x = result.get("startX", 847)
start_y = result.get("startY", 419)

for i in range(steps + 1):
    t = i / steps
    ease = t * t * (3 - 2 * t)
    x = start_x + drag * ease + random.uniform(-1, 1)
    y = start_y + random.uniform(-2, 2)
    ev(f"""(function(){{
        var evt = new MouseEvent('mousemove', {{
            bubbles: true, cancelable: true,
            clientX: {x}, clientY: {y},
            button: 0, buttons: 1, view: window
        }});
        document.dispatchEvent(evt);
    }})()""")
    time.sleep(0.015 + random.random() * 0.02)

# Check position after mousemove
pos = ev("""(function(){
    var bars = document.querySelectorAll('.verify-bar-area');
    var bar = null;
    bars.forEach(function(el){ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; });
    var slider = bar.closest('.slider') || bar.parentElement;
    var mb = slider.querySelector('.verify-move-block');
    var lb = slider.querySelector('.verify-left-bar');
    var sb = slider.querySelector('.verify-sub-block');
    return {
        moveBlockLeft: mb.style.left,
        leftBarWidth: lb.style.width,
        subBlockLeft: sb.style.left,
    };
})()""")
print(f"After mousemove: {json.dumps(pos)}")

# Mouseup
end_x = start_x + drag
ev(f"""(function(){{
    var evt = new MouseEvent('mouseup', {{
        bubbles: true, cancelable: true,
        clientX: {end_x}, clientY: {start_y},
        button: 0, view: window
    }});
    document.dispatchEvent(evt);
}})()""")
print("Mouseup dispatched")

time.sleep(2)

# Check result
after = ev("""(function(){
    var success = false;
    document.querySelectorAll('.slider_success').forEach(function(s){ if(s.offsetParent !== null) success = true; });
    var bars = document.querySelectorAll('.verify-bar-area');
    var barVis = false;
    bars.forEach(function(el){ if(el.offsetParent !== null) barVis = true; });
    return {success: success, barVisible: barVis, href: location.href.substring(0, 80)};
})()""")
print(f"\nResult: {json.dumps(after, ensure_ascii=False)}")

ws.close()
