#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/continue_core_to_yunbangban.json")


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=20)
        self.ws.settimeout(1.0)
        self.i = 1

    def call(self, method, params=None, timeout=12):
        if params is None:
            params = {}
        cid = self.i
        self.i += 1
        self.ws.send(json.dumps({"id": cid, "method": method, "params": params}))
        end = time.time() + timeout
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if msg.get("id") == cid:
                if "error" in msg:
                    return {"error": msg["error"]}
                return msg.get("result", {})
        return {"error": {"message": f"timeout {method}"}}

    def ev(self, expr, timeout=60000):
        r = self.call(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout},
            timeout=15,
        )
        return (((r or {}).get("result") or {}).get("value"))

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "icpsp-web-pc/core.html#/flow/base/" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws, url = pick_ws()
    if not ws:
        rec["error"] = "no_9087_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    c = CDP(ws)
    c.call("Network.enable", {})
    rec["steps"].append({"step": "start_url", "data": url})

    for i in range(12):
        s = c.ev(
            r"""(function(){
              var txt=(document.body.innerText||'');
              var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);
              return {href:location.href,hash:location.hash,hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0,errors:errs.slice(0,10),text:txt.slice(0,1200)};
            })()"""
        )
        rec["steps"].append({"step": f"state_{i}", "data": s})
        if s.get("hasYunbangban"):
            rec["result"] = "stopped_at_yunbangban"
            break

        act = c.ev(
            r"""(function(){
              function pickFirstFromSelect(container){
                if(!container) return false;
                var inp=container.querySelector('input.el-input__inner');
                if(inp && !inp.disabled){
                  inp.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
                }else{
                  container.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
                }
                var opts=[...document.querySelectorAll('.el-select-dropdown__item,.el-cascader-node,.el-tree-node__content,li')].filter(x=>x.offsetParent!==null);
                var op=opts.find(x=>!(x.className||'').toString().includes('is-disabled'));
                if(op){op.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));return true;}
                return false;
              }
              function setByLabel(k,v){
                var items=document.querySelectorAll('.el-form-item');
                for(var i=0;i<items.length;i++){
                  var lb=items[i].querySelector('.el-form-item__label');
                  var t=(lb&&lb.textContent||'').replace(/\s+/g,' ').trim();
                  if(t.indexOf(k)>=0){
                    var inp=items[i].querySelector('input.el-input__inner,textarea.el-textarea__inner');
                    if(inp && !inp.disabled && !(inp.value||'').trim()){
                      var p=(inp.tagName==='TEXTAREA'?HTMLTextAreaElement:HTMLInputElement).prototype;
                      var setter=Object.getOwnPropertyDescriptor(p,'value').set;
                      setter.call(inp,v); inp.dispatchEvent(new Event('input',{bubbles:true})); inp.dispatchEvent(new Event('change',{bubbles:true}));
                    }
                  }
                }
              }
              function fillNameCheck(){
                var items=document.querySelectorAll('.el-form-item');
                for(var i=0;i<items.length;i++){
                  var lb=items[i].querySelector('.el-form-item__label');
                  var t=(lb&&lb.textContent||'').replace(/\s+/g,' ').trim();
                  if(t.indexOf('行政区划')>=0){ pickFirstFromSelect(items[i]); }
                  if(t.indexOf('行业')>=0){ pickFirstFromSelect(items[i]); }
                  if(t.indexOf('组织形式')>=0){ pickFirstFromSelect(items[i]); }
                  if(t.indexOf('字号')>=0){
                    var inp=items[i].querySelector('input.el-input__inner');
                    if(inp && !inp.disabled && !(inp.value||'').trim()){
                      var setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                      setter.call(inp,'桂柚百货');
                      inp.dispatchEvent(new Event('input',{bubbles:true}));
                      inp.dispatchEvent(new Event('change',{bubbles:true}));
                    }
                  }
                }
                var agree=[...document.querySelectorAll('label,span,div')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('我已阅读并同意')>=0);
                if(agree){agree.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));}
              }
              fillNameCheck();
              setByLabel('联系电话','18977514892');
              setByLabel('从业人数','3');
              setByLabel('详细地址','容州镇城西路21号2单元803室');
              setByLabel('生产经营地详细地址','容州镇城西路21号2单元803室');

              var role=['投资人','委托代理人','联络员','以个人财产出资'];
              for(var r of role){
                var e=[...document.querySelectorAll('label,span,div')].find(x=>x.offsetParent!==null&&(x.textContent||'').replace(/\s+/g,'').indexOf(r)>=0);
                if(e)e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
              }

              var order=['保存并下一步','下一步','确定'];
              var btns=[...document.querySelectorAll('button,.el-button')].filter(x=>x.offsetParent!==null&&!x.disabled);
              for(var t of order){
                var b=btns.find(x=>(x.textContent||'').replace(/\s+/g,'').indexOf(t.replace(/\s+/g,''))>=0);
                if(b){b.click(); return {clicked:true,text:(b.textContent||'').replace(/\s+/g,' ').trim()};}
              }
              return {clicked:false};
            })()"""
        )
        rec["steps"].append({"step": f"action_{i}", "data": act})
        time.sleep(5)

    end = c.ev(
        r"""(function(){
          var txt=(document.body.innerText||'');
          var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);
          return {href:location.href,hash:location.hash,hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0,errors:errs.slice(0,20)};
        })()"""
    )
    rec["final"] = end
    if "result" not in rec:
        rec["result"] = "not_reached_yunbangban"
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

