"""Click '经营主体登记注册' from 6087 TopIP portal to navigate to 9087 with auth."""
import json, time, requests, websocket
from pathlib import Path

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

href = ev("location.href")
print(f"Current: {href[:80]}")

# Navigate to 6087 if not there
if "6087" not in str(href):
    send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"})
    time.sleep(5)
    href = ev("location.href")
    print(f"Navigated to: {href[:80]}")

# Find all clickable elements with text "经营主体登记注册"
print("\n=== Finding '经营主体登记注册' link ===")
links = ev("""(function(){
    var results = [];
    var els = document.querySelectorAll('a, span, div, li, button, p, h3, h4');
    for (var i = 0; i < els.length; i++) {
        var el = els[i];
        var text = el.textContent.trim();
        if (text.indexOf('经营主体') >= 0 || text.indexOf('登记注册') >= 0) {
            var r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) {
                results.push({
                    tag: el.tagName,
                    text: text.substring(0, 40),
                    href: el.href || '',
                    x: r.x + r.width/2,
                    y: r.y + r.height/2,
                    w: r.width,
                    h: r.height,
                    visible: el.offsetParent !== null,
                    onclick: !!el.onclick,
                });
            }
        }
    }
    return results;
})()""")
print(f"Found {len(links)} matching elements:")
for l in (links or []):
    print(f"  {l['tag']} '{l['text'][:30]}' href={l.get('href','')[:60]} ({l['x']:.0f},{l['y']:.0f}) {l['w']:.0f}x{l['h']:.0f}")

if not links:
    print("No matching links found! Let me check all visible links...")
    all_links = ev("""(function(){
        var results = [];
        var els = document.querySelectorAll('a[href], [onclick]');
        for (var i = 0; i < els.length && results.length < 30; i++) {
            var el = els[i];
            var text = el.textContent.trim();
            var r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0 && text.length > 0 && text.length < 30) {
                results.push({text: text, href: el.href || '', tag: el.tagName});
            }
        }
        return results;
    })()""")
    for l in (all_links or []):
        print(f"  {l['tag']} '{l['text']}' → {l['href'][:60]}")

# Click the first matching link
if links:
    best = links[0]
    print(f"\nClicking: '{best['text']}' at ({best['x']:.0f}, {best['y']:.0f})")
    
    # Enable network monitoring before click
    send_cdp("Network.enable")
    _events.clear()
    
    # Click via CDP
    send_cdp("Input.dispatchMouseEvent", {"type": "mousePressed", "x": best["x"], "y": best["y"], "button": "left", "clickCount": 1})
    time.sleep(0.1)
    send_cdp("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": best["x"], "y": best["y"], "button": "left", "clickCount": 1})
    
    # Monitor where it goes
    print("\nMonitoring navigation...")
    for i in range(20):
        time.sleep(2)
        try:
            href = ev("location.href")
            auth = ev("localStorage.getItem('Authorization') || ''")
        except:
            print(f"  [{i+1}] (redirecting...)")
            continue
        
        print(f"  [{i+1}] {href[:80]} auth={'YES:'+auth[:16] if auth else 'none'}")
        
        if "9087" in str(href) and auth:
            print(f"\n>>> SUCCESS! 9087 with auth={auth[:30]}...")
            # Save token
            out = Path("g:/UFO/政务平台/packet_lab/out/runtime_auth_headers.json")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps({
                "headers": {
                    "Authorization": auth,
                    "top-token": auth,
                    "language": "CH",
                    "Content-Type": "application/json",
                }, "ts": int(time.time()), "source": "topip_click"
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            break
        
        # Check network requests
        for evt in _events[-20:]:
            if evt.get("method") == "Network.requestWillBeSent":
                url = evt.get("params", {}).get("request", {}).get("url", "")
                if "9087" in url and ("sso" in url or "auth" in url or "token" in url or "login" in url):
                    print(f"    NET: {url[:100]}")
        _events.clear()

ws.close()
