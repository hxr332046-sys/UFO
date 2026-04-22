#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航回basic-info页面"""
import json, requests, websocket, time

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
page = [p for p in pages if p.get("type") == "page" and "zhjg" in p.get("url", "")][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=8)

def ev(js, timeout=15):
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": js, "returnByValue": True, "timeout": timeout * 1000}}))
    ws.settimeout(timeout + 2)
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == 1:
            return r.get("result", {}).get("result", {}).get("value")

# 导航到core.html
print("导航到core.html#/flow/base/basic-info...")
ev("location.href='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html#/flow/base/basic-info'")
time.sleep(8)

r = ev("({hash:location.hash, url:location.href, formCount:document.querySelectorAll('.el-form-item').length})")
print(f"页面: {r}")

ws.close()
