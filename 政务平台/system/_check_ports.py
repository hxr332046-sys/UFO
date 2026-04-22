"""Check projectPort mapping and SSO token exchange."""
import json, time, requests, websocket, urllib3
urllib3.disable_warnings()

# Fetch port.js from both 9087 and 6087
for port_num in [9087, 6087]:
    for path in ["/icpsp-web-pc/common/config/port.js", "/TopIP/web/common/config/port.js"]:
        try:
            r = requests.get(f"https://zhjg.scjdglj.gxzf.gov.cn:{port_num}{path}", verify=False, timeout=5)
            if r.status_code == 200 and len(r.text) > 50:
                print(f"\n=== {port_num}{path} ===")
                print(r.text[:2000])
        except:
            pass

# Connect to browser and check runtime values
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

# Navigate to 6087
href = ev("location.href")
if "6087" not in str(href):
    send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"})
    time.sleep(4)

print("\n=== 6087 window.projectPort ===")
pp = ev("JSON.stringify(window.projectPort || {})")
print(pp)

print("\n=== 6087 window.envConfig.framework.login ===")
login = ev("JSON.stringify(window.envConfig && window.envConfig.framework && window.envConfig.framework.login || {})")
print(login)

print("\n=== 6087 window.projectName ===")
pn = ev("window.projectName || ''")
print(pn)

# Now navigate to 9087 and check there
send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"})
time.sleep(3)

print("\n=== 9087 window.projectPort ===")
pp9 = ev("JSON.stringify(window.projectPort || {})")
print(pp9)

print("\n=== 9087 window.projectName ===")
pn9 = ev("window.projectName || ''")
print(pn9)

print("\n=== 9087 window.envConfig.framework.login ===")
login9 = ev("JSON.stringify(window.envConfig && window.envConfig.framework && window.envConfig.framework.login || {})")
print(login9)

# Try to call the 9087 API that the router guard uses for validation
# First, get the 6087 top-token
send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"})
time.sleep(3)
top_token = ev("localStorage.getItem('top-token') || ''")
print(f"\n6087 top-token: {top_token}")

# Call various 9087 API endpoints to find which one validates the token
print("\n=== Testing 9087 API endpoints ===")
headers = {"Authorization": top_token, "top-token": top_token, "language": "CH"}
for ep in [
    "/icpsp-api/v4/pc/common/user/currentUserInfo",
    "/icpsp-api/v4/pc/common/user/info",
    "/icpsp-api/v4/pc/common/auth/token",
    "/icpsp-api/v4/pc/common/auth/check",
    "/icpsp-api/v4/pc/common/tools/getUserByToken",
    "/icpsp-api/v4/pc/common/tools/cache/queryUserInfo",
]:
    try:
        r = requests.get(f"https://zhjg.scjdglj.gxzf.gov.cn:9087{ep}", headers=headers, verify=False, timeout=5)
        print(f"  {ep}: {r.status_code} → {r.text[:120]}")
    except Exception as e:
        print(f"  {ep}: ERROR {e}")

ws.close()
