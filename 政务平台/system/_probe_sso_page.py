"""Deep probe tyrz SSO login page structure."""
import json, sys, time, requests, websocket
from pathlib import Path

port = 9225
pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
target = [p for p in pages if p.get("type") == "page"][0]
ws_url = target["webSocketDebuggerUrl"]

ws = websocket.create_connection(ws_url, timeout=15)
_id = [0]
def ev(expr):
    _id[0] += 1
    ws.send(json.dumps({"id": _id[0], "method": "Runtime.evaluate",
                         "params": {"expression": expr, "returnByValue": True, "timeout": 20000}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == _id[0]:
            return msg.get("result", {}).get("result", {}).get("value")

# First navigate to enterprise-zone to trigger SSO redirect
print("Navigating to enterprise-zone...")
ws.send(json.dumps({"id": 998, "method": "Page.navigate", 
    "params": {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone"}}))
while True:
    msg = json.loads(ws.recv())
    if msg.get("id") == 998: break

# Wait for SSO redirect
for i in range(8):
    time.sleep(3)
    href = ev("location.href")
    print(f"  [{i+1}] {href[:100]}")
    if "tyrz" in str(href) or "am/auth" in str(href):
        break

time.sleep(2)
print("\n=== SSO Page Deep Probe ===")
state = ev("""(function(){
    var result = {
        href: location.href,
        title: document.title,
    };
    
    // Find all tabs
    var tabs = document.querySelectorAll('[class*="tab"],[role="tab"],.login-tab,.am-tabs-tab');
    result.tabs = [];
    tabs.forEach(function(t){
        if (t.textContent.trim().length < 30) {
            result.tabs.push({
                text: t.textContent.trim(),
                active: t.classList.contains('active') || t.classList.contains('am-tabs-tab-active') || t.getAttribute('aria-selected') === 'true',
                cls: t.className.substring(0, 60)
            });
        }
    });
    
    // Find all visible input fields
    result.inputs = [];
    document.querySelectorAll('input').forEach(function(inp){
        result.inputs.push({
            type: inp.type,
            name: inp.name || '',
            id: inp.id || '',
            placeholder: inp.placeholder || '',
            visible: inp.offsetParent !== null,
            value: inp.value ? '(has value)' : '',
            cls: inp.className.substring(0, 40),
            parentCls: (inp.parentElement && inp.parentElement.className || '').substring(0, 40)
        });
    });
    
    // Find slider verification
    result.sliders = [];
    document.querySelectorAll('[class*="slider"],[class*="slide"],[class*="verify"],[class*="captcha"],[class*="drag"]').forEach(function(s){
        var r = s.getBoundingClientRect();
        result.sliders.push({
            tag: s.tagName,
            cls: s.className.substring(0, 80),
            text: s.textContent.trim().substring(0, 50),
            visible: s.offsetParent !== null,
            rect: {x: r.x, y: r.y, w: r.width, h: r.height}
        });
    });
    
    // Find canvas elements (used by slider captcha)
    result.canvases = [];
    document.querySelectorAll('canvas').forEach(function(c){
        var r = c.getBoundingClientRect();
        result.canvases.push({
            w: c.width, h: c.height,
            visible: c.offsetParent !== null,
            rect: {x: r.x, y: r.y, w: r.width, h: r.height}
        });
    });
    
    // Find buttons
    result.buttons = [];
    document.querySelectorAll('button,input[type="submit"],[class*="btn-login"],[class*="login-btn"],.am-btn').forEach(function(b){
        var r = b.getBoundingClientRect();
        result.buttons.push({
            text: b.textContent.trim().substring(0, 30),
            visible: b.offsetParent !== null,
            cls: b.className.substring(0, 60),
            rect: {x: r.x, y: r.y, w: r.width, h: r.height}
        });
    });
    
    // Find images that might be slider bg/block
    result.images = [];
    document.querySelectorAll('img').forEach(function(img){
        var src = img.src || '';
        if (src.length > 10 && (src.indexOf('captcha') >= 0 || src.indexOf('verify') >= 0 || src.indexOf('slider') >= 0 || src.indexOf('data:image') === 0 || img.closest('[class*="slider"],[class*="verify"]'))) {
            result.images.push({
                src: src.substring(0, 100),
                cls: img.className.substring(0, 40),
                w: img.naturalWidth, h: img.naturalHeight,
            });
        }
    });
    
    return result;
})()""")

print(json.dumps(state, ensure_ascii=False, indent=2))
ws.close()
