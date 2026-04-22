"""用浏览器 session 测试 9087 API"""
import json, time, requests, websocket

tabs = requests.get("http://127.0.0.1:9225/json", timeout=3).json()
target = [t for t in tabs if t.get("type") == "page" and not t.get("url", "").startswith("devtools")][0]
print(f"Tab: {target['url'][:60]}")

ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=60)
_id = [0]

def send_cmd(method, params=None):
    _id[0] += 1
    mid = _id[0]
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == mid:
            return msg.get("result", {})

def ev(expr):
    r = send_cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "timeout": 20000, "awaitPromise": True})
    return r.get("result", {}).get("value")

# 先导航到 9087 确保 origin 正确
print("\n[1] 导航到 9087...")
send_cmd("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/page"})
time.sleep(5)

# 检查 localStorage
auth = ev("localStorage.getItem('Authorization') || '<empty>'") or ""
print(f"Authorization: {auth[:30]}")

# 用 fetch 在浏览器中直接调 API（使用浏览器的完整 session）
print("\n[2] 浏览器内 fetch getSysParam...")
result = ev("""
(async function(){
    try {
        var auth = localStorage.getItem('Authorization') || '';
        var r = await fetch('/icpsp-api/appinfo/getSysParam', {
            method: 'GET',
            headers: {
                'Authorization': auth,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        });
        var t = await r.text();
        return 'status=' + r.status + ' body=' + t.substring(0, 200);
    } catch(e) { return 'error:' + e.message; }
})()
""")
print(f"  {result}")

# 试 checkEstablishName
print("\n[3] 浏览器内 fetch checkEstablishName...")
result2 = ev("""
(async function(){
    try {
        var auth = localStorage.getItem('Authorization') || '';
        var r = await fetch('/icpsp-api/icpspsupervise/EstablishInfo/checkEstablishName?entType=4540&distCode=450921&distCodeArr=450000,450900,450921', {
            method: 'GET',
            headers: { 'Authorization': auth, 'Content-Type': 'application/json' }
        });
        var t = await r.text();
        return 'status=' + r.status + ' body=' + t.substring(0, 200);
    } catch(e) { return 'error:' + e.message; }
})()
""")
print(f"  {result2}")

ws.close()
print("\nDone.")
