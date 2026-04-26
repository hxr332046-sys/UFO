"""更深的诊断：换 GET fetch + 监听 Network 看请求到底发出没。"""
import json, time, urllib.request, websocket

CDP = "http://127.0.0.1:9225/json"
tab = next(t for t in json.loads(urllib.request.urlopen(CDP).read())
           if t.get("type") == "page" and "core.html" in t.get("url", ""))
ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=15)


def call(method, params=None, mid=None):
    if mid is None: mid = int(time.time() * 10000) % 900000 + 1
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    ws.settimeout(5)
    deadline = time.time() + 5
    while time.time() < deadline:
        try: m = json.loads(ws.recv())
        except: continue
        if m.get("id") == mid: return m
    return {"_err": "to"}


def ev(expr):
    r = call("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    res = r.get("result", {})
    if res.get("exceptionDetails"): return {"_exc": str(res["exceptionDetails"])[:300]}
    return (res.get("result") or {}).get("value")


call("Runtime.enable")
call("Network.enable")

# 清空 window 状态
ev("window.__r__=null; window.__e__=null; window.__s__='init';")

# 试 GET：最小 fetch / 根目录
print("[1] GET /")
ev("""(function(){
    window.__s__ = 'sending';
    fetch('/').then(r => {
        window.__s__ = 'got_response_' + r.status;
        return r.text();
    }).then(t => {
        window.__r__ = {len: t.length, head: t.slice(0,50)};
        window.__s__ = 'done';
    }).catch(e => {
        window.__e__ = String(e);
        window.__s__ = 'catch';
    });
    return window.__s__;
})()""")

# 同时监听 3 秒 Network 事件
ws.settimeout(0.5)
evts = []
t0 = time.time()
while time.time() - t0 < 5:
    try: raw = ws.recv()
    except: continue
    try: m = json.loads(raw)
    except: continue
    if m.get("method", "").startswith("Network."):
        p = m.get("params", {})
        if m["method"] == "Network.requestWillBeSent":
            evts.append(f"  REQ: {p.get('request', {}).get('url', '')[:60]}")
        elif m["method"] == "Network.responseReceived":
            evts.append(f"  RESP: status={p.get('response', {}).get('status')} url={p.get('response', {}).get('url', '')[:40]}")
        elif m["method"] == "Network.loadingFinished":
            evts.append(f"  FIN: {p.get('requestId','')[:12]}")
        elif m["method"] == "Network.loadingFailed":
            evts.append(f"  FAIL: {p.get('errorText', '')}")
    if len(evts) > 10: break

print("Network 事件:")
for e in evts[:15]:
    print(e)

# 读 window 状态
ws.settimeout(5)
s = ev("JSON.stringify({s:window.__s__, r:window.__r__, e:window.__e__})")
print(f"\nwindow 状态: {s}")

ws.close()
