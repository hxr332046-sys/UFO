#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
在 guide/base 上安装 XHR/fetch hook，执行 flowSave/下一步，并把 UI+接口尾部证据落盘。

目标：定位“卡住”到底是前端校验短路、弹窗阻塞，还是 icpsp-api 返回导致不跳转。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/phase1_flow_save_with_hook_latest.json")


def pick_ws() -> tuple[Optional[str], Optional[str]]:
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in (p.get("url") or ""):
            return p.get("webSocketDebuggerUrl"), p.get("url")
    for p in pages:
        if p.get("type") == "page" and ":9087" in (p.get("url") or ""):
            return p.get("webSocketDebuggerUrl"), p.get("url")
    return None, None


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=25)
        self.ws.settimeout(1.0)
        self.i = 1

    def call(self, method: str, params: Optional[dict] = None, *, timeout: float = 18) -> Dict[str, Any]:
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
                if msg.get("error"):
                    return {"error": msg["error"]}
                return msg.get("result") or {}
        return {"error": {"message": f"timeout {method}"}}

    def ev(self, expr: str, *, timeout_ms: int = 90000) -> Any:
        r = self.call(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": int(timeout_ms)},
            timeout=20,
        )
        return (((r or {}).get("result") or {}).get("value"))

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass


HOOK_JS = r"""(function(){
  window.__ufo_cap = window.__ufo_cap || {installed:false,items:[]};
  function pushOne(x){ try{ x.ts=Date.now(); window.__ufo_cap.items.push(x);
    if(window.__ufo_cap.items.length>200) window.__ufo_cap.items.shift(); }catch(e){} }
  if(!window.__ufo_cap.installed){
    var XO=XMLHttpRequest.prototype.open, XS=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open=function(m,u){ this.__ufo={m:m,u:u}; return XO.apply(this,arguments); };
    XMLHttpRequest.prototype.send=function(body){
      var self=this, u=(self.__ufo&&self.__ufo.u)||'';
      // 调试：抓本域所有请求（不要只限 icpsp-api）
      if(String(u).indexOf('zhjg.scjdglj.gxzf.gov.cn')>=0 || String(u).indexOf('/icpsp-api/')>=0){
        pushOne({t:'xhr',m:(self.__ufo&&self.__ufo.m)||'',u:u.slice(0,260),body:String(body||'').slice(0,800)});
        self.addEventListener('loadend',function(){
          pushOne({t:'xhr_end',u:u.slice(0,260),status:self.status,resp:String(self.responseText||'').slice(0,800)});
        });
      }
      return XS.apply(this,arguments);
    };
    var OF=window.fetch;
    if(typeof OF==='function'){
      window.fetch=function(input,init){
        try{
          var u=(typeof input==='string')?input:(input&&input.url)||'';
          if(String(u).indexOf('zhjg.scjdglj.gxzf.gov.cn')>=0 || String(u).indexOf('/icpsp-api/')>=0){
            var m=(init&&init.method)||'GET';
            var b=(init&&init.body)?String(init.body).slice(0,1200):'';
            pushOne({t:'fetch',m:m,u:String(u).slice(0,260),body:b});
            return OF.apply(this,arguments).then(function(res){
              try{
                return res.clone().text().then(function(txt){
                  pushOne({t:'fetch_end',u:String(u).slice(0,260),status:res.status,resp:String(txt||'').slice(0,800)});
                  return res;
                });
              }catch(e){ return res; }
            });
          }
        }catch(e){}
        return OF.apply(this,arguments);
      };
    }
    window.__ufo_cap.installed=true;
  }
  window.__ufo_cap.items=[];
  return {ok:true};
})()"""


SNAP_UI_JS = r"""(function(){
  function t(x){return (x&&x.textContent||'').replace(/\s+/g,' ').trim();}
  var errs=[...document.querySelectorAll('.el-form-item__error,.el-message__content')].map(t).filter(Boolean).slice(0,25);
  var mbs=[...document.querySelectorAll('.el-message-box__wrapper')].filter(w=>w.offsetParent!==null).map(w=>{
    var m=w.querySelector('.el-message-box__message'); return m? (m.innerText||'').replace(/\s+/g,' ').trim().slice(0,500):'';
  }).filter(Boolean).slice(0,5);
  var btns=[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null).map(b=>({text:t(b),disabled:!!b.disabled,cls:(b.className||'').slice(0,60)})).filter(b=>b.text).slice(0,30);
  return {href:location.href,hash:location.hash,title:document.title,errors:errs,messageBox:mbs,buttons:btns,body:(document.body&&document.body.innerText||'').replace(/\s+/g,' ').trim().slice(0,260)};
})()"""

REFRESH_JS = r"""(function(){ location.reload(); return {ok:true,reload:true,href:location.href}; })()"""

