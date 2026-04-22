import json, requests, websocket
pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
t = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=10)
_id = [0]
def sd(m, p=None):
    _id[0]+=1; ws.send(json.dumps({"id": _id[0], "method": m, "params": p or {}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == _id[0]: return r.get("result", {})
def ev(e):
    r = sd("Runtime.evaluate", {"expression": e, "returnByValue": True})
    return r.get("result", {}).get("value")

print("URL:", ev("location.href"))
print("Authorization:", ev("localStorage.getItem('Authorization')"))
print("top-token:", ev("localStorage.getItem('top-token')"))
ls = ev("JSON.stringify((function(){var o={};for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i);o[k]=(localStorage.getItem(k)||'').substring(0,50);}return o;})())")
print("localStorage:", ls)

# Check cookies
sd("Network.enable")
c = sd("Network.getAllCookies")
sessions = [x for x in c.get("cookies", []) if x.get("name") == "SESSION" and "scjdglj" in x.get("domain", "")]
print(f"SESSION cookies: {len(sessions)}")
for s in sessions:
    print(f"  {s['name']}={s['value'][:25]} path={s.get('path','/')}")
ws.close()
