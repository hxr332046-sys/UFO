#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/fill_namecheck_industry_org.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def ev(ws_url, expr):
    ws = websocket.create_connection(ws_url, timeout=16)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 70000},
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

    before = ev(
        ws,
        r"""(function(){
          var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);
          return {href:location.href,hash:location.hash,errors:errs.slice(0,10)};
        })()""",
    )
    rec["steps"].append({"step": "before", "data": before})

    fill = ev(
        ws,
        r"""(async function(){
          function walk(vm,d,pred){if(!vm||d>25)return null;if(pred(vm))return vm;for(var ch of (vm.$children||[])){var r=walk(ch,d+1,pred);if(r)return r;}return null;}
          var app=document.getElementById('app');
          var root=app&&app.__vue__;
          if(!root) return {ok:false,msg:'no_root'};
          var indexVm=walk(root,0,function(v){var n=(v.$options&&v.$options.name)||'';return n==='index' && v.$parent && v.$parent.$options && v.$parent.$options.name==='name-check-info';});
          var indVm=walk(root,0,function(v){return (v.$options&&v.$options.name)==='tni-industry-select';});
          var orgVm=walk(root,0,function(v){return (v.$options&&v.$options.name)==='organization-select';});
          if(!indexVm) return {ok:false,msg:'no_index_vm'};
          var trace=[];

          // Ensure basis values
          indexVm.formInfo=indexVm.formInfo||{};
          if(!indexVm.formInfo.nameMark){
            indexVm.$set(indexVm.formInfo,'nameMark','桂柚百货');
            trace.push('set_nameMark');
          }
          if(!indexVm.formInfo.distCode){ indexVm.$set(indexVm.formInfo,'distCode','450102'); trace.push('set_distCode'); }
          if(!indexVm.formInfo.streetCode){ indexVm.$set(indexVm.formInfo,'streetCode','450102'); trace.push('set_streetCode'); }

          // Fill organization via component method first, fallback direct set
          if(orgVm){
            var gl = orgVm.groupList || [];
            var picked = null;
            if(Array.isArray(gl) && gl.length){
              picked = gl[0];
              try{
                if(typeof orgVm.radioChange==='function'){ orgVm.radioChange(picked); trace.push('org_radioChange'); }
              }catch(e){ trace.push('org_radio_err:'+String(e)); }
            }
            if(!indexVm.formInfo.organize){
              var code = '';
              if(picked && typeof picked==='object'){ code = picked.value||picked.code||picked.id||picked.dictCode||picked.organizeCode||''; }
              if(!code && indexVm.formInfo.entType==='4540') code='01';
              indexVm.$set(indexVm.formInfo,'organize',code||'01');
              trace.push('org_direct_set');
            }
          }else{
            if(!indexVm.formInfo.organize){ indexVm.$set(indexVm.formInfo,'organize','01'); trace.push('org_direct_no_vm'); }
          }

          // Fill industry via component methods
          if(indVm){
            try{
              if(typeof indVm.show==='function') indVm.show();
              if(typeof indVm.renderList==='function') await indVm.renderList();
              trace.push('industry_render');
            }catch(e){ trace.push('industry_render_err:'+String(e)); }
            var list = indVm.industryList || [];
            var first = Array.isArray(list) && list.length ? list[0] : null;
            if(first){
              try{
                if(typeof indVm.handleSelect==='function'){ indVm.handleSelect(first); trace.push('industry_handleSelect'); }
              }catch(e){ trace.push('industry_select_err:'+String(e)); }
              var code = first.value||first.code||first.id||first.industryCode||first.dictCode||'';
              var name = first.label||first.name||first.text||first.industryName||'';
              if(code) indexVm.$set(indexVm.formInfo,'industry',code);
              if(name) indexVm.$set(indexVm.formInfo,'industryName',name);
              if(first.id) indexVm.$set(indexVm.formInfo,'industryId',first.id);
              trace.push('industry_direct_set_from_first');
            }else{
              // fallback values observed commonly accepted for trade
              if(!indexVm.formInfo.industry) indexVm.$set(indexVm.formInfo,'industry','5299');
              if(!indexVm.formInfo.industryName) indexVm.$set(indexVm.formInfo,'industryName','其他未列明零售业');
              trace.push('industry_fallback_set');
            }
          }else{
            if(!indexVm.formInfo.industry) indexVm.$set(indexVm.formInfo,'industry','5299');
            if(!indexVm.formInfo.industryName) indexVm.$set(indexVm.formInfo,'industryName','其他未列明零售业');
            trace.push('industry_direct_no_vm');
          }

          // sync declaration checkbox if present
          var agree=[...document.querySelectorAll('label,span,div')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('我已阅读并同意')>=0);
          if(agree){ agree.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window})); trace.push('agree_click'); }

          // try save next
          var save=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').replace(/\s+/g,'').indexOf('保存并下一步')>=0&&!x.disabled);
          if(save){ save.click(); trace.push('click_save_next'); }

          function p(o){ var r={}; Object.keys(o||{}).forEach(function(k){ var v=o[k]; if(v===null||v===undefined||typeof v==='string'||typeof v==='number'||typeof v==='boolean'){ r[k]=v; } }); return r; }
          return {ok:true,trace:trace,formInfo:p(indexVm.formInfo),industryListLen:indVm&&Array.isArray(indVm.industryList)?indVm.industryList.length:null,groupListLen:orgVm&&Array.isArray(orgVm.groupList)?orgVm.groupList.length:null};
        })()""",
    )
    rec["steps"].append({"step": "fill", "data": fill})

    time.sleep(6)
    after = ev(
        ws,
        r"""(function(){
          var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);
          var txt=(document.body.innerText||'');
          return {href:location.href,hash:location.hash,errors:errs.slice(0,10),hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0};
        })()""",
    )
    rec["steps"].append({"step": "after", "data": after})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

