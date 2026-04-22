"""Debug: check ssc page content and tyrz cookies after login."""
import json, time, requests, websocket

port = 9225
pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
target = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=30)
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

# Check current page
href = ev("location.href")
print(f"Current URL: {href[:100]}")

# Check cookies on all relevant domains
send_cdp("Network.enable")
for domain in ["https://tyrz.zwfw.gxzf.gov.cn", "https://zhjg.scjdglj.gxzf.gov.cn:6087", "https://zhjg.scjdglj.gxzf.gov.cn:9087", "https://ssc.mohrss.gov.cn"]:
    cookies = send_cdp("Network.getCookies", {"urls": [domain]})
    clist = cookies.get("cookies", [])
    if clist:
        print(f"\nCookies for {domain} ({len(clist)}):")
        for c in clist:
            print(f"  {c.get('name')}={c.get('value','')[:30]} domain={c.get('domain')} httpOnly={c.get('httpOnly')} path={c.get('path')}")

# Navigate to tyrz SSO and check if it auto-logins
print("\n=== Testing tyrz auto-login ===")
# First decode the goto param from the SSO URL
goto_url = "https://tyrz.zwfw.gxzf.gov.cn/am/auth/login?service=initService&goto=aHR0cHM6Ly90eXJ6Lnp3ZncuZ3h6Zi5nb3YuY24vYW0vb2F1dGgyL2F1dGhvcml6ZT9zZXJ2aWNlPWluaXRTZXJ2aWNlJmNsaWVudF9pZD16cnl0aHh0JnJlZGlyZWN0X3VyaT1odHRwczovL3poamcuc2NqZGdsai5neHpmLmdvdi5jbjo2MDg3L1RvcElQL3Nzby9vYXV0aDI_YXV0aFR5cGU9endmd19ndWFuZ3hpJnJlc3BvbnNlX3R5cGU9Y29kZSZzY29wZT11aWQrY24rc24rbWFpbCZ0b2tlblR5cGU9SldU"
import base64
try:
    goto_b64 = goto_url.split("goto=")[1]
    # pad base64
    padded = goto_b64 + "=" * (4 - len(goto_b64) % 4) if len(goto_b64) % 4 else goto_b64
    goto_decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
    print(f"goto decoded: {goto_decoded[:200]}")
except:
    print("Could not decode goto")

# Try navigating to tyrz directly to see if session is alive
send_cdp("Page.navigate", {"url": "https://tyrz.zwfw.gxzf.gov.cn/am/auth/login?service=initService"})
time.sleep(5)
href2 = ev("location.href")
print(f"After tyrz navigate: {href2[:100]}")

# Check if we're on login page or got redirected (meaning session is alive)
has_login = ev("!!document.querySelector('#username, .login-form, .form_button')")
print(f"Has login form: {has_login}")

ws.close()