CLICK_NEXT_JS = r"""(function(){
  function clean(s){return (s||'').replace(/\s+/g,' ').trim();}
  var btns=[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null&&!b.disabled);
  var nxt=btns.find(b=>clean(b.textContent).indexOf('保存并下一步')>=0) || btns.find(b=>clean(b.textContent).indexOf('下一步')>=0);
  if(nxt){ nxt.click(); return {ok:true,clicked:clean(nxt.textContent)}; }
  // 仅在弹窗可见时才点“确定”
  var mb=document.querySelector('.el-message-box__wrapper:not([style*="display: none"])');
  if(mb && mb.offsetParent!==null){
    var ok=btns.find(b=>clean(b.textContent).indexOf('确定')>=0) || null;
    if(ok){ ok.click(); return {ok:true,clicked:'确定'}; }
  }
  return {ok:false,seen:btns.map(b=>clean(b.textContent)).filter(Boolean).slice(0,12)};
})()"""


FLOW_SAVE_JS = r"""(async function(){
  function walk(vm,d){
    if(!vm||d>14) return null;
    var n=(vm.$options&&vm.$options.name)||'';
    if(n==='index' && typeof vm.flowSave==='function') return vm;
    for(var ch of (vm.$children||[])){ var r=walk(ch,d+1); if(r) return r; }
    return null;
  }
  var app=document.getElementById('app');
  var vm=app&&app.__vue__?walk(app.__vue__,0):null;
  if(!vm) return {ok:false,msg:'no_vm'};
  // 1) 强制设置区划 picker + form（容县案例）
  var path=[
    {value:'450000',text:'广西壮族自治区'},
    {value:'450900',text:'玉林市'},
    {value:'450921',text:'容县'}
  ];
  try{
    var picker = (vm.$refs&&vm.$refs.tniDataPicker) ? vm.$refs.tniDataPicker : null;
    if(picker){
      try{ picker.selected=JSON.parse(JSON.stringify(path)); }catch(e){}
      try{ picker.inputSelected=JSON.parse(JSON.stringify(path)); }catch(e){}
      try{ picker.checkValue=['450000','450900','450921']; }catch(e){}
      try{ picker.selectedIndex=2; }catch(e){}
      try{ picker.$emit('input',['450000','450900','450921']); }catch(e){}
      try{ picker.$emit('change', JSON.parse(JSON.stringify(path))); }catch(e){}
      try{ picker.updateBindData&&picker.updateBindData(); }catch(e){}
      try{ picker.updateSelected&&picker.updateSelected(); }catch(e){}
      try{ picker.onchange&&picker.onchange(JSON.parse(JSON.stringify(path))); }catch(e){}
    }
  }catch(e){}
  try{
    vm.$set(vm.form,'entType','1100');
    vm.$set(vm.form,'nameCode','0');
    vm.$set(vm.form,'isnameType','0');
    vm.$set(vm.form,'choiceName','0');
    vm.$set(vm.form,'havaAdress','1');
    vm.$set(vm.form,'distCode','450921');
    vm.$set(vm.form,'streetCode','450921');
    vm.$set(vm.form,'streetName','容县');
    vm.$set(vm.form,'address','容县');
    vm.$set(vm.form,'detAddress','容州镇车站西路富盛广场1幢3203号房');
  }catch(e){}

  // 2) UI 单选兜底：点“未申请”“内资有限公司”“确定”
  try{
    function clean(s){return (s||'').replace(/\\s+/g,' ').trim();}
    var nodes=[...document.querySelectorAll('label,span,div,li,a')].filter(e=>e.offsetParent!==null);
    function clickTxt(w){
      for(var n of nodes){
        var t=clean(n.textContent||'');
        if(!t||t.length>40) continue;
        if(t===w||t.indexOf(w)>=0){
          (n.closest('label,.tni-radio,.el-radio')||n).dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
          return t;
        }
      }
      return null;
    }
    clickTxt('未申请');
    clickTxt('内资有限公司');
    var ok=[...document.querySelectorAll('button,.el-button')].find(b=>b.offsetParent!==null && clean(b.textContent||'').indexOf('确定')>=0 && !b.disabled);
    if(ok) ok.click();
  }catch(e){}

  // 2b) VM 级兜底：同步 choiceName/entTypeCode 并调用组件自带切换方法
  try{
    if(typeof vm.choiceName!=='undefined') vm.$set(vm,'choiceName','内资有限公司');
    if(typeof vm.entTypeCode!=='undefined') vm.$set(vm,'entTypeCode','1100');
    if(typeof vm.entTypeRealy!=='undefined') vm.$set(vm,'entTypeRealy','gs');
    if(typeof vm.checkchange==='function'){ try{ vm.checkchange('1100', true); }catch(e){} }
    if(typeof vm.changeEntType==='function'){ try{ vm.changeEntType('1100'); }catch(e){} }
  }catch(e){}

  // 2c) 街道层级兜底：尝试拉取街道列表并补齐 streetCode（页面提示到“街道”）
  try{
    if(typeof vm.queryRegcodeAndStreet==='function'){
      var q = vm.queryRegcodeAndStreet();
      if(q && typeof q.then==='function') await q;
    }
    // distList 常见为 [省,市,区县,街道] code 列表
    if(Array.isArray(vm.distList) && vm.distList.length>=4){
      var sc = String(vm.distList[vm.distList.length-1]||'');
      if(sc){
        try{ vm.$set(vm.form,'streetCode', sc); }catch(e){}
        try{ vm.$set(vm.form,'distCode', String(vm.distList[2]||vm.form.distCode||'450921')); }catch(e){}
      }
    }
  }catch(e){}

  // patch refs getFormData if missing
  var patched=[];
  var refs=vm.$refs||{};
  try{
    // Proxy：任何缺失的 ref 都返回 stub，避免 xxx.getFormData of undefined
    vm.$refs = new Proxy(refs, {
      get: function(target, prop){
        var v = target[prop];
        if(v==null){
          return { getFormData: function(){ return {}; } };
        }
        return v;
      }
    });
    refs = vm.$refs;
    patched.push('refs_proxy');
  }catch(e){}
  Object.keys(refs).forEach(function(k){
    var r=refs[k];
    if(Array.isArray(r)){
      r.forEach(function(it,idx){
        if(it && typeof it.getFormData!=='function'){
          it.getFormData=function(){return {};};
          patched.push(k+'['+idx+']');
        }
      });
    }else if(r && typeof r.getFormData!=='function'){
      r.getFormData=function(){return {};};
      patched.push(k);
    }
  });
  if(typeof vm.getFormData!=='function'){
    vm.getFormData=function(){return vm.form||{};};
    patched.push('vm.getFormData');
  }
  try{
    var p=vm.getFormPromise&&vm.getFormPromise();
    if(p&&typeof p.then==='function') await p;
  }catch(e){}
  try{
    var r1=vm.flowSave();
    if(r1&&typeof r1.then==='function'){ r1 = await r1; }
    var flowRet = r1;
  }catch(e){ return {ok:false,msg:'flowSave_throw',err:String(e),stack:(e&&e.stack?String(e.stack).slice(0,1000):''),patched:patched,refs:Object.keys(refs)}; }

  // 3) 主动探测校验：validateEntType / validateDetailAddress / form.validate
  var validates={};
  try{
    if(typeof vm.validateEntType==='function'){ validates.validateEntType = vm.validateEntType(); }
  }catch(e){ validates.validateEntType = 'err:'+String(e); }
  try{
    if(typeof vm.validateDetailAddress==='function'){ validates.validateDetailAddress = vm.validateDetailAddress(); }
  }catch(e){ validates.validateDetailAddress = 'err:'+String(e); }
  try{
    if(vm.$refs && vm.$refs.form && typeof vm.$refs.form.validate==='function'){
      validates.formValidate = await new Promise(function(resolve){
        try{ vm.$refs.form.validate(function(ok){ resolve(ok); }); }catch(e){ resolve('err:'+String(e)); }
      });
    } else {
      validates.formValidate = 'no_form_validate';
    }
  }catch(e){ validates.formValidate = 'err:'+String(e); }

  return {
    ok:true,
    patched:patched,
    refs:Object.keys(refs),
    form:vm.form||null,
    pickerRef:!!(vm.$refs&&vm.$refs.tniDataPicker),
    totalAddress: vm.totalAddress || null,
    choiceName: vm.choiceName || null,
    flowRet: (typeof flowRet==='object' ? flowRet : String(flowRet)),
    validates: validates
  };
})()"""


