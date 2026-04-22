"""Force browser to SSO login by using the actual redirect URL."""
import json, sys, time, requests, websocket

port = 9225
pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
target = [p for p in pages if p.get("type") == "page"][0]
ws_url = target["webSocketDebuggerUrl"]

ws = websocket.create_connection(ws_url, timeout=20)
_id = [0]
def ev(expr):
    _id[0] += 1
    ws.send(json.dumps({"id": _id[0], "method": "Runtime.evaluate",
                         "params": {"expression": expr, "returnByValue": True, "timeout": 20000}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == _id[0]:
            return msg.get("result", {}).get("result", {}).get("value")

# Method 1: Navigate to the SSO authorize endpoint on icpsp
# This should redirect to tyrz
sso_authorize = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/sso/oauth2/authorize"
print(f"Navigating to: {sso_authorize}")
ws.send(json.dumps({"id": 998, "method": "Page.navigate", "params": {"url": sso_authorize}}))
while True:
    msg = json.loads(ws.recv())
    if msg.get("id") == 998: break

for i in range(8):
    time.sleep(3)
    href = ev("location.href")
    body = ev("(document.body && document.body.innerText || '').substring(0, 200)")
    has_pwd = ev("document.querySelectorAll('input[type=\"password\"]').length")
    print(f"  [{i+1}] href={str(href)[:100]}")
    print(f"       body={str(body)[:100]}")
    print(f"       password_inputs={has_pwd}")
    if has_pwd and int(has_pwd) > 0:
        print("  ✓ Found password inputs - SSO login page reached!")
        break
    if "tyrz" in str(href):
        print("  ✓ On tyrz domain!")
        break

ws.close()
