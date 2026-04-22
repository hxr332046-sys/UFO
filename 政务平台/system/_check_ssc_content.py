"""Navigate to ssc page and check what it displays."""
import json, time, requests, websocket

port = 9225
pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
target = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=30)
_id = [0]
_events = []
def send_cdp(method, params=None):
    _id[0] += 1
    ws.send(json.dumps({"id": _id[0], "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("method"):
            _events.append(msg)
        if msg.get("id") == _id[0]:
            return msg.get("result", {})
def ev(expr):
    r = send_cdp("Runtime.evaluate", {"expression": expr, "returnByValue": True, "timeout": 20000})
    return r.get("result", {}).get("value")

send_cdp("Network.enable")
_events.clear()

# Navigate to ssc
ssc_url = "https://ssc.mohrss.gov.cn/pc/code/index.html?dataToken=TEST"
print(f"Navigating to {ssc_url}")
send_cdp("Page.navigate", {"url": ssc_url})
time.sleep(15)

href = ev("location.href") or ""
print(f"URL: {href}")

# Check if page loaded
ready = ev("document.readyState")
print(f"readyState: {ready}")

# Page content
title = ev("document.title")
body = ev("document.body ? document.body.innerText.substring(0, 2000) : 'no body'")
print(f"Title: {title}")
print(f"Body:\n{body[:1000] if body else 'empty'}")

# Full HTML
html = ev("document.documentElement.outerHTML.substring(0, 5000)")
print(f"\n=== HTML ===\n{html[:3000] if html else 'none'}")

# Check for JS errors
errors = []
for evt in _events:
    if evt.get("method") == "Runtime.exceptionThrown":
        ex = evt.get("params", {}).get("exceptionDetails", {})
        errors.append(ex.get("text", "") + " " + str(ex.get("exception", {}).get("description", "")))
    if evt.get("method") == "Network.loadingFailed":
        params = evt.get("params", {})
        errors.append(f"Network fail: {params.get('errorText','')} - {params.get('blockedReason','')}")

if errors:
    print(f"\n=== Errors ({len(errors)}) ===")
    for e in errors[:10]:
        print(f"  {e[:150]}")

# Check network requests
print(f"\n=== Network requests ===")
reqs = []
for evt in _events:
    if evt.get("method") == "Network.requestWillBeSent":
        url = evt.get("params", {}).get("request", {}).get("url", "")
        reqs.append(url)
    if evt.get("method") == "Network.responseReceived":
        params = evt.get("params", {})
        resp = params.get("response", {})
        url = resp.get("url", "")
        status = resp.get("status", 0)
        if "ssc.mohrss" in url or "mohrss" in url:
            print(f"  {status} {url[:100]}")

print(f"\nAll requests ({len(reqs)}):")
for r in reqs[:15]:
    print(f"  {r[:100]}")

ws.close()
