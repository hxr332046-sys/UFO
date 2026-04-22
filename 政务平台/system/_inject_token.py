"""Extract tokens from 6087, navigate to 9087, inject them, and verify."""
import json, sys, time, requests, websocket

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

# Step 1: Navigate to 6087 to access its localStorage
href = ev("location.href")
print(f"Current: {href[:80]}")

if "6087" not in str(href):
    print("Navigating to 6087...")
    send_cdp("Page.navigate", {"url": "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"})
    time.sleep(5)

# Step 2: Read ALL 6087 tokens
tokens_6087 = ev("""(function(){
    var result = {};
    for (var i=0; i<localStorage.length; i++) {
        var k = localStorage.key(i);
        var v = localStorage.getItem(k);
        result[k] = v;
    }
    result._cookies = document.cookie;
    return result;
})()""")
print(f"\n=== 6087 localStorage ({len(tokens_6087)} items) ===")
for k, v in tokens_6087.items():
    print(f"  {k}: {str(v)[:80]}")

# Extract useful tokens
top_token = tokens_6087.get("top-token", "")
access_token_raw = tokens_6087.get("_topnet_accessToken", "")
if access_token_raw:
    try:
        import re
        m = re.search(r'"_value":"([^"]+)"', access_token_raw)
        access_token = m.group(1) if m else ""
    except:
        access_token = ""
else:
    access_token = ""

print(f"\ntop-token: {top_token}")
print(f"accessToken: {access_token}")

# Step 3: Try calling 9087 API with 6087 tokens
print("\n=== Testing 9087 API with 6087 tokens ===")

# Test with top-token as Authorization
for token_name, token_val in [("top-token", top_token), ("accessToken", access_token)]:
    if not token_val:
        continue
    print(f"\nTesting {token_name}={token_val[:20]}...")
    # Try as Authorization header
    try:
        r = requests.get(
            "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/v4/pc/common/tools/getCacheCreateTime",
            headers={"Authorization": token_val, "top-token": top_token},
            timeout=10, verify=False
        )
        print(f"  getCacheCreateTime: {r.status_code} → {r.text[:100]}")
    except Exception as e:
        print(f"  Error: {e}")

# Step 4: Try the 6087 API to get the real 9087 token
print("\n=== Checking 6087 API for 9087 token info ===")
# The 6087 TopIP might have an API that provides user info including the icpsp token
for endpoint in [
    "/TopIP/api/v1/user/info",
    "/TopIP/api/v1/auth/token",
    "/TopIP/sso/oauth2/token",
    "/TopIP/api/framework/user/currentUserInfo",
    "/TopIP/api/framework/sso/getToken",
]:
    try:
        r = requests.get(
            f"https://zhjg.scjdglj.gxzf.gov.cn:6087{endpoint}",
            headers={"Authorization": access_token, "top-token": top_token, "language": "CH"},
            timeout=10, verify=False
        )
        if r.status_code < 500:
            print(f"  {endpoint}: {r.status_code} → {r.text[:150]}")
    except:
        pass

# Step 5: Also try calling 6087 API from the browser (which has cookies)
print("\n=== Browser-side 6087 API calls ===")
user_info = ev("""(function(){
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '/TopIP/api/framework/user/currentUserInfo', false);
    xhr.setRequestHeader('top-token', localStorage.getItem('top-token') || '');
    xhr.setRequestHeader('language', 'CH');
    try {
        xhr.send();
        return {status: xhr.status, body: xhr.responseText.substring(0, 500)};
    } catch(e) {
        return {error: e.message};
    }
})()""")
print(f"currentUserInfo: {json.dumps(user_info, ensure_ascii=False)}")

# Try to get icpsp token from 6087
icpsp_token = ev("""(function(){
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '/TopIP/api/framework/sso/getToken', false);
    xhr.setRequestHeader('top-token', localStorage.getItem('top-token') || '');
    xhr.setRequestHeader('language', 'CH');
    try {
        xhr.send();
        return {status: xhr.status, body: xhr.responseText.substring(0, 500)};
    } catch(e) {
        return {error: e.message};
    }
})()""")
print(f"sso/getToken: {json.dumps(icpsp_token, ensure_ascii=False)}")

# Check if 6087 has info about 9087 in Vuex store
vuex = ev("""(function(){
    var app = document.getElementById('app');
    var vm = app && app.__vue__;
    var store = vm && vm.$store;
    if (!store) return 'no store';
    var s = store.state;
    // Recursively find any auth-related data
    var result = {};
    function scan(obj, prefix, depth) {
        if (depth > 3) return;
        for (var k in obj) {
            if (!obj.hasOwnProperty(k)) continue;
            var v = obj[k];
            if (typeof v === 'string' && v.length > 5 && v.length < 200 && /token|auth|session|user|login/i.test(k)) {
                result[prefix + k] = v;
            } else if (typeof v === 'object' && v !== null && depth < 2) {
                scan(v, prefix + k + '.', depth + 1);
            }
        }
    }
    scan(s, '', 0);
    return result;
})()""")
print(f"\nVuex auth-related: {json.dumps(vuex, ensure_ascii=False)}")

ws.close()
