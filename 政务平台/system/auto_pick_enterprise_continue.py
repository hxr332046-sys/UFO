#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/auto_pick_enterprise_continue.json")
MYSPACE_URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/company/my-space/space-index"


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        u = p.get("url", "")
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in u:
            return p["webSocketDebuggerUrl"], u
    for p in pages:
        if p.get("type") == "page":
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, ""


def ev(ws_url, expr, timeout=120000):
    ws = websocket.create_connection(ws_url, timeout=20)
    ws.settimeout(1.0)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout},
            }
        )
    )
    end = time.time() + max(20, timeout / 1000 + 20)
    try:
        while time.time() < end:
            try:
                msg = json.loads(ws.recv())
            except Exception:
                continue
            if msg.get("id") == 1:
                return ((msg.get("result") or {}).get("result") or {}).get("value")
        return {"ok": False, "msg": "timeout"}
    finally:
        try:
            ws.close()
        except Exception:
            pass


def main():
    ws_url, cur = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "start_url": cur}
    if not ws_url:
        rec["result"] = "no_ws"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    rec["nav"] = ev(ws_url, f"location.href={json.dumps(MYSPACE_URL, ensure_ascii=False)}", timeout=30000)
    time.sleep(4)
    rec["pick_and_click"] = ev(
        ws_url,
        r"""(async function(){
          function clean(s){return String(s||'').replace(/\s+/g,' ').trim();}
          function isVis(el){return !!(el && el.offsetParent!==null);}
          window.__pick_cap={resps:[]};
          var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
          XMLHttpRequest.prototype.open=function(m,u){this.__u=u; return oo.apply(this,arguments);};
          XMLHttpRequest.prototype.send=function(b){
            var self=this; self.addEventListener('loadend', function(){
              var t=String(self.responseText||'');
              if((self.__u||'').indexOf('/mattermanager/matters/operate')>=0 || t.indexOf('"route"')>=0){
                window.__pick_cap.resps.push({u:String(self.__u||''),s:self.status,t:t.slice(0,5000)});
              }
            });
            return os.apply(this,arguments);
          };
          try{
            var rows=[].slice.call(document.querySelectorAll('tbody tr,.el-table__row')).filter(isVis);
            var chosen=null, chosenReason='';
            for(var i=0;i<rows.length;i++){
              var t=clean(rows[i].innerText||'');
              if((t.indexOf('企业开办')>=0 || t.indexOf('设立')>=0) && t.indexOf('继续办理')>=0){
                chosen=rows[i]; chosenReason='enterprise_or_establish'; break;
              }
            }
            if(!chosen){
              for(var j=0;j<rows.length;j++){
                var t2=clean(rows[j].innerText||'');
                if(t2.indexOf('继续办理')>=0){ chosen=rows[j]; chosenReason='fallback_first_continue'; break; }
              }
            }
            if(!chosen){
              return {ok:false,msg:'no_row_with_continue'};
            }
            var btn=[].slice.call(chosen.querySelectorAll('button,.el-button,a,span')).find(function(x){return isVis(x)&&clean(x.textContent).indexOf('继续办理')>=0;});
            if(!btn){
              return {ok:false,msg:'row_without_continue_button',rowText:clean(chosen.innerText||'')};
            }
            btn.click();
            await new Promise(function(r){setTimeout(r,3500);});
            function parseRoute(t){
              try{
                var j=JSON.parse(t), d=(j&&j.data)||{};
                if(d&&d.route) return d.route;
                if(d&&d.data&&d.data.route) return d.data.route;
              }catch(e){}
              return null;
            }
            var route=null;
            for(var k=0;k<window.__pick_cap.resps.length;k++){
              route=parseRoute(window.__pick_cap.resps[k].t||'');
              if(route) break;
            }
            return {
              ok:true,
              chosenReason:chosenReason,
              rowText:clean(chosen.innerText||'').slice(0,300),
              route:route,
              captures:window.__pick_cap.resps.slice(0,2)
            };
          } finally {
            XMLHttpRequest.prototype.open=oo;
            XMLHttpRequest.prototype.send=os;
          }
        })()""",
        timeout=120000,
    )
    rec["end_state"] = ev(
        ws_url,
        r"""(function(){
          var txt=(document.body.innerText||'').replace(/\s+/g,' ').trim();
          return {href:location.href,hash:location.hash,hasNameCheck:location.href.indexOf('name-check-info')>=0,hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0,text:txt.slice(0,220)};
        })()""",
        timeout=30000,
    )
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

