"""Find the slider verification implementation and try to hack it directly."""
import json, sys, time, requests, websocket

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

# Check if on tyrz
href = ev("location.href")
print(f"Page: {href[:80]}")
if "tyrz" not in str(href):
    print("Need to be on tyrz page first!")
    sys.exit(1)

# Step 1: Find the event handlers on verify-move-block
print("\n=== Event handler analysis ===")
# Use Chrome's getEventListeners (only works in DevTools protocol)
r = send_cdp("Runtime.evaluate", {
    "expression": """(function(){
        var bars = document.querySelectorAll('.verify-bar-area');
        var bar = null;
        bars.forEach(function(el){ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; });
        if (!bar) return 'no bar';
        var parent = bar.parentElement;
        while (parent && !parent.querySelector('.verify-move-block')) {
            parent = parent.parentElement;
            if (!parent || parent === document.body) return 'no parent';
        }
        var mb = parent.querySelector('.verify-move-block');
        
        // Try to find the slider JS object
        // Common: jQuery data, Vue component, or standalone
        var info = {};
        
        // Check for jQuery event data
        if (typeof jQuery !== 'undefined') {
            var events = jQuery._data(mb, 'events') || {};
            info.jqueryEvents = Object.keys(events);
        }
        
        // Check for __vue__ component
        if (mb.__vue__) info.hasVue = true;
        if (parent.__vue__) info.parentHasVue = true;
        
        // Find slider class source
        var scripts = document.querySelectorAll('script[src]');
        var scriptSrcs = [];
        scripts.forEach(function(s){ 
            if (s.src && (s.src.indexOf('verify') >= 0 || s.src.indexOf('slider') >= 0 || s.src.indexOf('captcha') >= 0))
                scriptSrcs.push(s.src);
        });
        info.sliderScripts = scriptSrcs;
        
        // Search global scope for slider/verify related objects
        var globals = [];
        ['slideVerify', 'SlideVerify', 'verify', 'Verify', 'captcha', 'Captcha', 'slider', 'Slider'].forEach(function(name){
            if (window[name]) globals.push(name + ': ' + typeof window[name]);
        });
        info.globals = globals;
        
        // Check for inline event handlers
        info.onmousedown = mb.onmousedown ? 'set' : 'not set';
        info.ontouchstart = mb.ontouchstart ? 'set' : 'not set';
        
        // Check the move-block's parent chain CSS
        var chain = [];
        var el = parent;
        while (el && el !== document.body) {
            chain.push({tag: el.tagName, cls: el.className.substring(0, 40), display: getComputedStyle(el).display});
            el = el.parentElement;
        }
        info.parentChain = chain.slice(0, 5);
        
        return info;
    })()""",
    "returnByValue": True
})
print(json.dumps(r.get("result", {}).get("value"), ensure_ascii=False, indent=2))

# Step 2: Check the actual verify-img-out CSS
print("\n=== Image panel CSS ===")
css_info = ev("""(function(){
    var bars = document.querySelectorAll('.verify-bar-area');
    var bar = null;
    bars.forEach(function(el){ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; });
    if (!bar) return null;
    var parent = bar.parentElement;
    while (parent && !parent.querySelector('.verify-img-out')) {
        parent = parent.parentElement;
        if (!parent || parent === document.body) return null;
    }
    var imgOut = parent.querySelector('.verify-img-out');
    var imgPanel = parent.querySelector('.verify-img-panel');
    var style = imgOut ? getComputedStyle(imgOut) : {};
    var pstyle = imgPanel ? getComputedStyle(imgPanel) : {};
    return {
        imgOut: imgOut ? {display: style.display, visibility: style.visibility, opacity: style.opacity, position: style.position, width: style.width, height: style.height, overflow: style.overflow} : null,
        imgPanel: imgPanel ? {display: pstyle.display, visibility: pstyle.visibility, position: pstyle.position, width: pstyle.width} : null,
    };
})()""")
print(json.dumps(css_info, indent=2))

# Step 3: Try to manually show the images
print("\n=== Forcing image visibility ===")
ev("""(function(){
    var outs = document.querySelectorAll('.verify-img-out');
    outs.forEach(function(el){
        el.style.display = 'block';
        el.style.visibility = 'visible';
        el.style.opacity = '1';
        el.style.position = 'absolute';
        el.style.zIndex = '99999';
    });
    var panels = document.querySelectorAll('.verify-img-panel');
    panels.forEach(function(el){
        el.style.display = 'block';
        el.style.visibility = 'visible';
    });
})()""")
time.sleep(0.5)

visible_after = ev("""(function(){
    var outs = document.querySelectorAll('.verify-img-out');
    var r = [];
    outs.forEach(function(el){
        var br = el.getBoundingClientRect();
        r.push({w: br.width, h: br.height, visible: el.offsetParent !== null});
    });
    return r;
})()""")
print(f"After forcing: {json.dumps(visible_after)}")

# Step 4: Try to use dispatchEvent with isTrusted workaround
# Actually, isTrusted can't be faked. Let's try Input.dispatchMouseEvent but 
# use the exact coordinates of the move-block center
print("\n=== Trying CDP Input.dispatchMouseEvent with Touch events ===")
mb_rect = ev("""(function(){
    var bars = document.querySelectorAll('.verify-bar-area');
    var bar = null;
    bars.forEach(function(el){ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; });
    if (!bar) return null;
    var parent = bar.parentElement;
    while (parent && !parent.querySelector('.verify-move-block')) {
        parent = parent.parentElement;
        if (!parent || parent === document.body) return null;
    }
    var mb = parent.querySelector('.verify-move-block');
    var r = mb.getBoundingClientRect();
    return {x: r.x, y: r.y, w: r.width, h: r.height};
})()""")
print(f"Move-block: {mb_rect}")

if mb_rect:
    cx = mb_rect["x"] + mb_rect["w"]/2
    cy = mb_rect["y"] + mb_rect["h"]/2
    
    # Try touch events first
    send_cdp("Input.dispatchTouchEvent", {
        "type": "touchStart",
        "touchPoints": [{"x": cx, "y": cy}]
    })
    time.sleep(0.5)
    
    # Check if images appeared
    vis = ev("""(function(){
        var imgs = document.querySelectorAll('img.backImg');
        var r = [];
        imgs.forEach(function(img){
            var br = img.getBoundingClientRect();
            r.push({w: br.width, h: br.height, visible: img.offsetParent !== null});
        });
        return r;
    })()""")
    print(f"After touchStart: {json.dumps(vis)}")
    
    # Release touch
    send_cdp("Input.dispatchTouchEvent", {
        "type": "touchEnd",
        "touchPoints": []
    })

ws.close()
