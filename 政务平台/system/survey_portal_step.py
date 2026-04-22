#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""普查当前 portal 全部服务页的入口框架信息。"""

import json
import requests
import websocket


def eval_js(ws_url: str, expr: str, timeout: int = 12):
    ws = websocket.create_connection(ws_url, timeout=8)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "timeout": timeout * 1000},
            }
        )
    )
    ws.settimeout(timeout + 2)
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close()
            return msg.get("result", {}).get("result", {}).get("value")


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    target = [p for p in pages if p.get("type") == "page" and "portal.html#/index/page" in p.get("url", "")]
    print(f"targets={len(target)}")
    if not target:
        print("no portal page found")
        return
    print(target[0]["url"])

    expr = r"""(function(){
  var cards = Array.from(document.querySelectorAll('[class*="card"], .all-server-item, .service-item, .item'))
    .filter(function(e){return e.offsetParent!==null;});
  var texts = cards.map(function(c){return (c.textContent||'').trim().replace(/\s+/g,' ').slice(0,120);}).filter(Boolean);
  var entries = Array.from(document.querySelectorAll('a,button,div'))
    .filter(function(e){
      if(e.offsetParent===null) return false;
      var t=(e.textContent||'');
      return /设立登记|变更（备案）登记|普通注销登记|经营主体（变更）名称自主申报/.test(t);
    })
    .map(function(e){return (e.textContent||'').trim().replace(/\s+/g,' ').slice(0,80);});
  return {title:document.title,url:location.href,hash:location.hash,cards:texts.slice(0,20),entryMatches:entries.slice(0,20)};
})()"""
    info = eval_js(target[0]["webSocketDebuggerUrl"], expr)
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

