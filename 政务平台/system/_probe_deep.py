"""深度探测 9087 服务状态"""
import json, time, requests, websocket

tabs = requests.get("http://127.0.0.1:9225/json", timeout=3).json()
target = [t for t in tabs if t.get("type") == "page" and not t.get("url", "").startswith("devtools")][0]
ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=60)
_id = [0]

def send_cmd(method, params=None):
    _id[0] += 1; mid = _id[0]
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == mid: return msg.get("result", {})

def ev(expr):
    r = send_cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "timeout": 20000, "awaitPromise": True})
    return r.get("result", {}).get("value")

send_cmd("Network.enable")

# 1. 9087 域的所有 cookies
cookies = send_cmd("Network.getAllCookies").get("cookies", [])
print("=== 9087 相关 Cookies ===")
for c in cookies:
    if "9087" in c.get("domain", "") or "scjdglj" in c.get("domain", ""):
        print(f"  {c['name']}={c['value'][:30]}... domain={c['domain']} path={c.get('path','/')}")

# 2. 直接 HTTP 到不同端口/路径
import requests as req
req.packages.urllib3.disable_warnings()
px = {"https": None, "http": None}

print("\n=== 直接 HTTP 探测 ===")
# 9087 根
try:
    r = req.get("https://zhjg.scjdglj.gxzf.gov.cn:9087/", verify=False, timeout=5, proxies=px)
    print(f"9087 root: {r.status_code}")
except Exception as e:
    print(f"9087 root: {e}")

# 6087 API
try:
    r = req.get("https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html", verify=False, timeout=5, proxies=px)
    print(f"6087 portal: {r.status_code} len={len(r.text)}")
except Exception as e:
    print(f"6087 portal: {e}")

# 9087 静态资源
try:
    r = req.get("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html", verify=False, timeout=5, proxies=px)
    print(f"9087 SPA html: {r.status_code} len={len(r.text)}")
except Exception as e:
    print(f"9087 SPA html: {e}")

# 9087 健康检查类
for path in ["/icpsp-api/", "/icpsp-api/actuator/health", "/icpsp-api/actuator/info"]:
    try:
        r = req.get(f"https://zhjg.scjdglj.gxzf.gov.cn:9087{path}", verify=False, timeout=5, proxies=px)
        print(f"9087{path}: {r.status_code} body={r.text[:80]}")
    except Exception as e:
        print(f"9087{path}: {e}")

ws.close()
print("\nDone.")