def main() -> int:
    ws, cur = pick_ws()
    rec: Dict[str, Any] = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "picked_url": cur, "steps": []}
    if not ws:
        rec["error"] = "no_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return 2
    c = CDP(ws)
    try:
        rec["steps"].append({"step": "ui_before", "data": c.ev(SNAP_UI_JS, timeout_ms=30000)})
        rec["steps"].append({"step": "install_hook", "data": c.ev(HOOK_JS, timeout_ms=30000)})
        time.sleep(1.2)
        rec["steps"].append({"step": "flow_save", "data": c.ev(FLOW_SAVE_JS, timeout_ms=120000)})
        time.sleep(1.0)
        rec["steps"].append({"step": "click_next", "data": c.ev(CLICK_NEXT_JS, timeout_ms=30000)})
        time.sleep(6.0)
        rec["steps"].append({"step": "ui_after", "data": c.ev(SNAP_UI_JS, timeout_ms=30000)})
        hook_tail = c.ev(r"(function(){return window.__ufo_cap?{count:window.__ufo_cap.items.length,items:window.__ufo_cap.items.slice(-20)}:null;})()", timeout_ms=30000)
        rec["steps"].append({"step": "hook_tail", "data": hook_tail})
        # 服务异常自动刷新并更新数据（用户要求）
        items = ((hook_tail or {}).get("items")) or []
        a0002 = any("A0002" in str((it or {}).get("resp", "")) for it in items if isinstance(it, dict))
        if a0002:
            time.sleep(1.2)
            rec["steps"].append({"step": "refresh_on_service_error", "data": c.ev(REFRESH_JS, timeout_ms=30000)})
            time.sleep(2.0)
            rec["steps"].append({"step": "ui_after_refresh", "data": c.ev(SNAP_UI_JS, timeout_ms=30000)})
    finally:
        c.close()
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

