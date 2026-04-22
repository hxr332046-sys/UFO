#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT_JSON = Path("G:/UFO/政务平台/dashboard/data/records/full_submit_test_02_4.json")
OUT_MD = Path("G:/UFO/政务平台/dashboard/data/records/full_submit_test_02_4.md")


def pick_core_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        u = p.get("url", "")
        if p.get("type") == "page" and "core.html#/flow/base/" in u:
            return p["webSocketDebuggerUrl"], u
    return None, None


def ev(ws_url, expr, timeout=60000):
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


INIT_HOOK_JS = r"""(function(){
  window.__full_submit_probe = window.__full_submit_probe || {reqs:[],resps:[]};
  if(!window.__full_submit_hooked){
    window.__full_submit_hooked = true;
    var oo = XMLHttpRequest.prototype.open;
    var os = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(m,u){ this.__u=u; this.__m=m; return oo.apply(this,arguments); };
    XMLHttpRequest.prototype.send = function(b){
      var u=this.__u||'';
      if(u.indexOf('/icpsp-api/')>=0){
        window.__full_submit_probe.reqs.push({
          t:Date.now(), m:this.__m||'GET', u:u.slice(0,260),
          len:(b||'').length, body:(b||'').slice(0,500), href:location.href, hash:location.hash
        });
        var self=this;
        self.addEventListener('load', function(){
          window.__full_submit_probe.resps.push({
            t:Date.now(), u:u.slice(0,260), status:self.status,
            text:(self.responseText||'').slice(0,700), href:location.href, hash:location.hash
          });
        });
      }
      return os.apply(this,arguments);
    };
  }
  return {ok:true, hooked:!!window.__full_submit_hooked};
})()"""


SNAP_JS = r"""(function(){
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
  var btns=Array.from(document.querySelectorAll('button,.el-button')).filter(function(b){return b.offsetParent!==null;}).map(function(b){return {text:(b.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!b.disabled};});
  var errs=Array.from(document.querySelectorAll('.el-form-item__error,.el-message')).map(function(e){return (e.textContent||'').replace(/\s+/g,' ').trim();}).filter(Boolean);
  var vals={};
  var items=document.querySelectorAll('.el-form-item');
  for(var i=0;i<items.length;i++){
    var lb=items[i].querySelector('.el-form-item__label');
    var t=(lb&&lb.textContent||'').replace(/\s+/g,' ').trim();
    var inp=items[i].querySelector('input.el-input__inner,textarea.el-textarea__inner');
    if(t&&inp) vals[t]=(inp.value||'').trim();
  }
  return {
    href:location.href, hash:location.hash, title:document.title,
    flowData:p.flowData||null, busiCompUrlPaths:fc?fc.busiCompUrlPaths:null,
    buttons:btns.slice(0,30), errors:errs.slice(0,20), values:vals,
    text:(document.body.innerText||'').slice(0,1200)
  };
})()"""


STEP_JS = r"""(function(){
  function setByLabel(labelKw,val){
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
      }
    }
    return {ok:false};
  }
  var actions={fills:{},clicks:[]};
  // common fill fallbacks
  actions.fills.entPhone = setByLabel('联系电话','18977514335');
  actions.fills.empNum = setByLabel('从业人数','1');
  actions.fills.detAddress = setByLabel('详细地址','容州镇容州大道88号A栋1201室');
  actions.fills.detBizAddr = setByLabel('生产经营地详细地址','容州镇容州大道88号A栋1201室');
  actions.fills.memberName = setByLabel('姓名','黄永裕');
  actions.fills.idNo = setByLabel('证件号码','450921198812051251');
  actions.fills.mobile = setByLabel('手机','18977514335');

  // choose radio defaults for common required groups
  var radios=[...document.querySelectorAll('.el-radio,.el-radio__label,span,label')].filter(e=>e.offsetParent!==null);
  var radioTargets=['以个人财产出资','同意','是','长期','独立核算'];
  for(var rt of radioTargets){
    for(var r of radios){
      var tx=(r.textContent||'').replace(/\s+/g,' ').trim();
      if(tx.indexOf(rt)>=0){
        r.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
        actions.clicks.push('radio:'+rt);
        break;
      }
    }
  }

  // click add buttons first if available (member steps)
  var addBtns=[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null && !b.disabled && /添加投资人|添加成员|添加/.test((b.textContent||'')));
  if(addBtns.length){
    addBtns[0].click();
    actions.clicks.push('add:'+((addBtns[0].textContent||'').trim()));
  }

  // confirm modal if available
  var cands=[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null && !b.disabled);
  var order=['确定','保存','完成并提交','保存并下一步','下一步','提交'];
  for(var t of order){
    var b=cands.find(x=>((x.textContent||'').replace(/\s+/g,' ').trim()).indexOf(t)>=0);
    if(b){
      b.click();
      actions.clicks.push('btn:'+((b.textContent||'').trim()));
      break;
    }
  }
  return actions;
})()"""


