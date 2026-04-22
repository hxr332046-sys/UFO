#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查Chrome重启后页面状态"""
import json, time, requests, websocket

def ev(js, timeout=10):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        page = [p for p in pages if p.get("type")=="page" and "zhjg" in (p.get("url","") or "chrome://" not in p.get("url",""))]
        if not page:
            page = [p for p in pages if p.get("type")=="page"]
        if not page:
            return "ERROR:no_page"
        ws_url = page[0]["webSocketDebuggerUrl"]
        ws = websocket.create_connection(ws_url, timeout=8)
        ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
        ws.settimeout(timeout+2)
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == 1:
                ws.close()
                return r.get("result",{}).get("result",{}).get("value")
    except Exception as e:
        return f"ERROR:{e}"

# 检查页面
cur = ev("({hash:location.hash,url:location.href.substring(0,100),title:document.title})")
print(f"当前: {cur}")

# 列出所有CDP targets
targets = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
for t in targets:
    if t.get('type') in ['page','iframe']:
        print(f"  {t.get('type')}: {t.get('url','')[:80]}")
