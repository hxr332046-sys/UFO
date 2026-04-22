#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT_JSON = Path("G:/UFO/政务平台/dashboard/data/records/full_submit_test_02_4_round2.json")
OUT_MD = Path("G:/UFO/政务平台/dashboard/data/records/full_submit_test_02_4_round2.md")

URL_ENTERPRISE = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone?fromProject=portal&fromPage=%2Findex%2Fpage&busiType=02_4&merge=Y"
URL_DECL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/namenotice/declaration-instructions?fromProject=portal&fromPage=%2Findex%2Fenterprise%2Fenterprise-zone&entType=4540&busiType=02_4"
URL_GUIDE = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=4540&marPrId=&marUniscId="
URL_BASIC = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html#/flow/base/basic-info"


def pick_ws(prefer=None):
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    if prefer:
        for p in pages:
            if p.get("type") == "page" and prefer in p.get("url", ""):
                return p["webSocketDebuggerUrl"], p.get("url", "")
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url, expr, timeout=70000):
    ws = websocket.create_connection(ws_url, timeout=20)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout}}))
    while True:
        try:
            m = json.loads(ws.recv())
        except Exception:
            continue
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def snapshot(ws, tag):
    return {
        "tag": tag,
        "at": time.strftime("%H:%M:%S"),
        "data": ev(
            ws,
            r"""(function(){
              function find(vm,d){
                if(!vm||d>20) return null;
                var n=(vm.$options&&vm.$options.name)||'';
                if(n==='flow-control') return vm;
                for(var c of (vm.$children||[])){var r=find(c,d+1); if(r) return r;}
                return null;
              }
              var fc=null;
              var app=document.getElementById('app');
              if(app&&app.__vue__) fc=find(app.__vue__,0);
              var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);
              var btns=[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null).map(b=>({text:(b.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!b.disabled}));
              return {href:location.href,hash:location.hash,flowData:fc&&fc.params?fc.params.flowData:null,errors:errs.slice(0,10),buttons:btns.slice(0,20)};
            })()""",
        ),
    }


