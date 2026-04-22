#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/fix_capital_mode_and_empnum_02_4.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/basic-info" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url, expr, timeout=50000):
    ws = websocket.create_connection(ws_url, timeout=8)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout},
            }
        )
    )
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws, url = pick_ws()
    if not ws:
        rec["error"] = "no_basic_info_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    rec["steps"].append({"step": "S1_start", "data": {"url": url}})

    set_fields = ev(
        ws,
        r"""(function(){
          function setByLabel(labelKw, val){
            var items=document.querySelectorAll('.el-form-item');
            for(var i=0;i<items.length;i++){
              var lb=items[i].querySelector('.el-form-item__label');
              var t=(lb&&lb.textContent||'').replace(/\s+/g,' ').trim();
              if(t.indexOf(labelKw)>=0){
                var inp=items[i].querySelector('input.el-input__inner,textarea.el-textarea__inner');
                if(inp && !inp.disabled){
                  var setter=Object.getOwnPropertyDescriptor((inp.tagName==='TEXTAREA'?HTMLTextAreaElement:HTMLInputElement).prototype,'value').set;
                  setter.call(inp,val);
                  inp.dispatchEvent(new Event('input',{bubbles:true}));
                  inp.dispatchEvent(new Event('change',{bubbles:true}));
                  return {ok:true,label:t,val:val};
                }
                return {ok:false,label:t,reason:'no_input'};
              }
            }
            return {ok:false,label:labelKw,reason:'not_found'};
          }
          // 1) 从业人数
          var emp = setByLabel('从业人数','1');

          // 2) 出资方式（优先点“以个人财产出资”）
          var cap={ok:false,reason:'not_found'};
          var radios=[...document.querySelectorAll('.el-radio,.el-radio__label,span,label')].filter(e=>e.offsetParent!==null);
          for(var r of radios){
            var tx=(r.textContent||'').replace(/\s+/g,' ').trim();
            if(tx.indexOf('以个人财产出资')>=0){
              r.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
              cap={ok:true,text:tx,mode:'个人财产'};
              break;
            }
          }
          if(!cap.ok){
            for(var r2 of radios){
              var tx2=(r2.textContent||'').replace(/\s+/g,' ').trim();
              if(tx2.indexOf('以家庭共有财产作为个人出资')>=0){
                r2.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
                cap={ok:true,text:tx2,mode:'家庭共有财产'};
                break;
              }
            }
          }

          // 3) bdi 模型兜底
          function find(vm,d){if(!vm||d>20)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='flow-control')return vm;var ch=vm.$children||[];for(var i=0;i<ch.length;i++){var x=find(ch[i],d+1);if(x)return x;}return null;}
          var app=document.getElementById('app');
          var bdiSync={ok:false};
          if(app&&app.__vue__){
            var fc=find(app.__vue__,0);
            if(fc&&fc.$data&&fc.$data.businessDataInfo){
              var bdi=fc.$data.businessDataInfo;
              fc.$set(bdi,'operatorNum','1');
              fc.$set(bdi,'empNum','1');
              if(!bdi.investWay) fc.$set(bdi,'investWay','1');
              bdiSync={ok:true,operatorNum:bdi.operatorNum,empNum:bdi.empNum,investWay:bdi.investWay||null};
            }
          }
          return {emp:emp,cap:cap,bdiSync:bdiSync};
        })()""",
    )
    rec["steps"].append({"step": "S2_set_fields", "data": set_fields})

    hook = ev(
        ws,
        r"""(function(){
          window.__save_fix02_4={req:null,resp:null};
          var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
          XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__m=m;return oo.apply(this,arguments)};
          XMLHttpRequest.prototype.send=function(b){
            var u=this.__u||'';
            if(u.indexOf('operationBusinessData')>=0){
              window.__save_fix02_4.req={u:u,m:this.__m||'POST',len:(b||'').length,body:(b||'').slice(0,700)};
              var self=this;
              self.addEventListener('load',function(){window.__save_fix02_4.resp={status:self.status,text:(self.responseText||'').slice(0,700)};});
            }
            return os.apply(this,arguments);
          };
          return {ok:true};
        })()""",
    )
    rec["steps"].append({"step": "S3_hook_save", "data": hook})

    click = ev(
        ws,
        r"""(function(){
          var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('保存并下一步')>=0);
          if(!b) return {clicked:false,reason:'not_found'};
          if(b.disabled) return {clicked:false,reason:'disabled'};
          b.click(); return {clicked:true,text:(b.textContent||'').trim()};
        })()""",
    )
    rec["steps"].append({"step": "S4_click_save", "data": click})
    time.sleep(10)

    after = ev(
        ws,
        r"""(function(){
          var errs=Array.from(document.querySelectorAll('.el-form-item__error')).map(e=>(e.textContent||'').trim()).filter(Boolean);
          return {href:location.href,hash:location.hash,errors:errs.slice(0,10),save:window.__save_fix02_4||null};
        })()""",
    )
    rec["steps"].append({"step": "S5_after", "data": after})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

