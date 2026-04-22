#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/chain_submit_namecheck_with_bodies.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


class CDP:
    def __init__(self, ws):
        self.ws = websocket.create_connection(ws, timeout=20)
        self.ws.settimeout(1.0)
        self.i = 1

    def call(self, method, params=None, timeout=10):
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
                return msg
        return {"error": {"message": f"timeout {method}"}}

    def ev(self, expr, timeout=90000):
        m = self.call(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout},
            timeout=15,
        )
        return ((m.get("result") or {}).get("result") or {}).get("value")

    def net(self, sec=8):
        reqs, resps = [], []
        end = time.time() + sec
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if msg.get("method") == "Network.requestWillBeSent":
                p = msg.get("params", {})
                r = p.get("request", {})
                reqs.append(
                    {
                        "requestId": p.get("requestId"),
                        "url": (r.get("url") or "")[:260],
                        "method": r.get("method"),
                        "postData": (r.get("postData") or "")[:2000],
                    }
                )
            elif msg.get("method") == "Network.responseReceived":
                p = msg.get("params", {})
                r = p.get("response", {})
                rid = p.get("requestId")
                body = None
                if rid and "/icpsp-api/" in (r.get("url") or ""):
                    b = self.call("Network.getResponseBody", {"requestId": rid}, timeout=5)
                    body = ((b.get("result") or {}).get("body") or "")[:8000]
                resps.append({"requestId": rid, "url": (r.get("url") or "")[:260], "status": r.get("status"), "body": body})
        return {"reqs": reqs, "resps": resps}


