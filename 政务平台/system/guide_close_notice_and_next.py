#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/guide_close_notice_and_next.json")
GUIDE_URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=4540&marPrId=&marUniscId="


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def ev(ws_url, expr, timeout=70000):
    ws = websocket.create_connection(ws_url, timeout=20)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close()
            return msg.get("result", {}).get("result", {}).get("value")


def main():
    ws = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    if not ws:
        rec["error"] = "no_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    ev(ws, f"location.href={json.dumps(GUIDE_URL, ensure_ascii=False)}", timeout=20000)
    time.sleep(5)
    rec["steps"].append({"step": "before", "data": ev(ws, r"""(function(){return {href:location.href,hash:location.hash,text:(document.body.innerText||'').slice(0,1200)};})()""")})
    rec["steps"].append(
        {
            "step": "close_and_next",
            "data": ev(
                ws,
                r"""(async function(){
                  function visibleButtons(){
                    return [...document.querySelectorAll('button,.el-button')].filter(x=>x.offsetParent!==null&&!x.disabled);
                  }
                  function clickBtn(kw){
                    var b=visibleButtons().find(x=>(x.textContent||'').replace(/\s+/g,'').indexOf(kw.replace(/\s+/g,''))>=0);
                    if(!b) return false;
                    b.click(); return true;
                  }
                  function clickText(kw){
                    var nodes=[...document.querySelectorAll('label,.tni-radio,.tni-radio__label,span,div')].filter(x=>x.offsetParent!==null);
                    for(var n of nodes){
                      var t=(n.textContent||'').replace(/\s+/g,' ').trim();
                      if(t===kw||t.indexOf(kw)>=0){
                        ['mousedown','mouseup','click'].forEach(function(tp){
                          n.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window}));
                        });
                        return true;
                      }
                    }
                    return false;
                  }
                  var acts=[];
                  for(var i=0;i<3;i++){
                    if(clickBtn('关 闭')) acts.push('close_notice');
                    if(clickBtn('确定')) acts.push('confirm');
                    await new Promise(function(r){setTimeout(r,300);});
                  }
                  clickText('个人独资企业')&&acts.push('pick_type');
                  clickText('未申请')&&acts.push('pick_name_mode');
                  await new Promise(function(r){setTimeout(r,300);});
                  clickBtn('下一步')&&acts.push('next');
                  await new Promise(function(r){setTimeout(r,1200);});
                  clickBtn('确定')&&acts.push('confirm_after_next');
                  return {ok:true,acts:acts,href:location.href,hash:location.hash};
                })()""",
            ),
        }
    )
    time.sleep(4)
    rec["steps"].append({"step": "after", "data": ev(ws, r"""(function(){return {href:location.href,hash:location.hash,text:(document.body.innerText||'').slice(0,1200)};})()""")})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()
