"""Check if 6087 has a session after tyrz login (even though ssc is stuck)."""
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

href = ev("location.href")
print(f"Current: {href[:80]}")

# Navigate to 6087 and check localStorage
print("\n=== Checking 6087 localStorage ===")
send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"})
time.sleep(5)

href = ev("location.href")
print(f"6087 URL: {href[:80]}")

# Get ALL localStorage items
ls = ev("""(function(){
    var items = {};
    for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        var v = localStorage.getItem(k);
        items[k] = v ? v.substring(0, 60) : '';
    }
    return items;
})()""")
print(f"\n6087 localStorage ({len(ls or {})}):")
for k, v in (ls or {}).items():
    print(f"  {k}: {v}")

# Check ALL cookies via CDP (including httpOnly, all domains)
send_cdp("Network.enable")
all_cookies = send_cdp("Storage.getCookies")
if "cookies" not in all_cookies:
    all_cookies = send_cdp("Network.getAllCookies")
print(f"\nALL browser cookies ({len(all_cookies.get('cookies', []))}):")
for c in all_cookies.get("cookies", []):
    print(f"  {c['name']}={c['value'][:25]} domain={c['domain']} httpOnly={c.get('httpOnly',False)} path={c.get('path','/')}")

# Test the authLogin endpoint with Python requests to see what it needs
import urllib3; urllib3.disable_warnings()
print("\n=== Testing authLogin with Python requests ===")
top_token = (ls or {}).get("top-token", "")
if not top_token:
    top_token = ev("localStorage.getItem('top-token') || ''") or ""

# Test 1: No cookies, no token
r = requests.get(
    "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/authLogin?clientId=GS01&redirectUrl=https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/sso/entservice",
    verify=False, timeout=10, allow_redirects=False)
print(f"\n1) No auth: {r.status_code} Location={r.headers.get('Location','')[:80]}")
print(f"   Set-Cookie: {r.headers.get('Set-Cookie','none')[:60]}")

# Test 2: With top-token as cookie
r2 = requests.get(
    "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/authLogin?clientId=GS01&redirectUrl=https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/sso/entservice",
    headers={"Cookie": f"top-token={top_token}"},
    verify=False, timeout=10, allow_redirects=False)
print(f"\n2) Cookie top-token: {r2.status_code} Location={r2.headers.get('Location','')[:80]}")
print(f"   Set-Cookie: {r2.headers.get('Set-Cookie','none')[:60]}")

# Test 3: With Authorization header
r3 = requests.get(
    "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/authLogin?clientId=GS01&redirectUrl=https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/sso/entservice",
    headers={"Authorization": top_token},
    verify=False, timeout=10, allow_redirects=False)
print(f"\n3) Auth header: {r3.status_code} Location={r3.headers.get('Location','')[:80]}")

# Test 4: Follow the full redirect chain and capture cookies
print("\n=== Full redirect trace with requests ===")
session = requests.Session()
session.verify = False
r = session.get(
    "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/authLogin?clientId=GS01&redirectUrl=https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/sso/entservice",
    timeout=10, allow_redirects=True)
print(f"Final: {r.status_code} {r.url[:80]}")
hist = [str(h.status_code) + " → " + h.headers.get("Location","")[:50] for h in r.history]
print(f"History: {hist}")
print(f"Session cookies: {dict(session.cookies)}")

ws.close()
