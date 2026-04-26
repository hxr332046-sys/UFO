"""最小 sanity：在浏览器里发一个最简单的 fetch 查 fire-and-forget 模式是否能用。"""
import json, time, urllib.request, websocket

CDP = "http://127.0.0.1:9225/json"
tab = next(t for t in json.loads(urllib.request.urlopen(CDP).read())
           if t.get("type") == "page" and "core.html" in t.get("url", ""))
ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=15)


def call(method, params=None, mid=None):
    if mid is None: mid = int(time.time() * 10000) % 900000 + 1
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    ws.settimeout(15)
    deadline = time.time() + 15
    while time.time() < deadline:
        try: m = json.loads(ws.recv())
        except: continue
        if m.get("id") == mid: return m
    return {"_err": "to"}


def ev(expr, await_p=False):
    r = call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": await_p})
    if r.get("error"): return {"_err": r["error"]}
    res = r.get("result", {})
    if res.get("exceptionDetails"): return {"_exc": str(res["exceptionDetails"])[:300]}
    return (res.get("result") or {}).get("value")


print(call("Runtime.enable"))
print("\n[1] 直接同步 JS 执行:", ev("1 + 2"))

# 2. Fire-and-forget fetch /icpsp-api/systemParam/list（最简单 API）
print("\n[2] fire-and-forget fetch /sysParam/list:")
ev("""(function(){
    window.__r__ = null; window.__e__ = null; window.__s__ = 'start';
    try {
        var auth = localStorage.getItem('Authorization');
        window.__s__ = 'have_auth_len=' + (auth||'').length;
        fetch('/icpsp-api/v4/pc/register/establish/sysParam/list?t='+Date.now(), {
            method: 'POST',
            headers: {'Authorization': auth, 'Content-Type': 'application/json;charset=UTF-8', 'language':'CH'},
            body: '{}',
            credentials: 'include'
        }).then(function(r){return r.json();}).then(function(j){
            window.__r__ = {code: j.code, hasData: !!j.data};
            window.__s__ = 'done';
        }).catch(function(e){
            window.__e__ = String(e);
            window.__s__ = 'catch';
        });
        window.__s__ = 'fetch_sent';
    } catch(e) {
        window.__e__ = 'outer: ' + String(e);
        window.__s__ = 'outer_catch';
    }
    return window.__s__;
})()""")

# 读状态 5 次
for i in range(5):
    time.sleep(2)
    s = ev("JSON.stringify({s:window.__s__, r:window.__r__, e:window.__e__})")
    print(f"  T+{(i+1)*2}s: {s}")

ws.close()
