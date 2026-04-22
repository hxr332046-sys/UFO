#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/fill_remaining_and_save_02_4.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        u = p.get("url", "")
        if p.get("type") == "page" and "portal.html#/index/page?fromProject=core&fromPage=%2Fflow%2Fbase%2Fbasic-info" in u:
            return p["webSocketDebuggerUrl"], p.get("url", "")
    for p in pages:
        u = p.get("url", "")
        if p.get("type") == "page" and "core.html#/flow/base/basic-info" in u:
            return p["webSocketDebuggerUrl"], p.get("url", "")
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url, expr, timeout=40000):
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
        rec["error"] = "no_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    rec["steps"].append({"step": "S1_start", "data": {"url": url}})

    # 快照（补前）
    s_before = ev(
        ws,
        r"""(function(){
          var errs=Array.from(document.querySelectorAll('.el-form-item__error')).map(function(e){return (e.textContent||'').trim();}).filter(Boolean);
          var vals={};
          var items=document.querySelectorAll('.el-form-item');
          for(var i=0;i<items.length;i++){
            var lb=items[i].querySelector('.el-form-item__label');
            var t=(lb&&lb.textContent||'').replace(/\s+/g,' ').trim();
            var inp=items[i].querySelector('input.el-input__inner,textarea.el-textarea__inner');
            if(inp&&t){vals[t]=(inp.value||'').trim();}
          }
          return {href:location.href,hash:location.hash,errors:errs.slice(0,10),vals:vals};
        })()""",
    )
    rec["steps"].append({"step": "S2_before_fill", "data": s_before})

    # 只补 3 个剩余核心空项
    fill = ev(
        ws,
        r"""(function(){
          function setInputByLabel(labelKw,val){
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
                return {ok:false,label:t,reason:'no_input_or_disabled'};
              }
            }
            return {ok:false,label:labelKw,reason:'not_found'};
          }
          return {
            entPhone:setInputByLabel('联系电话','18977514335'),
            detAddress:setInputByLabel('详细地址','容州镇容州大道88号A栋1201室'),
            detBusinessAddress:setInputByLabel('生产经营地详细地址','容州镇容州大道88号A栋1201室')
          };
        })()""",
    )
    rec["steps"].append({"step": "S3_fill_remaining", "data": fill})

    # 同步模型兜底
    sync = ev(
        ws,
        r"""(function(){
          function find(vm,d){if(!vm||d>20)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='flow-control')return vm;var ch=vm.$children||[];for(var i=0;i<ch.length;i++){var r=find(ch[i],d+1);if(r)return r;}return null;}
          var app=document.getElementById('app'); var fc=(app&&app.__vue__)?find(app.__vue__,0):null;
          if(!fc || !fc.$data || !fc.$data.businessDataInfo) return {ok:false,err:'no_bdi'};
          var bdi=fc.$data.businessDataInfo;
          fc.$set(bdi,'entPhone','18977514335');
          fc.$set(bdi,'detAddress',bdi.detAddress||'容州镇容州大道88号A栋1201室');
          fc.$set(bdi,'detBusinessAddress',bdi.detBusinessAddress||'容州镇容州大道88号A栋1201室');
          return {ok:true,entPhone:bdi.entPhone,detAddress:bdi.detAddress,detBusinessAddress:bdi.detBusinessAddress};
        })()""",
    )
    rec["steps"].append({"step": "S4_sync_model", "data": sync})

    # 拦截保存
    hook = ev(
        ws,
        r"""(function(){
          window.__save02_4={req:null,resp:null};
          var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
          XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__m=m;return oo.apply(this,arguments)};
          XMLHttpRequest.prototype.send=function(b){
            var u=this.__u||'';
            if(u.indexOf('operationBusinessData')>=0){
              window.__save02_4.req={u:u,m:this.__m||'POST',len:(b||'').length,body:(b||'').slice(0,700)};
              var self=this;
              self.addEventListener('load',function(){window.__save02_4.resp={status:self.status,text:(self.responseText||'').slice(0,700)};});
            }
            return os.apply(this,arguments);
          };
          return {ok:true};
        })()""",
    )
    rec["steps"].append({"step": "S5_hook_save", "data": hook})

    click = ev(
        ws,
        r"""(function(){
          var b=[...document.querySelectorAll('button,.el-button')].find(function(x){return x.offsetParent!==null && (x.textContent||'').indexOf('保存并下一步')>=0;});
          if(!b) return {clicked:false,reason:'not_found'};
          if(b.disabled) return {clicked:false,reason:'disabled'};
          b.click();
          return {clicked:true,text:(b.textContent||'').trim()};
        })()""",
    )
    rec["steps"].append({"step": "S6_click_save", "data": click})
    time.sleep(10)

    s_after = ev(
        ws,
        r"""(function(){
          var errs=Array.from(document.querySelectorAll('.el-form-item__error')).map(function(e){return (e.textContent||'').trim();}).filter(Boolean);
          return {href:location.href,hash:location.hash,errors:errs.slice(0,10),save:window.__save02_4||null};
        })()""",
    )
    rec["steps"].append({"step": "S7_after_save", "data": s_after})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

