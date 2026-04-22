import json, time, requests, websocket
pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
t = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=30)
_id = [0]
def sd(m, p=None):
    _id[0]+=1; ws.send(json.dumps({"id": _id[0], "method": m, "params": p or {}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == _id[0]: return r.get("result", {})
def ev(e):
    r = sd("Runtime.evaluate", {"expression": e, "returnByValue": True, "timeout": 20000})
    return r.get("result", {}).get("value")

print("Before:", ev("location.href"))
print("Navigating to SSO entservice...")
sd("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/sso/entservice?targetUrlKey=02_0002"})

for i in range(15):
    time.sleep(2)
    href = ev("location.href") or ""
    auth = ev("localStorage.getItem('Authorization') || ''") or ""
    print(f"  [{i+1}] {href[:80]}")
    if auth and len(auth) >= 16:
        print(f"\n>>> Authorization={auth}")
        break
    if "tyrz" in href:
        print(">>> Redirected to tyrz, session invalid")
        break
ws.close()
