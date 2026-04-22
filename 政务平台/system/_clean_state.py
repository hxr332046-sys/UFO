"""Clean browser state: delete all cookies without navigating (avoids creating new sessions)."""
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
sd("Network.enable")
all_c = sd("Network.getAllCookies")
n = 0
for c in all_c.get("cookies", []):
    d = c.get("domain", "")
    if "scjdglj" in d or "zwfw" in d or "mohrss" in d:
        sd("Network.deleteCookies", {"name": c["name"], "domain": d, "path": c.get("path", "/")})
        n += 1
# Also clear localStorage via Storage.clearDataForOrigin
for origin in [
    "https://zhjg.scjdglj.gxzf.gov.cn:6087",
    "https://zhjg.scjdglj.gxzf.gov.cn:9087",
]:
    sd("Storage.clearDataForOrigin", {"origin": origin, "storageTypes": "local_storage,session_storage"})
sd("Page.navigate", {"url": "about:blank"})
ws.close()
print(f"Cleaned {n} cookies + localStorage, at about:blank")
