#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""通过CDP刷新页面"""
import json, time, requests, websocket

# 获取页面target
pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
page = [p for p in pages if p.get("type")=="page" and "zhjg" in p.get("url","")]
if not page:
    page = [p for p in pages if p.get("type")=="page"]
if not page:
    print("No page found")
    exit(1)

target_id = page[0].get("id","")
ws_url = page[0]["webSocketDebuggerUrl"]
print(f"Target: {target_id}")
print(f"URL: {page[0].get('url','')[:80]}")

# 通过Page.navigate导航
ws = websocket.create_connection(ws_url, timeout=10)
ws.send(json.dumps({
    "id": 1,
    "method": "Page.navigate",
    "params": {
        "url": "https://zhjg.scjdgjlj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/page?fromProject=name-register&fromPage=%2Fnamenot"
    }
}))

try:
    ws.settimeout(15)
    r = json.loads(ws.recv())
    print(f"Navigate result: {r}")
except Exception as e:
    print(f"Timeout (expected for navigation): {e}")

ws.close()

# 等待页面加载
print("Waiting for page load...")
time.sleep(15)

# 检查结果
pages2 = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
for p in pages2:
    if p.get("type") == "page":
        print(f"  {p.get('url','')[:80]}")

# 重新连接检查
try:
    page2 = [p for p in pages2 if p.get("type")=="page" and "zhjg" in p.get("url","") and "chrome-error" not in p.get("url","")]
    if page2:
        ws2 = websocket.create_connection(page2[0]["webSocketDebuggerUrl"], timeout=8)
        ws2.send(json.dumps({"id":2,"method":"Runtime.evaluate","params":{"expression":"({hash:location.hash,url:location.href.substring(0,80),title:document.title})","returnByValue":True}}))
        ws2.settimeout(10)
        r2 = json.loads(ws2.recv())
        print(f"Page state: {r2.get('result',{}).get('result',{}).get('value')}")
        ws2.close()
    else:
        print("Page still in error state")
except Exception as e:
    print(f"Check failed: {e}")

print("Done")
