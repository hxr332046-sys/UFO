#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查引导页并找到导航按钮"""
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

# 当前页面
r0 = ev("({hash:location.hash, url:location.href})")
print(f"当前页面: {r0}")

# 所有按钮和链接
r1 = ev("""(function(){
    var btns=document.querySelectorAll('button, a, .el-button, .el-step, .guide-item, .card-item, .next-btn');
    var result=[];
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        var cls=btns[i].className||'';
        if(t.length>0&&t.length<50){
            result.push({text:t, tag:btns[i].tagName, class:cls.substring(0,60)});
        }
    }
    return result;
})()""")
print(f"\n按钮/链接 ({len(r1 or [])}个):")
for b in (r1 or []):
    print(f"  <{b['tag']}> {b['text']}  class={b['class']}")

# 查找router-link
r2 = ev("""(function(){
    var links=document.querySelectorAll('[data-v-], .router-link, a[href]');
    var result=[];
    for(var i=0;i<links.length;i++){
        var href=links[i].getAttribute('href')||'';
        var t=links[i].textContent?.trim()||'';
        if(t.length>0&&t.length<50)result.push({text:t,href:href});
    }
    return result;
})()""")
print(f"\n导航链接:")
for l in (r2 or []):
    print(f"  {l['text']} → {l['href']}")

ws.close()
