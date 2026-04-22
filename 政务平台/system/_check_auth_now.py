"""Quick check current page auth state."""
import json, requests, websocket

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

href = ev("location.href")
auth = ev("localStorage.getItem('Authorization') || ''")
top = ev("localStorage.getItem('top-token') || ''")
# Also check Vuex
vuex_token = ev("""(function(){
    var app = document.getElementById('app');
    var vm = app && app.__vue__;
    var store = vm && vm.$store;
    if (!store) return '(no store)';
    var state = store.state || {};
    return JSON.stringify({
        token: (state.common || {}).token || '',
        auth: (state.common || {}).Authorization || '',
        user: (state.common || {}).userInfo ? 'exists' : 'none',
    });
})()""")

# Check all localStorage keys
all_keys = ev("""(function(){
    var keys = [];
    for (var i=0; i<localStorage.length; i++) {
        var k = localStorage.key(i);
        var v = localStorage.getItem(k);
        keys.push({key: k, val: v ? v.substring(0, 60) : ''});
    }
    return keys;
})()""")

print(f"URL: {href[:100]}")
print(f"Auth: '{auth}' (len={len(auth) if auth else 0})")
print(f"top-token: '{top[:30]}' (len={len(top) if top else 0})")
print(f"Vuex: {vuex_token}")
print(f"\nAll localStorage keys:")
for item in (all_keys or []):
    print(f"  {item['key']}: {item['val']}")

ws.close()