def write_md(rec):
    lines = [
        "# 02_4 Round2 全链路重测",
        "",
        f"- started_at: {rec.get('started_at','')}",
        f"- ended_at: {rec.get('ended_at','')}",
        f"- result: {rec.get('result','')}",
        f"- final_hash: {rec.get('final_hash','')}",
        "",
        "## 关键ID",
        f"- busiId: {rec.get('busiId','')}",
        f"- nameId: {rec.get('nameId','')}",
        "",
        "## 节点记录",
    ]
    for i, st in enumerate(rec.get("steps", []), 1):
        lines.append(f"- {i}. {st.get('step','')} -> {st.get('note','')}")
    lines += ["", "## 接口摘要"]
    for r in rec.get("network", {}).get("resps", [])[-6:]:
        lines.append(f"- {r.get('u','')} status={r.get('status')} text={str(r.get('text',''))[:140]}")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    ws, cur = pick_ws()
    if not ws:
        rec["error"] = "no_page"
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        write_md(rec)
        return
    rec["steps"].append({"step": "S0_start", "note": cur})

    # hook xhr capture once
    ev(
        ws,
        r"""(function(){
          window.__round2_cap=window.__round2_cap||{reqs:[],resps:[]};
          if(!window.__round2_hook){
            window.__round2_hook=true;
            var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__m=m;return oo.apply(this,arguments);};
            XMLHttpRequest.prototype.send=function(b){
              var u=this.__u||'';
              if(u.indexOf('/icpsp-api/')>=0){
                window.__round2_cap.reqs.push({t:Date.now(),m:this.__m,u:u.slice(0,260),body:(b||'').slice(0,700)});
                var self=this; self.addEventListener('load',function(){
                  window.__round2_cap.resps.push({t:Date.now(),u:u.slice(0,260),status:self.status,text:(self.responseText||'').slice(0,900)});
                });
              }
              return os.apply(this,arguments);
            };
          }
          return {ok:true};
        })()""",
    )

    # enterprise-zone
    ev(ws, f"location.href='{URL_ENTERPRISE}'", timeout=15000)
    time.sleep(6)
    ws, _ = pick_ws("portal.html#/index/enterprise/enterprise-zone")
    rec["steps"].append({"step": "S1_enterprise", "note": "opened"})
    ev(
        ws,
        r"""(function(){
          var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('开始办理')>=0&&!x.disabled);
          if(b){b.click();return true;}return false;
        })()""",
    )
    time.sleep(2)

    # declaration
    ev(ws, f"location.href='{URL_DECL}'", timeout=15000)
    time.sleep(6)
    ws, _ = pick_ws("name-register.html#/namenotice/declaration-instructions")
    rec["steps"].append({"step": "S2_declaration", "note": "opened"})
    ev(
        ws,
        r"""(function(){
          var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('我已阅读并同意')>=0&&!x.disabled);
          if(b){b.click();return true;}return false;
        })()""",
    )
    time.sleep(2)

    # guide/base
    ev(ws, f"location.href='{URL_GUIDE}'", timeout=15000)
    time.sleep(6)
    ws, _ = pick_ws("name-register.html#/guide/base")
    rec["steps"].append({"step": "S3_guide", "note": "opened"})
    ev(
        ws,
        r"""(function(){
          var els=[...document.querySelectorAll('label,span,div,li,a')].filter(e=>e.offsetParent!==null);
          for(var e of els){
            var t=(e.textContent||'').replace(/\s+/g,' ').trim();
            // 优先走“未办理企业名称预保留”（自主申报），避免复用已过期 nameId
            if(t.indexOf('未办理企业名称预保留')>=0){e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));return 'picked_unreserved';}
          }
          var n=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0&&!x.disabled);
          if(n)n.click();
          var ok=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&((x.textContent||'').replace(/\s+/g,'').indexOf('确定')>=0)&&!x.disabled);
          if(ok)ok.click();
          return 'clicked_next';
        })()""",
    )
    time.sleep(8)

    # basic-info with preserve-default strategy
    ws, _ = pick_ws("core.html#/flow/base/basic-info")
    if not ws:
        ws, _ = pick_ws()
        ev(ws, f"location.href='{URL_BASIC}'", timeout=15000)
        time.sleep(5)
        ws, _ = pick_ws("core.html#/flow/base/basic-info")
    rec["steps"].append({"step": "S4_basic_info", "note": "fill required only if empty"})

    fill_basic = ev(
        ws,
        r"""(function(){
          function setIfEmpty(labelKw,val){
            var items=document.querySelectorAll('.el-form-item');
            for(var i=0;i<items.length;i++){
              var lb=items[i].querySelector('.el-form-item__label');
              var t=(lb&&lb.textContent||'').replace(/\s+/g,' ').trim();
              if(t.indexOf(labelKw)>=0){
                var inp=items[i].querySelector('input.el-input__inner,textarea.el-textarea__inner');
                if(inp && !inp.disabled){
                  var old=(inp.value||'').trim();
                  if(old) return {ok:true,kept:true,label:t,old:old};
                  var setter=Object.getOwnPropertyDescriptor((inp.tagName==='TEXTAREA'?HTMLTextAreaElement:HTMLInputElement).prototype,'value').set;
                  setter.call(inp,val); inp.dispatchEvent(new Event('input',{bubbles:true})); inp.dispatchEvent(new Event('change',{bubbles:true}));
                  return {ok:true,kept:false,label:t,val:val};
                }
              }
            }
            return {ok:false,label:labelKw};
          }
          var out={};
          out.phone=setIfEmpty('联系电话','18977514367');
          out.emp=setIfEmpty('从业人数','2');
          out.addr=setIfEmpty('详细地址','容州镇兴容街66号B座1502室');
          out.bizaddr=setIfEmpty('生产经营地详细地址','容州镇兴容街66号B座1502室');
          // select capital mode if missing
          var texts=['以个人财产出资','个人财产出资'];
          var clicked=false;
          for(var t of texts){
            var e=[...document.querySelectorAll('label,span,div')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf(t)>=0);
            if(e){e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window})); clicked=true;break;}
          }
          out.capitalMode={clicked:clicked};
          var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('保存并下一步')>=0&&!x.disabled);
          if(b){b.click(); out.save=true;} else out.save=false;
          return out;
        })()""",
    )
    rec["steps"].append({"step": "S5_basic_save", "note": json.dumps(fill_basic, ensure_ascii=False)})
    time.sleep(8)
    rec["steps"].append({"step": "S6_after_basic", "note": json.dumps(snapshot(ws, "after-basic")["data"], ensure_ascii=False)})

    # member-post fill minimal + save
    ws2, url2 = pick_ws("core.html#/flow/base/member-post")
    if ws2:
        ws = ws2
    rec["steps"].append({"step": "S7_member_post", "note": url2 or "not_in_member_post"})
    ev(
        ws,
        r"""(function(){
          function setByLabel(labelKw,val){
            var items=document.querySelectorAll('.el-form-item');
            for(var i=0;i<items.length;i++){
              var lb=items[i].querySelector('.el-form-item__label');
              var t=(lb&&lb.textContent||'').replace(/\s+/g,' ').trim();
              if(t.indexOf(labelKw)>=0){
                var inp=items[i].querySelector('input.el-input__inner,textarea.el-textarea__inner');
                if(inp && !inp.disabled){
                  var old=(inp.value||'').trim();
                  if(old) return true; // preserve default
                  var setter=Object.getOwnPropertyDescriptor((inp.tagName==='TEXTAREA'?HTMLTextAreaElement:HTMLInputElement).prototype,'value').set;
                  setter.call(inp,val); inp.dispatchEvent(new Event('input',{bubbles:true})); inp.dispatchEvent(new Event('change',{bubbles:true}));
                  return true;
                }
              }
            }
            return false;
          }
          // open add/edit if modal needed
          var open=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&/编辑|添加成员/.test((x.textContent||''))&&!x.disabled);
          if(open) open.click();
          setByLabel('成员名称','梁天成');
          setByLabel('证件号码','450921199011167812');
          setByLabel('民族','汉族');
          setByLabel('出生日期','1990-11-16');
          setByLabel('发证机关','容县公安局');
          setByLabel('证件有效期起','2012-01-01');
          setByLabel('住址','广西玉林市容县容州镇南街2号');
          var roles=['投资人','委托代理人','联络员'];
          for(var r of roles){
            var e=[...document.querySelectorAll('label,span,div')].find(x=>x.offsetParent!==null&&(x.textContent||'').replace(/\s+/g,'').indexOf(r)>=0);
            if(e)e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
          }
          var ok=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&((x.textContent||'').replace(/\s+/g,'').indexOf('确定')>=0)&&!x.disabled);
          if(ok)ok.click();
          var save=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('保存并下一步')>=0&&!x.disabled);
          if(save)save.click();
          return true;
        })()""",
    )
    time.sleep(10)
    rec["steps"].append({"step": "S8_after_member", "note": json.dumps(snapshot(ws, "after-member")["data"], ensure_ascii=False)})

    # final status
    final = snapshot(ws, "final")["data"]
    rec["final_hash"] = final.get("hash")
    fd = (final.get("flowData") or {})
    rec["busiId"] = fd.get("busiId")
    rec["nameId"] = fd.get("nameId")
    rec["network"] = ev(ws, "window.__round2_cap || {reqs:[],resps:[]}")

    resps = rec["network"].get("resps", [])
    joined = " ".join([(r.get("text") or "") for r in resps[-8:]])
    if ("提交成功" in (final.get("href") or "")) or ("00000" in joined and "operationBusinessDataInfo" in " ".join([(r.get("u") or "") for r in resps[-8:]])):
        rec["result"] = "progressed_or_partial_success"
    if "A0002" in joined:
        rec["result"] = "blocked_A0002"
    rec.setdefault("result", "inconclusive")
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    write_md(rec)
    print(f"Saved: {OUT_JSON}")
    print(f"Saved: {OUT_MD}")


if __name__ == "__main__":
    main()

