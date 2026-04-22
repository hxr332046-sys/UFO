"""Probe current page + try forcing SSO redirect."""
import json, sys, time, requests, websocket

port = 9225
pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
target = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=15)
_id = [0]
def ev(expr):
    _id[0] += 1
    ws.send(json.dumps({"id": _id[0], "method": "Runtime.evaluate",
                         "params": {"expression": expr, "returnByValue": True, "timeout": 15000}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == _id[0]:
            return msg.get("result", {}).get("result", {}).get("value")

# Check current state
href = ev("location.href")
auth = ev("localStorage.getItem('Authorization') || ''")
body = ev("(document.body && document.body.innerText || '').substring(0, 300)")
print(f"URL: {href[:120]}")
print(f"Auth: {auth[:16] if auth else '(empty)'}")
print(f"Body: {body[:200]}")

# Check if there's a login/register button on the page
btns = ev("""(function(){
    var r = [];
    document.querySelectorAll('a,button,.el-button,span').forEach(function(el){
        var t = el.textContent.trim();
        if (t && (t.indexOf('登录') >= 0 || t.indexOf('注册') >= 0 || t.indexOf('开始办理') >= 0) && el.offsetParent !== null) {
            var rect = el.getBoundingClientRect();
            r.push({tag: el.tagName, text: t.substring(0, 30), x: rect.x, y: rect.y, w: rect.width, h: rect.height, cls: el.className.substring(0, 40), href: (el.href || '').substring(0, 80)});
        }
    });
    return r;
})()""")
print(f"\nLogin/Register buttons: {json.dumps(btns, ensure_ascii=False, indent=2)}")

# Try directly navigating to tyrz SSO with proper service URL
sso_url = ev("""(function(){
    // Check if there's an SSO redirect in the Vue router or window config
    var app = document.getElementById('app');
    var vm = app && app.__vue__;
    var store = vm && vm.$store;
    var conf = window.__ICPSP_CONFIG__ || window.globalConfig || {};
    return JSON.stringify({
        hasVue: !!vm,
        hasStore: !!store,
        config: Object.keys(conf).slice(0, 10),
        hash: location.hash,
    });
})()""")
print(f"\nVue state: {sso_url}")
ws.close()
