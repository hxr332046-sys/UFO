#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/hook_namecheck_org_chain.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def ev(ws_url, expr, timeout=70000):
    ws = websocket.create_connection(ws_url, timeout=20)
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
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close()
            return msg.get("result", {}).get("result", {}).get("value")


def main():
    ws = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    if not ws:
        rec["error"] = "no_namecheck_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    rec["steps"].append(
        {
            "step": "install_hooks_and_drive",
            "data": ev(
                ws,
                r"""(async function(){
                  function walk(vm,d,pred){if(!vm||d>25)return null;if(pred(vm))return vm;for(var ch of (vm.$children||[])){var r=walk(ch,d+1,pred);if(r)return r;}return null;}
                  function safe(v){
                    try{
                      if(v===null||v===undefined||typeof v==='string'||typeof v==='number'||typeof v==='boolean') return v;
                      if(Array.isArray(v)) return '[array:'+v.length+']';
                      if(typeof v==='object') return '[object]';
                      return String(v);
                    }catch(e){return '[err]';}
                  }
                  var app=document.getElementById('app'); var root=app&&app.__vue__;
                  if(!root) return {ok:false,msg:'no_root'};
                  var idx=walk(root,0,function(v){var n=(v.$options&&v.$options.name)||'';return n==='index'&&v.$parent&&v.$parent.$options&&v.$parent.$options.name==='name-check-info';});
                  var org=walk(root,0,function(v){return (v.$options&&v.$options.name)==='organization-select';});
                  if(!idx||!org) return {ok:false,msg:'no_idx_or_org'};
                  window.__org_chain_trace = [];
                  function push(m,d){ window.__org_chain_trace.push({t:Date.now(),m:m,d:d||{}}); }

                  // hook organization methods
                  ['focusFun','radioChange'].forEach(function(k){
                    var f=org[k];
                    if(typeof f==='function' && !f.__hooked){
                      org[k]=function(){
                        var args=[].slice.call(arguments).map(function(a){return safe(a);});
                        push('org_'+k+'_enter',{args:args,formInline:{groupval:org.formInline&&org.formInline.groupval,radio1:org.formInline&&org.formInline.radio1},zhongjainzhi:safe(org.zhongjainzhi)});
                        try{
                          var r=f.apply(this,arguments);
                          push('org_'+k+'_return',{ret:safe(r),formInline:{groupval:org.formInline&&org.formInline.groupval,radio1:org.formInline&&org.formInline.radio1}});
                          return r;
                        }catch(e){
                          push('org_'+k+'_throw',{err:String(e)});
                          throw e;
                        }
                      };
                      org[k].__hooked=true;
                    }
                  });

                  // hook parent methods
                  ['getFormPromise','flowSave'].forEach(function(k){
                    var f=idx[k];
                    if(typeof f==='function' && !f.__hooked){
                      idx[k]=function(){
                        push('idx_'+k+'_enter',{organize:idx.formInfo&&idx.formInfo.organize,industry:idx.formInfo&&idx.formInfo.industry,nameMark:idx.formInfo&&idx.formInfo.nameMark});
                        try{
                          var r=f.apply(this,arguments);
                          if(r && typeof r.then==='function'){
                            return r.then(function(v){ push('idx_'+k+'_resolve',{ret:safe(v),organize:idx.formInfo&&idx.formInfo.organize}); return v; })
                                    .catch(function(e){ push('idx_'+k+'_reject',{err:String(e)}); throw e; });
                          }
                          push('idx_'+k+'_return',{ret:safe(r)});
                          return r;
                        }catch(e){
                          push('idx_'+k+'_throw',{err:String(e)});
                          throw e;
                        }
                      };
                      idx[k].__hooked=true;
                    }
                  });

                  // drive: try multiple organization codes and invoke getFormPromise each time
                  var candidates = (org.groupList||[]).slice(0,20).map(function(it){return String((it&&it.code)||'');}).filter(Boolean);
                  if(!candidates.length) candidates=['802','805','1005','1004'];
                  var trial = [];
                  for(var i=0;i<candidates.length && i<8;i++){
                    var code=candidates[i];
                    idx.$set(idx.formInfo,'organize',code);
                    org.formInline=org.formInline||{};
                    org.$set(org.formInline,'groupval',code);
                    org.$set(org.formInline,'radio1',code);
                    try{ if(typeof org.focusFun==='function') org.focusFun(); }catch(e){}
                    try{ if(typeof org.radioChange==='function') org.radioChange({target:{value:code}}); }catch(e){}
                    try{ if(typeof org.radioChange==='function') org.radioChange(code); }catch(e){}
                    try{ org.$emit('input',code); }catch(e){}
                    try{ org.$emit('change',code); }catch(e){}
                    var ok = true, err='';
                    try{
                      var p = idx.getFormPromise();
                      if(p && typeof p.then==='function'){ await p; }
                    }catch(e){ ok=false; err=String(e); }
                    trial.push({code:code,ok:ok,err:err,groupval:org.formInline&&org.formInline.groupval,radio1:org.formInline&&org.formInline.radio1,parentOrganize:idx.formInfo&&idx.formInfo.organize});
                    if(ok){ break; }
                  }

                  // final click
                  var save=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').replace(/\s+/g,'').indexOf('保存并下一步')>=0&&!x.disabled);
                  if(save) save.click();
                  await new Promise(r=>setTimeout(r,400));
                  var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);
                  return {ok:true,trial:trial,errors:errs.slice(0,10),trace:window.__org_chain_trace.slice(-120)};
                })()""",
            ),
        }
    )
    time.sleep(6)
    rec["steps"].append(
        {
            "step": "after",
            "data": ev(
                ws,
                r"""(function(){var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);var txt=(document.body.innerText||'');return {href:location.href,hash:location.hash,errors:errs.slice(0,10),hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0};})()""",
            ),
        }
    )
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

