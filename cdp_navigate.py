#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Navigate to 政务平台 via CDP"""

import json
import websocket
import time
import requests

CDP_PORT = 9225
GOV_URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone?fromProject=portal&fromPage=%2Flogin%2FauthPage&busiType=02_4&merge=Y"

pages = requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5).json()
page = [p for p in pages if p.get("type") == "page"][0]
ws_url = page["webSocketDebuggerUrl"]
print(f"Connecting: {ws_url}")
ws = websocket.create_connection(ws_url, timeout=15)

ws.send(json.dumps({"id": 1, "method": "Page.navigate", "params": {"url": GOV_URL}}))
r = json.loads(ws.recv())
print("Navigate:", json.dumps(r, ensure_ascii=False))

time.sleep(8)

ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {"expression": "document.title + ' | ' + location.href", "returnByValue": True}}))
r2 = json.loads(ws.recv())
print("Page:", r2.get("result", {}).get("result", {}).get("value", ""))
ws.close()
