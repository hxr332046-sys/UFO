#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import requests
import websocket

TARGET = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html#/flow/base/basic-info"

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
page = None
for p in pages:
    u = p.get("url", "")
    if p.get("type") == "page" and "portal.html#/index/page?fromProject=core&fromPage=%2Fflow%2Fbase%2Fbasic-info" in u:
        page = p
        break
if not page and pages:
    page = [p for p in pages if p.get("type") == "page"][0]

ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=8)
expr = f"location.href='{TARGET}'"
ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "timeout": 15000}}))
while True:
    m = json.loads(ws.recv())
    if m.get("id") == 1:
        print("ok")
        break
ws.close()

