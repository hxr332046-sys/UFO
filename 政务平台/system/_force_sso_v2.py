"""Force SSO redirect by full page reload to enterprise-zone."""
import json, sys, time, requests, websocket

port = 9225
pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
target = [p for p in pages if p.get("type") == "page"][0]
ws_url = target["webSocketDebuggerUrl"]

ws = websocket.create_connection(ws_url, timeout=20)
_id = [0]
def ev(expr):
    _id[0] += 1
    ws.send(json.dumps({"id": _id[0], "method": "Runtime.evaluate",
                         "params": {"expression": expr, "returnByValue": True, "timeout": 20000}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == _id[0]:
            return msg.get("result", {}).get("result", {}).get("value")

# Force full page reload (not SPA navigation) to enterprise-zone
target_url = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone"
print(f"Full reload to: {target_url[:80]}")

# Use location.replace for a full page navigation
ev(f'window.location.replace("{target_url}")')
time.sleep(3)

for i in range(12):
    time.sleep(3)
    try:
        href = ev("location.href")
        has_pwd = ev("document.querySelectorAll('input[type=\"password\"]').length")
        has_slider = ev("!!document.querySelector('[class*=\"slider\"],[class*=\"verify\"]')")
        auth = ev("(localStorage.getItem('Authorization') || '').substring(0, 12)")
        body_short = ev("(document.body && document.body.innerText || '').substring(0, 150)")
        
        on_tyrz = "tyrz" in str(href) or "am/auth" in str(href)
        on_9087 = "9087" in str(href)
        
        print(f"  [{i+1}/12] {str(href)[:80]}")
        print(f"     tyrz={on_tyrz} 9087={on_9087} pwd={has_pwd} slider={has_slider} auth={auth or '(none)'}")
        print(f"     body: {str(body_short)[:100]}")
        
        if on_tyrz or (has_pwd and int(has_pwd) > 0):
            print("  ✓ SSO login page reached!")
            break
        if auth and len(auth) > 8:
            print("  ✓ Already have token!")
            break
    except Exception as e:
        print(f"  [{i+1}/12] eval error (page may be redirecting): {e}")

ws.close()
