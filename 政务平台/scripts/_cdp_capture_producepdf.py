"""CDP capture: automate YbbSelect in browser and capture producePdf request.
Connects to Edge Dev with CDP, navigates to establish flow, clicks save on YbbSelect,
and captures the producePdf network request.
"""
import sys, json, time, asyncio
sys.path.insert(0, 'system')

CDP_PORT = 9225

# Get the target page
import requests
tabs = requests.get(f"http://127.0.0.1:{CDP_PORT}/json").json()
target = None
for tab in tabs:
    if 'zhjg' in tab.get('url', '') or 'icpsp' in tab.get('url', ''):
        target = tab
        break
if not target:
    target = tabs[0]

ws_url = target['webSocketDebuggerUrl']
print(f"Connecting to: {ws_url}")
print(f"Page: {target.get('title', '')} - {target.get('url', '')[:80]}")

ws = websocket.create_connection(ws_url, timeout=30)
msg_id = 1

def send_cdp(method, params=None):
    global msg_id
    msg = {"id": msg_id, "method": method}
    if params:
        msg["params"] = params
    ws.send(json.dumps(msg))
    msg_id += 1
    while True:
        resp = json.loads(ws.recv())
        if resp.get("id") == msg_id - 1:
            return resp

# Enable Network domain
send_cdp("Network.enable")
send_cdp("Network.enable", {"maxPostDataSize": 65536})
print("Network monitoring enabled")

captured = []
keywords = ["producePdf", "YbbSelect", "loadCurrentLocation", "operationBusinessDataInfo",
            "loadBusinessDataInfo", "preSubmit", "PreElectronicDoc"]
print(f"Listening for: {keywords}")
print("Please operate the browser to YbbSelect save...")

start_time = time.time()
timeout = 300

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
            entry = {"url": url, "method": req_method, "postData": post_data, "timestamp": time.time()}
            captured.append(entry)
            print(f"\n[CAPTURED] {req_method} {url[:120]}")
            if post_data:
                try:
                    body = json.loads(post_data)
                    print(f"  Body keys: {list(body.keys())}")
                    if body.get('flowData'):
                        fd = body['flowData']
                        print(f"  flowData.busiId={fd.get('busiId')} currCompUrl={fd.get('currCompUrl')} status={fd.get('status')}")
                        print(f"  flowData keys: {list(fd.keys())}")
                    if body.get('linkData'):
                        ld = body['linkData']
                        print(f"  linkData.token={ld.get('token')} compUrl={ld.get('compUrl')}")
                        print(f"  linkData keys: {list(ld.keys())}")
                    for k in ['isSelectYbb', 'isOptional', 'signInfo', 'itemId']:
                        if k in body:
                            print(f"  {k}={body.get(k)}")
                except:
                    print(f"  PostData: {post_data[:200]}")
    
    elif method == "Network.responseReceived":
        params = msg.get("params", {})
        response = params.get("response", {})
        url = response.get("url", "")
        status = response.get("status")
        
        if any(kw in url for kw in keywords):
            request_id = params.get("requestId")
            try:
                resp = send_cdp("Network.getResponseBody", {"requestId": request_id})
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

out_path = "packet_lab/out/cdp_captured_producepdf.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(captured, f, ensure_ascii=False, indent=2)
print(f"\nCaptured {len(captured)} requests, saved to {out_path}")
ws.close()