def append_md(record):
    lines = [
        "# 02_4 全流程真实提交测试",
        "",
        f"- started_at: {record.get('started_at','')}",
        f"- ended_at: {record.get('ended_at','')}",
        f"- final_hash: {record.get('final_hash','')}",
        f"- final_status: {record.get('final_status','')}",
        "",
        "## 关键上下文",
        f"- busiId: {record.get('busiId','')}",
        f"- nameId: {record.get('nameId','')}",
        "",
        "## 步骤摘要",
    ]
    for i, s in enumerate(record.get("steps", []), 1):
        snap = s.get("snapshot", {})
        lines.append(f"- Step {i}: `{snap.get('hash','')}` | errors={len(snap.get('errors',[]))} | action={s.get('action')}")
    lines.append("")
    lines.append("## 最后接口回包（摘要）")
    for r in record.get("last_responses", [])[-5:]:
        lines.append(f"- `{r.get('u','')}` status={r.get('status')} text={str(r.get('text',''))[:120]}")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main():
    ws, url = pick_core_ws()
    rec = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "start_url": url,
        "steps": [],
        "target": "full_submit_complete",
    }
    if not ws:
        rec["error"] = "no_core_flow_page"
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        append_md(rec)
        print(f"Saved: {OUT_JSON}")
        print(f"Saved: {OUT_MD}")
        return

    ev(ws, INIT_HOOK_JS)
    first_snap = ev(ws, SNAP_JS)
    rec["init_snapshot"] = first_snap
    fd = (first_snap or {}).get("flowData", {}) or {}
    rec["busiId"] = fd.get("busiId")
    rec["nameId"] = fd.get("nameId")

    final_status = "unknown"
    for _ in range(18):
        snap = ev(ws, SNAP_JS)
        txt = (snap.get("text") or "")
        hashv = snap.get("hash") or ""
        if "申报成功" in txt or "提交成功" in txt or "success" in hashv.lower():
            final_status = "success_page"
            rec["steps"].append({"snapshot": snap, "action": "stop_on_success"})
            break
        action = ev(ws, STEP_JS)
        rec["steps"].append({"snapshot": snap, "action": action})
        time.sleep(6)
    else:
        final_status = "max_steps_reached"

    end_snap = ev(ws, SNAP_JS)
    rec["final_snapshot"] = end_snap
    rec["final_hash"] = end_snap.get("hash")
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    rec["final_status"] = final_status
    probe = ev(ws, "window.__full_submit_probe || {reqs:[],resps:[]}")
    rec["request_count"] = len((probe or {}).get("reqs", []))
    rec["response_count"] = len((probe or {}).get("resps", []))
    rec["last_requests"] = (probe or {}).get("reqs", [])[-10:]
    rec["last_responses"] = (probe or {}).get("resps", [])[-10:]

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    append_md(rec)
    print(f"Saved: {OUT_JSON}")
    print(f"Saved: {OUT_MD}")


if __name__ == "__main__":
    main()

