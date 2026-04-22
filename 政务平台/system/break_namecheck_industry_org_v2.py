#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/break_namecheck_industry_org_v2.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def ev(ws_url, expr, timeout=70000):
    ws = websocket.create_connection(ws_url, timeout=18)
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
            "step": "before",
            "data": ev(
                ws,
                r"""(function(){var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);return {href:location.href,hash:location.hash,errors:errs.slice(0,10)};})()""",
            ),
        }
    )

    rec["steps"].append(
        {
            "step": "fill_try",
            "data": ev(
                ws,
                r"""(async function(){
                  function walk(vm,d,pred){if(!vm||d>25)return null;if(pred(vm))return vm;for(var ch of (vm.$children||[])){var r=walk(ch,d+1,pred);if(r)return r;}return null;}
                  var app=document.getElementById('app'); var root=app&&app.__vue__;
                  if(!root) return {ok:false,msg:'no_root'};
                  var idx=walk(root,0,function(v){var n=(v.$options&&v.$options.name)||'';return n==='index'&&v.$parent&&v.$parent.$options&&v.$parent.$options.name==='name-check-info';});
                  var ind=walk(root,0,function(v){return (v.$options&&v.$options.name)==='tni-industry-select';});
                  var org=walk(root,0,function(v){return (v.$options&&v.$options.name)==='organization-select';});
                  if(!idx) return {ok:false,msg:'no_index'};
                  var trace=[];

                  idx.formInfo=idx.formInfo||{};
                  if(!idx.formInfo.nameMark){ idx.$set(idx.formInfo,'nameMark','桂柚百货'); trace.push('set_nameMark'); }
                  if(!idx.formInfo.distCode){ idx.$set(idx.formInfo,'distCode','450102'); trace.push('set_distCode'); }
                  if(!idx.formInfo.streetCode){ idx.$set(idx.formInfo,'streetCode','450102'); trace.push('set_streetCode'); }

                  // organization: try each option using component method
                  if(org && Array.isArray(org.groupList) && org.groupList.length){
                    var picked=null, lastErr='';
                    for(var i=0;i<org.groupList.length;i++){
                      var it=org.groupList[i];
                      var val=(it&&typeof it==='object')?(it.value||it.code||it.id||it.dictCode||it.organizeCode||''):it;
                      if(!val) continue;
                      try{
                        idx.$set(idx.formInfo,'organize',String(val));
                        if(typeof org.radioChange==='function'){
                          try{ org.radioChange({target:{value:String(val)}}); }catch(e){}
                        }
                        picked=String(val);
                        // break early on first reasonable code
                        if(String(val).length<=4) break;
                      }catch(e){
                        lastErr=String(e);
                      }
                    }
                    trace.push('org_picked:'+(picked||'none'));
                    if(lastErr) trace.push('org_err:'+lastErr);
                  }else{
                    idx.$set(idx.formInfo,'organize','802');
                    trace.push('org_fallback_802');
                  }

                  // industry: load list with keyword attempts
                  var iPicked=null;
                  if(ind){
                    var kws=['零售','百货','商贸','贸易'];
                    for(var k=0;k<kws.length;k++){
                      try{
                        ind.keyword=kws[k];
                        if(typeof ind.renderList==='function'){ await ind.renderList(); }
                        var list=ind.industryList||[];
                        if(Array.isArray(list) && list.length){
                          var one=list[0];
                          if(typeof ind.handleSelect==='function'){ try{ ind.handleSelect(one); }catch(e){} }
                          var code=one.value||one.code||one.id||one.industryCode||one.dictCode||'';
                          var name=one.label||one.name||one.text||one.industryName||'';
                          if(code){ idx.$set(idx.formInfo,'industry',String(code)); iPicked=String(code); }
                          if(name){ idx.$set(idx.formInfo,'industryName',String(name)); }
                          if(one.id){ idx.$set(idx.formInfo,'industryId',one.id); }
                          trace.push('industry_kw:'+kws[k]+' len='+list.length);
                          break;
                        }else{
                          trace.push('industry_kw:'+kws[k]+' len=0');
                        }
                      }catch(e){
                        trace.push('industry_kw_err:'+kws[k]+':'+String(e));
                      }
                    }
                  }
                  if(!iPicked){
                    idx.$set(idx.formInfo,'industry','5299');
                    idx.$set(idx.formInfo,'industryName','其他未列明零售业');
                    trace.push('industry_fallback_5299');
                  }

                  // try checkbox and save button
                  var agree=[...document.querySelectorAll('label,span,div')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('我已阅读并同意')>=0);
                  if(agree){ agree.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window})); trace.push('agree_click'); }
                  if(typeof idx.$forceUpdate==='function'){ idx.$forceUpdate(); trace.push('force_update'); }
                  await new Promise(r=>setTimeout(r,250));
                  var save=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').replace(/\s+/g,'').indexOf('保存并下一步')>=0&&!x.disabled);
                  if(save){ save.click(); trace.push('click_save_next'); }

                  function flat(o){var r={};Object.keys(o||{}).forEach(function(k){var v=o[k];if(v===null||v===undefined||typeof v==='string'||typeof v==='number'||typeof v==='boolean'){r[k]=v;}});return r;}
                  return {
                    ok:true,
                    trace:trace,
                    industryListLen:ind&&Array.isArray(ind.industryList)?ind.industryList.length:null,
                    groupListLen:org&&Array.isArray(org.groupList)?org.groupList.length:null,
                    formInfo:flat(idx.formInfo)
                  };
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

