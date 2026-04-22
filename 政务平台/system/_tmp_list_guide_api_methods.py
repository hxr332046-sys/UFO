#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import requests
import websocket

GUIDE_URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=4540&marPrId=&marUniscId="


def main():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = None
    for p in pages:
        if p.get("type") == "page" and ":9087" in (p.get("url") or "") and "icpsp-web-pc" in (p.get("url") or ""):
            ws_url = p["webSocketDebuggerUrl"]
            break
    if not ws_url:
        print(json.dumps({"error": "no_page"}, ensure_ascii=False))
        return
    ws = websocket.create_connection(ws_url, timeout=20)

    def run(msg_id, expr, timeout=60000):
        ws.send(
            json.dumps(
                {
                    "id": msg_id,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout},
                }
            )
        )
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == msg_id:
                return m.get("result", {}).get("result", {}).get("value")

    run(1, f"location.href={json.dumps(GUIDE_URL, ensure_ascii=False)}", 60000)
    result = run(
        2,
        r"""(function(){
          function walk(vm,d){
            if(!vm||d>20) return null;
            var n=(vm.$options&&vm.$options.name)||'';
            if(n==='index' && vm.$api && vm.$api.guide) return vm;
            var ch=vm.$children||[];
            for(var i=0;i<ch.length;i++){var r=walk(ch[i],d+1); if(r) return r;}
            return null;
          }
          var vm=walk(document.getElementById('app')&&document.getElementById('app').__vue__,0);
          if(!vm) return {error:'no_vm',href:location.href,hash:location.hash};
          var g=vm.$api&&vm.$api.guide;
          var keys=Object.keys(g||{});
          var src={};
          for(var i=0;i<keys.length;i++){
            var k=keys[i];
            try{
              if(typeof g[k]==='function') src[k]=g[k].toString().slice(0,300);
            }catch(e){}
          }
          return {href:location.href,hash:location.hash,keys:keys,src:src};
        })()""",
        60000,
    )
    ws.close()
    print(json.dumps(result, ensure_ascii=False, indent=2)[:24000])


if __name__ == "__main__":
    main()