def main():
    ws = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    if not ws:
        rec["error"] = "no_namecheck_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    c = CDP(ws)
    c.call("Network.enable", {})
    rec["steps"].append({"step": "before", "data": c.ev(r"""(function(){var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);return {hash:location.hash,errors:errs.slice(0,10)};})()""")})
    rec["steps"].append(
        {
            "step": "invoke_chain",
            "data": c.ev(
                r"""(async function(){
                  function walk(vm,d,p){if(!vm||d>25)return null;if(p(vm))return vm;for(var c of (vm.$children||[])){var r=walk(c,d+1,p);if(r)return r;}return null;}
                  function s(v){try{return JSON.parse(JSON.stringify(v));}catch(e){return String(v);}}
                  function clean(v){return String(v||'').replace(/\s+/g,' ').trim();}
                  function vis(el){return !!(el && el.offsetParent!==null);}
                  function qsa(sel){return [].slice.call(document.querySelectorAll(sel));}
                  function setv(target,key,val){
                    try{
                      if(target && typeof target.$set==='function') target.$set(target,key,val);
                      else if(target) target[key]=val;
                    }catch(e){
                      try{ target[key]=val; }catch(_){}
                    }
                  }
                  function readVisibleInputs(){
                    var ins=qsa('input').filter(vis);
                    function byPlaceholder(ph){
                      var hit=ins.find(function(x){ return clean(x.placeholder)===ph; });
                      return hit ? clean(hit.value) : '';
                    }
                    var checkedNameRadio=qsa('input[type=radio]').filter(function(x){return vis(x)&&x.checked;}).find(function(x){ return ['10','20','30'].indexOf(String(x.value))>=0; });
                    var nameText='';
                    if(checkedNameRadio){
                      var box=checkedNameRadio.closest('label') || checkedNameRadio.parentElement;
                      nameText=clean(box && box.textContent || '');
                      nameText=nameText.replace(/\s*\（\）\s*$/,'').trim();
                    }
                    return {
                      namePre: byPlaceholder('请选择行政区划'),
                      nameMark: byPlaceholder('字号最多只能输入10位汉字'),
                      industrySpecial: byPlaceholder('请输入内容'),
                      organizeText: byPlaceholder('请选择组织形式'),
                      selectedName: nameText
                    };
                  }
                  var app=document.getElementById('app'); var root=app&&app.__vue__;
                  if(!root) return {ok:false,msg:'no_root'};
                  var idx=walk(root,0,function(v){var n=(v.$options&&v.$options.name)||'';return n==='index'&&v.$parent&&v.$parent.$options&&v.$parent.$options.name==='name-check-info';});
                  var fc=walk(root,0,function(v){return v.$data&&v.$data.businessDataInfo;});
                  if(!idx) return {ok:false,msg:'no_index'};
                  var t=[];
                  var ui=readVisibleInputs();
                  idx.formInfo = idx.formInfo || {};
                  var bdi = fc && fc.$data ? (fc.$data.businessDataInfo || {}) : {};
                  var extra = bdi.extraDto || {};
                  if(ui.namePre) setv(idx.formInfo,'namePre',ui.namePre);
                  if(ui.nameMark) setv(idx.formInfo,'nameMark',ui.nameMark);
                  if(ui.industrySpecial){
                    setv(idx.formInfo,'industrySpecial',ui.industrySpecial);
                    if(!clean(idx.formInfo.allIndKeyWord)) setv(idx.formInfo,'allIndKeyWord',ui.industrySpecial);
                    if(!clean(idx.formInfo.showKeyWord)) setv(idx.formInfo,'showKeyWord',ui.industrySpecial);
                  }
                  // Backend "主营行业不能为空" usually checks this field chain.
                  if(!clean(idx.formInfo.mainBusinessDesc)){
                    setv(idx.formInfo,'mainBusinessDesc', clean(idx.formInfo.industrySpecial) || clean(idx.formInfo.industryName) || '贸易');
                  }
                  if(!clean(idx.formInfo.industry)) setv(idx.formInfo,'industry','5299');
                  if(!clean(idx.formInfo.industryId)) setv(idx.formInfo,'industryId', idx.formInfo.industry || '5299');
                  if(!clean(idx.formInfo.industryName)) setv(idx.formInfo,'industryName','其他未列明零售业');
                  if(!clean(idx.formInfo.multiIndustry)) setv(idx.formInfo,'multiIndustry', idx.formInfo.industry || '5299');
                  if(!clean(idx.formInfo.multiIndustryName)) setv(idx.formInfo,'multiIndustryName', idx.formInfo.industryName || '其他未列明零售业');
                  if(ui.organizeText){
                    // Keep numeric organize code if already present; only sync the visible name.
                    var curOrg = clean(idx.formInfo.organize);
                    if(!/^\d+$/.test(curOrg)){
                      var codeHit = ui.organizeText.match(/^(\d{3,4})/);
                      if(codeHit) setv(idx.formInfo,'organize',codeHit[1]);
                    }
                    setv(idx.formInfo,'organizeName',ui.organizeText);
                  }
                  if(ui.selectedName) setv(idx.formInfo,'name',ui.selectedName);
                  setv(idx.formInfo,'isCheckBox','Y');
                  setv(idx.formInfo,'declarationMode','Y');
                  ['namePre','nameMark','industrySpecial','allIndKeyWord','showKeyWord','mainBusinessDesc','industry','industryId','industryName','multiIndustry','multiIndustryName','organize','organizeName','name','isCheckBox','declarationMode','distCode','streetCode','entType'].forEach(function(k){
                    if(idx.formInfo[k]!==undefined){
                      setv(bdi,k,idx.formInfo[k]);
                      setv(extra,k,idx.formInfo[k]);
                    }
                  });
                  if(idx.formInfo.name) setv(bdi,'businessName',idx.formInfo.name);
                  if(fc && fc.$data){
                    fc.$data.businessDataInfo = bdi;
                    bdi.extraDto = extra;
                  }
                  t.push(['ui_sync', s(ui)]);
                  t.push(['form_snapshot', s({
                    namePre: idx.formInfo.namePre,
                    nameMark: idx.formInfo.nameMark,
                    industrySpecial: idx.formInfo.industrySpecial,
                    mainBusinessDesc: idx.formInfo.mainBusinessDesc,
                    industry: idx.formInfo.industry,
                    industryId: idx.formInfo.industryId,
                    organize: idx.formInfo.organize,
                    name: idx.formInfo.name
                  })]);
                  try{
                    var p=idx.getFormPromise&&idx.getFormPromise();
                    if(p&&typeof p.then==='function'){await p; t.push(['getFormPromise','resolved']);}
                    else t.push(['getFormPromise','non_promise']);
                  }catch(e){t.push(['getFormPromise_err',String(e)]);}
                  try{
                    if(typeof idx.nameCheckRepeat==='function'){
                      var r1=idx.nameCheckRepeat();
                      if(r1&&typeof r1.then==='function'){r1=await r1;}
                      t.push(['nameCheckRepeat',s(r1)]);
                    } else t.push(['no_nameCheckRepeat']);
                  }catch(e){
                    var ee={msg:String(e)};
                    try{ if(e&&e.message) ee.message=String(e.message); }catch(_){}
                    try{ if(e&&e.code) ee.code=e.code; }catch(_){}
                    try{ if(e&&e.response) ee.response=s(e.response); }catch(_){}
                    try{ if(e&&e.data) ee.data=s(e.data); }catch(_){}
                    t.push(['nameCheckRepeat_err',ee]);
                  }
                  try{
                    var ok=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').replace(/\s+/g,'').indexOf('确定')>=0&&!x.disabled);
                    if(ok){ok.click();t.push(['click_ok']);}
                  }catch(e){t.push(['click_ok_err',String(e)]);}
                  try{
                    if(typeof idx.flowSave==='function'){
                      var r2=idx.flowSave();
                      if(r2&&typeof r2.then==='function'){r2=await r2;}
                      t.push(['flowSave',s(r2)]);
                    } else t.push(['no_flowSave']);
                  }catch(e){
                    var fe={msg:String(e)};
                    try{ if(e&&e.message) fe.message=String(e.message); }catch(_){}
                    t.push(['flowSave_err',fe]);
                  }
                  return {ok:true,trace:t};
                })()"""
            ),
        }
    )
    rec["steps"].append({"step": "network", "data": c.net(10)})
    rec["steps"].append({"step": "after", "data": c.ev(r"""(function(){var txt=(document.body.innerText||'');var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);return {hash:location.hash,errors:errs.slice(0,10),hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0};})()""")})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.ws.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()
