"""Fully automated CDP capture: navigate to establish flow and capture producePdf.
Uses CDP to: 1) navigate to core.html, 2) monitor network for producePdf.
"""
import sys, json, time, websocket, copy
sys.path.insert(0, 'system')

CDP_PORT = 9225
import requests as http_requests

# Get the target page
tabs = http_requests.get(f"http://127.0.0.1:{CDP_PORT}/json").json()
# Find or create icpsp tab
target = None
for tab in tabs:
    if 'zhjg' in tab.get('url', '') or 'icpsp' in tab.get('url', ''):
        target = tab
        break
if not target:
    target = tabs[0]

ws_url = target['webSocketDebuggerUrl']
print(f"Connecting to: {ws_url[:60]}...")
ws = websocket.create_connection(ws_url, timeout=60)
msg_id = 1
pending_events = []

def send_cdp(method, params=None, timeout=10):
    global msg_id
    msg = {"id": msg_id, "method": method}
    if params:
        msg["params"] = params
    ws.send(json.dumps(msg))
    mid = msg_id
    msg_id += 1
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            ws.settimeout(1)
            resp = json.loads(ws.recv())
        except websocket.WebSocketTimeoutException:
            continue
        if resp.get("id") == mid:
            return resp
        else:
            pending_events.append(resp)
    return {"error": "timeout"}

# Step 1: Enable Network monitoring
print("Enabling Network monitoring...")
send_cdp("Network.enable", {"maxPostDataSize": 131072})

# Step 2: Navigate to the establish flow page
busi_id = "2048388847616139266"
name_id = "2048387710974500865"
ent_type = "4540"
busi_type = "02_4"
core_url = f"https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html#/flow/base?fromProject=core&busiType={busi_type}&entType={ent_type}&nameId={name_id}"

print(f"Navigating to: {core_url[:80]}...")
send_cdp("Page.enable")
nav_result = send_cdp("Page.navigate", {"url": core_url}, timeout=15)
print(f"Navigation result: {nav_result.get('result', {}).get('frameId', 'N/A')}")

# Step 3: Wait for page load and capture all relevant network requests
captured = []
keywords = ["producePdf", "YbbSelect", "loadCurrentLocation", "operationBusinessDataInfo",
            "loadBusinessDataInfo", "preSubmit", "PreElectronicDoc"]

print("\nMonitoring network for 120 seconds...")
print("The page should auto-load to YbbSelect. If you need to click save, do it in the browser.")

start_time = time.time()
timeout = 120

# Process pending events first
for evt in pending_events:
    method = evt.get("method", "")
    if method == "Network.requestWillBeSent":
        params = evt.get("params", {})
        url = params.get("request", {}).get("url", "")
        if any(kw in url for kw in keywords):
            post_data = params.get("request", {}).get("postData", "")
            entry = {"url": url, "method": params.get("request", {}).get("method"), 
                     "postData": post_data, "timestamp": time.time() - start_time}
            captured.append(entry)
            print(f"\n[{time.time()-start_time:.1f}s] CAPTURED: {entry['method']} {url[:100]}")

while time.time() - start_time < timeout:
    ws.settimeout(1)
    try:
        msg = json.loads(ws.recv())
    except websocket.WebSocketTimeoutException:
        continue
    except Exception as e:
        print(f"WS error: {e}")
        break
    
    method = msg.get("method", "")
    
    if method == "Network.requestWillBeSent":
        params = msg.get("params", {})
        request = params.get("request", {})
        url = request.get("url", "")
        req_method = request.get("method", "")
        post_data = request.get("postData", "")
        
        if any(kw in url for kw in keywords):
            entry = {"url": url, "method": req_method, "postData": post_data, 
                     "timestamp": time.time() - start_time}
            captured.append(entry)
            print(f"\n[{time.time()-start_time:.1f}s] CAPTURED: {req_method} {url[:120]}")
            if post_data:
                try:
                    body = json.loads(post_data)
                    print(f"  Body keys: {list(body.keys())}")
                    if body.get('flowData'):
                        fd = body['flowData']
                        print(f"  flowData: busiId={fd.get('busiId')} currCompUrl={fd.get('currCompUrl')} status={fd.get('status')}")
                        print(f"  flowData keys: {list(fd.keys())}")
                    if body.get('linkData'):
                        ld = body['linkData']
                        print(f"  linkData: token={ld.get('token')} compUrl={ld.get('compUrl')} opeType={ld.get('opeType')}")
                        print(f"  linkData keys: {list(ld.keys())}")
                    for k in ['isSelectYbb', 'isOptional', 'signInfo', 'itemId']:
                        if k in body:
                            print(f"  {k}={body.get(k)}")
                except:
                    print(f"  PostData: {post_data[:300]}")
    
    elif method == "Network.responseReceived":
        params = msg.get("params", {})
        response = params.get("response", {})
        url = response.get("url", "")
        status = response.get("status")
        
        if any(kw in url for kw in keywords):
            request_id = params.get("requestId")
            try:
                resp = send_cdp("Network.getResponseBody", {"requestId": request_id}, timeout=5)
                body_text = resp.get("result", {}).get("body", "")
                if body_text:
                    try:
                        body_json = json.loads(body_text)
                        code = body_json.get("code", "")
                        msg_text = body_json.get("msg", "")
                        print(f"  [RESP] {status} code={code} msg={msg_text}")
                        for entry in captured:
                            if entry["url"] == url and "response" not in entry:
                                entry["response"] = body_json
                                break
                    except:
                        print(f"  [RESP] {status} body={body_text[:200]}")
            except:
                print(f"  [RESP] {status}")

# Save all captured data
out_path = "packet_lab/out/cdp_captured_producepdf.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(captured, f, ensure_ascii=False, indent=2)
print(f"\nCaptured {len(captured)} requests, saved to {out_path}")
ws.close()
