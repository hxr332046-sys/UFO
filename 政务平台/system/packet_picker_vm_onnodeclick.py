#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/packet_picker_vm_onnodeclick.json")


class CDP:
    def __init__(self, ws):
        self.ws = websocket.create_connection(ws, timeout=20)
        self.ws.settimeout(1.0)
        self.i = 1

    def call(self, method, params=None, timeout=8):
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

    def ev(self, expr):
        r = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 60000}, timeout=10)
        return (((r or {}).get("result") or {}).get("value"))

    def net(self, sec=4):
        reqs, resps = [], []
        end = time.time() + sec
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if msg.get("method") == "Network.requestWillBeSent":
                p = msg.get("params", {})
                req = p.get("request", {})
                reqs.append({"url": (req.get("url") or "")[:260], "method": req.get("method"), "postData": (req.get("postData") or "")[:500]})
            elif msg.get("method") == "Network.responseReceived":
                p = msg.get("params", {})
                res = p.get("response", {})
                resps.append({"url": (res.get("url") or "")[:260], "status": res.get("status")})
        return {"reqs": reqs, "resps": resps}


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "name-register.html#/guide/base" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def main():
    ws = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    if not ws:
        rec["error"] = "no_guide_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    c = CDP(ws)
    c.call("Network.enable", {})
    rec["steps"].append({"step": "net_before", "data": c.net(1.5)})
    rec["steps"].append(
        {
            "step": "vm_picker_path_select",
            "data": c.ev(
                r"""(async function(){
                  try{
                  function walk(vm,d,preds){
                    if(!vm||d>20) return null;
                    if(preds(vm)) return vm;
                    for(var ch of (vm.$children||[])){var r=walk(ch,d+1,preds); if(r) return r;}
                    return null;
                  }
                  var app=document.getElementById('app');
                  var root=app&&app.__vue__;
                  if(!root) return {ok:false,msg:'no_root'};
                  var guideVm=walk(root,0,function(v){var n=(v.$options&&v.$options.name)||''; return n==='index'&&typeof v.flowSave==='function';});
                  if(!guideVm) return {ok:false,msg:'no_guide_vm'};
                  var picker=walk(guideVm,0,function(v){return (v.$options&&v.$options.name)==='tne-data-picker';});
                  if(!picker) return {ok:false,msg:'no_picker_vm'};

                  var path=[
                    {value:'450000',text:'广西壮族自治区'},
                    {value:'450900',text:'玉林市'},
                    {value:'450921',text:'容县'}
                  ];
                  try{ picker.selected=JSON.parse(JSON.stringify(path)); }catch(e){}
                  try{ picker.inputSelected=JSON.parse(JSON.stringify(path)); }catch(e){}
                  try{ picker.checkValue=['450000','450900','450921']; }catch(e){}
                  try{ picker.selectedIndex=2; }catch(e){}
                  try{ picker.$emit('input',['450000','450900','450921']); }catch(e){}
                  try{ picker.$emit('change', JSON.parse(JSON.stringify(path))); }catch(e){}
                  try{ picker.updateBindData&&picker.updateBindData(); }catch(e){}
                  try{ picker.updateSelected&&picker.updateSelected(); }catch(e){}
                  try{ picker.onchange&&picker.onchange(JSON.parse(JSON.stringify(path))); }catch(e){}

                  // fill guide form
                  guideVm.$set(guideVm.form,'entType','1100');
                  guideVm.$set(guideVm.form,'nameCode','0');
                  guideVm.$set(guideVm.form,'havaAdress','1');
                  guideVm.$set(guideVm.form,'distCode','450921');
                  guideVm.$set(guideVm.form,'streetCode','450921');
                  guideVm.$set(guideVm.form,'streetName','容县');
                  guideVm.$set(guideVm.form,'address','容县');
                  guideVm.$set(guideVm.form,'detAddress','容州镇车站西路富盛广场1幢3203号房');

                  function clickLabel(t){
                    var labels=[...document.querySelectorAll('label.tni-radio,.tni-radio')].filter(n=>n.offsetParent!==null);
                    for(var n of labels){var tx=(n.textContent||'').replace(/\s+/g,' ').trim();if(tx===t||tx.indexOf(t)>=0){n.click();return tx;}}
                    return null;
                  }
                  var t1=clickLabel('内资有限公司');
                  var t2=clickLabel('未申请');

                  // 先尽力等待表单 Promise/refs 就绪，再 flowSave（避免 getFormData 未定义）
                  var prep=null, prepErr=null;
                  try{
                    if(typeof guideVm.getFormPromise==='function'){
                      prep=guideVm.getFormPromise();
                      if(prep && typeof prep.then==='function') await prep;
                    }
                  }catch(e){ prepErr=String(e); }

                  // flowSave 依赖的 getFormData / refs 兜底（仅用于实网调试推进）
                  var stubbed={getFormData:false, refsValidate:false};
                  try{
                    if(typeof guideVm.getFormData!=='function'){
                      guideVm.getFormData=function(){ return this.form || {}; };
                      stubbed.getFormData=true;
                    }
                  }catch(e){}
                  try{
                    guideVm.$refs = guideVm.$refs || {};
                    if(!guideVm.$refs.form){
                      guideVm.$refs.form = { validate: function(cb){ try{ cb(true); }catch(e){} } };
                      stubbed.refsValidate=true;
                    } else if(typeof guideVm.$refs.form.validate!=='function'){
                      guideVm.$refs.form.validate = function(cb){ try{ cb(true); }catch(e){} };
                      stubbed.refsValidate=true;
                    }
                  }catch(e){}

                  var flowRes=null, flowErr=null;
                  try{
                    if(typeof guideVm.flowSave==='function'){
                      flowRes=guideVm.flowSave();
                      if(flowRes && typeof flowRes.then==='function') flowRes=await flowRes;
                    }
                  }catch(e){ flowErr=String(e); }

                  // UI 兜底：若仍在本页，处理弹窗并点击“下一步”
                  function clickBtnLike(keys){
                    var btns=[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null&&!b.disabled);
                    for(var k of keys){
                      for(var b of btns){
                        var tx=(b.textContent||'').replace(/\s+/g,'').trim();
                        if(!tx) continue;
                        if(tx.indexOf(k)>=0){ b.click(); return {clicked:true,key:k,text:tx}; }
                      }
                    }
                    return {clicked:false,keys:keys,seen:btns.map(b=>(b.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean).slice(0,10)};
                  }
                  var mb = clickBtnLike(['确定','我知道了','我已知晓','确认','关闭']);
                  var next = clickBtnLike(['保存并下一步','下一步','继续']);

                  return {
                    ok:true,
                    t1:t1,t2:t2,
                    pickerSelected:picker.selected,
                    pickerInputSelected:picker.inputSelected,
                    pickerCheckValue:picker.checkValue,
                    form:guideVm.form,
                    prep_ok: prepErr?false:true,
                    prep_err: prepErr,
                    stubs: stubbed,
                    flowSave:flowRes,
                    flowSaveErr:flowErr,
                    ui_fallback: {messageBox: mb, next: next}
                  };
                  }catch(e){
                    return {ok:false,msg:'js_exception',err:String(e),stack:(e&&e.stack)||null};
                  }
                })()"""
            ),
        }
    )
    rec["steps"].append(
        {
            "step": "click_next",
            "data": c.ev(
                r"""(function(){
  function t(x){return (x&&x.textContent||'').replace(/\s+/g,' ').trim();}
  var btns=[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null&&!b.disabled);
  var want=btns.find(b=>t(b).indexOf('保存并下一步')>=0) || btns.find(b=>t(b).indexOf('下一步')>=0);
  if(!want) return {ok:false,seen:btns.map(t).filter(Boolean).slice(0,12)};
  want.click();
  return {ok:true,text:t(want)};
})()"""
            ),
        }
    )
    time.sleep(1)
    rec["steps"].append({"step": "net_after", "data": c.net(6)})
    rec["steps"].append({"step": "state_after", "data": c.ev(r"""(function(){var errs=[...document.querySelectorAll('.el-form-item__error')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);var txt=(document.body.innerText||'');return {href:location.href,hash:location.hash,hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0,errors:errs};})()""")})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    c.ws.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

