"""Push Vue router to enterprise-zone."""
import json, time, requests, websocket
from pathlib import Path

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

url = ev('location.href') or ''
auth0 = ev("localStorage.getItem('Authorization') || ''")
print(f'URL: {url[:80]}')
print(f'Auth: {auth0}')

# Try Vue router push
r = ev("""(function(){
    var app = document.getElementById('app');
    if (!app) return 'no app element';
    var vm = app.__vue__;
    if (!vm) return 'no vue instance';
    if (!vm.$router) return 'no router';
    try {
        vm.$router.push('/index/enterprise/enterprise-zone');
        return 'router.push done';
    } catch(err) {
        return 'error: ' + err.message;
    }
})()""")
print(f"Router push: {r}")
time.sleep(5)

href = ev("location.href")
auth = ev("localStorage.getItem('Authorization') || ''")
body = ev("(document.body && document.body.innerText || '').substring(0, 200)")
print("\nAfter push:")
print(f"  URL: {href[:80]}")
print(f"  Auth: {auth[:36] if auth else '(empty)'}")
print(f"  Body: {body[:100] if body else '(empty)'}")

# If still stuck, try hash change + reload
if "enterprise" not in str(href):
    print("\nRouter push didn't work, trying location.hash change...")
    ev("window.location.hash = '#/index/enterprise/enterprise-zone'")
    time.sleep(3)
    href = ev("location.href")
    print(f"  After hash: {href[:80]}")
    
    # If still stuck, force full reload
    if "enterprise" not in str(href):
        print("  Force reload...")
        ev("window.location.href = 'https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone'")
        time.sleep(5)
        href = ev("location.href")
        auth = ev("localStorage.getItem('Authorization') || ''")
        body = ev("(document.body && document.body.innerText || '').substring(0, 200)")
        print(f"  URL: {href[:80]}")
        print(f"  Auth: {auth[:36] if auth else '(empty)'}")
        print(f"  Body: {body[:100] if body else '(empty)'}")

ws.close()
