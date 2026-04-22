"""Navigate to tyrz SSO page."""
import json, time, requests, websocket

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

ev("localStorage.removeItem('Authorization'); localStorage.removeItem('top-token');")
send_cdp("Network.enable")
cookies = send_cdp("Network.getCookies", {"urls": ["https://tyrz.zwfw.gxzf.gov.cn", "https://zhjg.scjdglj.gxzf.gov.cn:9087"]})
for c in cookies.get("cookies", []):
    send_cdp("Network.deleteCookies", {"name": c["name"], "domain": c["domain"]})
send_cdp("Page.navigate", {"url": "about:blank"})
time.sleep(1.5)
send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone"})
for i in range(10):
    time.sleep(3)
    href = ev("location.href")
    print(f"[{i+1}] {href[:80]}")
    if "tyrz" in str(href):
        print("OK - on tyrz!")
        break
ws.close()
