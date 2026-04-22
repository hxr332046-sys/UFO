"""Simulate logout: clear all cookies and localStorage."""
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
    r = sd("Runtime.evaluate", {"expression": e, "returnByValue": True, "timeout": 10000})
    return r.get("result", {}).get("value")

sd("Network.enable")
all_c = sd("Network.getAllCookies")
cleared = 0
for c in all_c.get("cookies", []):
    if "scjdglj" in c.get("domain", "") or "zwfw" in c.get("domain", ""):
        sd("Network.deleteCookies", {"name": c["name"], "domain": c["domain"], "path": c.get("path", "/")})
        cleared += 1
print(f"Cleared {cleared} cookies")

for url in ["https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html",
            "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"]:
    sd("Page.navigate", {"url": url})
    time.sleep(3)
    ev("localStorage.clear(); sessionStorage.clear();")
print("Cleared localStorage/sessionStorage")

sd("Page.navigate", {"url": "about:blank"})
time.sleep(1)
ws.close()
print("Logout done")
