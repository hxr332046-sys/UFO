"""Get the actual tyrz SSO URL by clearing cookies and re-triggering redirect."""
import json, sys, time, requests, websocket, base64

port = 9225
pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
target = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=20)
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

# Step 1: Clear tyrz cookies to force re-redirect
print("Clearing tyrz cookies...")
send_cdp("Network.enable")
cookies = send_cdp("Network.getCookies", {"urls": [
    "https://tyrz.zwfw.gxzf.gov.cn",
    "https://zhjg.scjdglj.gxzf.gov.cn:9087"
]})
for c in cookies.get("cookies", []):
    name = c.get("name", "")
    domain = c.get("domain", "")
    print(f"  Deleting cookie: {name} @ {domain}")
    send_cdp("Network.deleteCookies", {"name": name, "domain": domain})

# Step 2: Clear localStorage auth
ev("localStorage.removeItem('Authorization'); localStorage.removeItem('top-token'); true")
print("Cleared localStorage auth")

# Step 3: Navigate to enterprise-zone with full page reload
print("\nNavigating to enterprise-zone (fresh)...")
ev('window.location.replace("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone")')

for i in range(15):
    time.sleep(2)
    try:
        href = ev("location.href")
    except:
        print(f"  [{i+1}] (redirecting...)")
        continue
    print(f"  [{i+1}] {str(href)[:100]}")
    if "tyrz" in str(href):
        # Found SSO URL!
        print(f"\n=== SSO URL ===")
        print(f"{href}")
        # Decode goto
        if "goto=" in str(href):
            goto_b64 = str(href).split("goto=")[1].split("&")[0]
            try:
                goto_decoded = base64.b64decode(goto_b64 + "==").decode("utf-8", errors="replace")
                print(f"\ngoto decoded: {goto_decoded}")
            except:
                print(f"\ngoto (raw): {goto_b64[:80]}")
        break
    if i > 8 and "9087" in str(href):
        print("  Stuck at 9087, no SSO redirect")
        # Try clicking login button
        btn = ev("""(function(){
            var els = document.querySelectorAll('a,span,div');
            for(var i=0;i<els.length;i++){
                var t=els[i].textContent.trim();
                if((t==='登录'||t==='登录/注册')&&els[i].offsetParent!==null){
                    var r=els[i].getBoundingClientRect();
                    return {text:t, x:r.x+r.width/2, y:r.y+r.height/2};
                }
            }
            return null;
        })()""")
        if btn:
            print(f"  Found login button: '{btn.get('text')}' at ({btn.get('x'):.0f},{btn.get('y'):.0f})")
            # Click it
            send_cdp("Input.dispatchMouseEvent", {"type": "mousePressed", "x": btn["x"], "y": btn["y"], "button": "left", "clickCount": 1})
            time.sleep(0.1)
            send_cdp("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": btn["x"], "y": btn["y"], "button": "left", "clickCount": 1})
            time.sleep(3)
            href2 = ev("location.href")
            print(f"  After click: {str(href2)[:100]}")

ws.close()
