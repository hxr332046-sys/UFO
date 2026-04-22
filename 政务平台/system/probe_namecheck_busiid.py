#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket


OUT = Path("G:/UFO/政务平台/data/probe_namecheck_busiid.json")


def get_core_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url, expr, timeout=15):
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
    rec = {"steps": []}
    ws, url = get_core_ws()
    rec["start_url"] = url
    if not ws:
        rec["error"] = "no_core_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    s1 = ev(
        ws,
        """(function(){
          var app=document.getElementById('app');
          return {href:location.href,hash:location.hash,hasVue:!!(app&&app.__vue__)};
        })()""",
    )
    rec["steps"].append({"step": "S1_start", "data": s1})

    route = ev(
        ws,
        """(function(){
          var app=document.getElementById('app');
          if(!app||!app.__vue__||!app.__vue__.$router) return {ok:false,err:'no_router'};
          app.__vue__.$router.push('/flow/base/name-check-info');
          return {ok:true,hash:location.hash};
        })()""",
    )
    rec["steps"].append({"step": "S2_route_namecheck", "data": route})
    time.sleep(2)

    # 先强制刷新，清理历史拦截和loading状态
    ev(
        ws,
        """(function(){
          location.reload();
          return {reloaded:true,hash:location.hash};
        })()""",
    )
    time.sleep(5)

    prep = ev(
        ws,
        r"""(function(){
          function find(vm,d){
            if(!vm||d>20) return null;
            var n=(vm.$options&&vm.$options.name)||'';
            if(n==='flow-control') return vm;
            var ch=vm.$children||[];
            for(var i=0;i<ch.length;i++){var r=find(ch[i],d+1); if(r) return r;}
            return null;
          }
          var app=document.getElementById('app');
          if(!app||!app.__vue__) return {ok:false,err:'no_app',hash:location.hash};
          var fc=find(app.__vue__,0);
          if(!fc) return {ok:false,err:'no_fc',hash:location.hash};
          var bdi=fc.$data&&fc.$data.businessDataInfo;
          if(!bdi) return {ok:false,err:'no_bdi',hash:location.hash};

          fc.$set(bdi,'entName','广西智信数据科技有限公司');
          fc.$set(bdi,'name','广西智信数据科技有限公司');
          fc.$set(bdi,'entShortName','智信数据');
          fc.$set(bdi,'entType','1100');
          fc.$set(bdi,'entTypeName','有限责任公司');
          fc.$set(bdi,'namePreFlag',false);
          fc.$set(bdi,'namePreIndustryTypeCode','I');
          fc.$set(bdi,'namePreIndustryTypeName','信息传输、软件和信息技术服务业');

          var ins=document.querySelectorAll('input.el-input__inner');
          var setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
          for(var i=0;i<ins.length;i++){
            if(ins[i].offsetParent===null||ins[i].disabled) continue;
            var ph=ins[i].placeholder||'';
            var lb='';
            var fi=ins[i].closest('.el-form-item');
            if(fi){
              var l=fi.querySelector('.el-form-item__label');
              lb=(l&&l.textContent||'').trim();
            }
            var val='';
            if(ph.indexOf('名称')>=0||lb.indexOf('名称')>=0) val='广西智信数据科技有限公司';
            else if(ph.indexOf('字号')>=0||lb.indexOf('字号')>=0) val='智信数据';
            else if(ph.indexOf('行业')>=0||lb.indexOf('行业')>=0) val='信息技术服务';
            if(val){
              setter.call(ins[i],val);
              ins[i].dispatchEvent(new Event('input',{bubbles:true}));
              ins[i].dispatchEvent(new Event('change',{bubbles:true}));
            }
          }
          window.__namecheck_resp=null;
          window.__namecheck_req=null;
          var origOpen=XMLHttpRequest.prototype.open;
          var origSend=XMLHttpRequest.prototype.send;
          XMLHttpRequest.prototype.open=function(m,u){this.__u=u; return origOpen.apply(this,arguments)};
          XMLHttpRequest.prototype.send=function(body){
            var u=this.__u||'';
            var self=this;
            if(u.indexOf('operationBusinessData')>=0||u.indexOf('BasicInfo')>=0){
              window.__namecheck_req={url:u,body:(body||'').slice(0,500),len:(body||'').length};
              self.addEventListener('load',function(){window.__namecheck_resp={url:u,status:self.status,text:self.responseText||''};});
            }
            return origSend.apply(this,arguments);
          };
          return {
            ok:true,hash:location.hash,entName:bdi.entName||bdi.name||'',
            flowData:(fc.params&&fc.params.flowData)||null
          };
        })()""",
    )
    rec["steps"].append({"step": "S3_prepare_namecheck", "data": prep})

    click = ev(
        ws,
        """(function(){
          var btns=document.querySelectorAll('button,.el-button');
          for(var i=0;i<btns.length;i++){
            var t=(btns[i].textContent||'').trim();
            if((t.indexOf('保存并下一步')>=0||t.indexOf('下一步')>=0) && !btns[i].disabled && btns[i].offsetParent!==null){
              btns[i].click();
              return {clicked:true,text:t};
            }
          }
          return {clicked:false};
        })()""",
    )
    rec["steps"].append({"step": "S4_click_next", "data": click})
    time.sleep(10)

    after = ev(
        ws,
        """(function(){
          function find(vm,d){
            if(!vm||d>20) return null;
            var n=(vm.$options&&vm.$options.name)||'';
            if(n==='flow-control') return vm;
            var ch=vm.$children||[];
            for(var i=0;i<ch.length;i++){var r=find(ch[i],d+1); if(r) return r;}
            return null;
          }
          var app=document.getElementById('app');
          var fc=(app&&app.__vue__)?find(app.__vue__,0):null;
          var p=fc&&fc.params?fc.params:{};
          var errs=Array.from(document.querySelectorAll('.el-form-item__error')).map(function(e){return (e.textContent||'').trim()}).filter(Boolean);
          return {
            href:location.href,
            hash:location.hash,
            req:window.__namecheck_req||null,
            resp:window.__namecheck_resp||null,
            flowData:p.flowData||null,
            busiCompUrlPaths:fc?fc.busiCompUrlPaths:null,
            curCompUrlPath:fc?fc.curCompUrlPath:null,
            errors:errs.slice(0,10)
          };
        })()""",
    )
    rec["steps"].append({"step": "S5_after_click", "data": after})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

