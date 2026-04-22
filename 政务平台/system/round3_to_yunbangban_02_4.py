#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT_MAIN = Path("G:/UFO/政务平台/dashboard/data/records/full_submit_test_02_4_round3_to_yunbangban.json")
OUT_MD = Path("G:/UFO/政务平台/dashboard/data/records/full_submit_test_02_4_round3_to_yunbangban.md")
OUT_ERR = Path("G:/UFO/政务平台/dashboard/data/records/round3_error_fix_log.json")
OUT_STOP = Path("G:/UFO/政务平台/dashboard/data/records/round3_yunbangban_stop_evidence.json")

URL_ENTERPRISE = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone?fromProject=portal&fromPage=%2Findex%2Fpage&busiType=02_4&merge=Y"
URL_DECL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/namenotice/declaration-instructions?fromProject=portal&fromPage=%2Findex%2Fenterprise%2Fenterprise-zone&entType=4540&busiType=02_4"
URL_GUIDE = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=4540&marPrId=&marUniscId="
URL_BASIC = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html#/flow/base/basic-info"
NEW_COMPANY_NAME = "广西玉林桂柚百货中心（个人独资）"


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
            msg = json.loads(ws.recv())
        except Exception:
            continue
        if msg.get("id") == 1:
            ws.close()
            return msg.get("result", {}).get("result", {}).get("value")


def snap(ws, tag):
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
              var app=document.getElementById('app');
              var fc=(app&&app.__vue__)?find(app.__vue__,0):null;
              var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);
              var btns=[...document.querySelectorAll('button,.el-button')].filter(x=>x.offsetParent!==null).map(x=>({text:(x.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!x.disabled}));
              return {href:location.href,hash:location.hash,text:(document.body.innerText||'').slice(0,1200),flowData:fc&&fc.params?fc.params.flowData:null,errors:errs.slice(0,10),buttons:btns.slice(0,20)};
            })()""",
        ),
    }


def is_yunbangban(snapshot_data):
    t = (snapshot_data.get("text") or "")
    h = (snapshot_data.get("hash") or "")
    return ("云帮办流程模式选择" in t) or ("help" in h.lower() and "mode" in h.lower())


def main():
    rec = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "company_name_target": NEW_COMPANY_NAME,
        "steps": [],
    }
    errlog = {"started_at": rec["started_at"], "items": []}

    ws, cur = pick_ws()
    if not ws:
        rec["error"] = "no_page"
        OUT_MAIN.parent.mkdir(parents=True, exist_ok=True)
        OUT_MAIN.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        OUT_ERR.write_text(json.dumps(errlog, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    # XHR capture
    ev(
        ws,
        r"""(function(){
          window.__round3_cap=window.__round3_cap||{reqs:[],resps:[]};
          if(!window.__round3_hook){
            window.__round3_hook=true;
            var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__m=m;return oo.apply(this,arguments);};
            XMLHttpRequest.prototype.send=function(b){
              var u=this.__u||'';
              if(u.indexOf('/icpsp-api/')>=0){
                window.__round3_cap.reqs.push({t:Date.now(),m:this.__m,u:u.slice(0,260),body:(b||'').slice(0,700)});
                var self=this; self.addEventListener('load', function(){
                  window.__round3_cap.resps.push({t:Date.now(),u:u.slice(0,260),status:self.status,text:(self.responseText||'').slice(0,1000)});
                });
              }
              return os.apply(this,arguments);
            };
          }
          return {ok:true};
        })()""",
    )

    # Start from portal path
    ev(ws, f"location.href='{URL_ENTERPRISE}'", timeout=15000)
    time.sleep(5)
    ws, _ = pick_ws("portal.html#/index/enterprise/enterprise-zone")
    rec["steps"].append({"step": "S1_enterprise_zone", "data": snap(ws, "enterprise")["data"]})
    ev(
        ws,
        r"""(function(){
          var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('开始办理')>=0&&!x.disabled);
          if(b){b.click(); return {clicked:true};}
          return {clicked:false};
        })()""",
    )
    time.sleep(2)

    # declaration
    ev(ws, f"location.href='{URL_DECL}'", timeout=15000)
    time.sleep(5)
    ws, _ = pick_ws("name-register.html#/namenotice/declaration-instructions")
    rec["steps"].append({"step": "S2_declaration", "data": snap(ws, "declaration")["data"]})
    ev(
        ws,
        r"""(function(){
          var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('我已阅读并同意')>=0&&!x.disabled);
          if(b){b.click();return {clicked:true};}
          return {clicked:false};
        })()""",
    )
    time.sleep(2)

    # guide
    ev(ws, f"location.href='{URL_GUIDE}'", timeout=15000)
    time.sleep(6)
    ws, _ = pick_ws("name-register.html#/guide/base")
    rec["steps"].append({"step": "S3_guide_base", "data": snap(ws, "guide")["data"]})
    ev(
        ws,
        r"""(async function(){
          function walk(vm,d){if(!vm||d>12)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='index'&&typeof vm.flowSave==='function')return vm;for(var ch of (vm.$children||[])){var r=walk(ch,d+1);if(r)return r;}return null;}
          function clickLabel(t){
            var labels=[...document.querySelectorAll('label.tni-radio,.tni-radio,.tni-radio__label,label,span,div')].filter(n=>n.offsetParent!==null);
            for(var n of labels){var tx=(n.textContent||'').replace(/\s+/g,' ').trim();if(tx===t||tx.indexOf(t)>=0){(n.closest('label.tni-radio,.tni-radio')||n).dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));return tx;}}
            return null;
          }
          var app=document.getElementById('app'); var vm=app&&app.__vue__?walk(app.__vue__,0):null;
          clickLabel('个人独资企业');
          clickLabel('未申请');
          if(vm&&vm.form){
            vm.$set(vm.form,'entType','4540');
            vm.$set(vm.form,'nameCode','0');
            // key bypass: avoid addressChild.getFormData undefined branch
            vm.$set(vm.form,'havaAdress','0');
            vm.$set(vm.form,'distCode','450102');
            vm.$set(vm.form,'streetCode','450102');
            vm.$set(vm.form,'streetName','兴宁区');
            vm.$set(vm.form,'address','兴宁区');
            vm.$set(vm.form,'detAddress','容州大道88号');
          }
          var btn=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0);
          if(btn&&btn.__vue__&&btn.__vue__.$listeners&&btn.__vue__.$listeners.click){
            try{
              var p=btn.__vue__.$listeners.click({type:'click',target:btn,currentTarget:btn});
              if(p&&typeof p.then==='function'){try{await p;}catch(e){}}
            }catch(e){}
          }else if(btn){
            btn.click();
          }
          var ok=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&((x.textContent||'').replace(/\s+/g,'').indexOf('确定')>=0)&&!x.disabled);
          if(ok)ok.click();
          return {done:true};
        })()""",
    )
    time.sleep(7)

    # enter core basic-info
    ws, cur = pick_ws("core.html#/flow/base/basic-info")
    if not ws:
        ws, _ = pick_ws()
        ev(ws, f"location.href='{URL_BASIC}'", timeout=15000)
        time.sleep(6)
        ws, cur = pick_ws("core.html#/flow/base/basic-info")
    rec["steps"].append({"step": "S4_basic_open", "data": {"url": cur}})

    # Fill only empty required + try set new company name if editable and different
    basic_fill = ev(
        ws,
        f"""(function(){{
          function setIfEmpty(labelKw,val){{
            var items=document.querySelectorAll('.el-form-item');
            for(var i=0;i<items.length;i++){{
              var lb=items[i].querySelector('.el-form-item__label');
              var t=(lb&&lb.textContent||'').replace(/\\s+/g,' ').trim();
              if(t.indexOf(labelKw)>=0){{
                var inp=items[i].querySelector('input.el-input__inner,textarea.el-textarea__inner');
                if(inp && !inp.disabled){{
                  var old=(inp.value||'').trim();
                  if(old) return {{ok:true,kept:true,label:t,old:old}};
                  var setter=Object.getOwnPropertyDescriptor((inp.tagName==='TEXTAREA'?HTMLTextAreaElement:HTMLInputElement).prototype,'value').set;
                  setter.call(inp,val); inp.dispatchEvent(new Event('input',{{bubbles:true}})); inp.dispatchEvent(new Event('change',{{bubbles:true}}));
                  return {{ok:true,kept:false,label:t,val:val}};
                }}
              }}
            }}
            return {{ok:false,label:labelKw}};
          }}
          function setCompanyName(newName){{
            var items=document.querySelectorAll('.el-form-item');
            for(var i=0;i<items.length;i++){{
              var lb=items[i].querySelector('.el-form-item__label');
              var t=(lb&&lb.textContent||'').replace(/\\s+/g,' ').trim();
              if(t.indexOf('企业名称')>=0){{
                var inp=items[i].querySelector('input.el-input__inner');
                if(inp && !inp.disabled){{
                  var old=(inp.value||'').trim();
                  if(old===newName) return {{ok:true,changed:false,reason:'already_target',old:old}};
                  var setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                  setter.call(inp,newName); inp.dispatchEvent(new Event('input',{{bubbles:true}})); inp.dispatchEvent(new Event('change',{{bubbles:true}}));
                  return {{ok:true,changed:true,old:old,new:newName}};
                }}
                return {{ok:false,reason:'disabled_or_missing_input'}};
              }}
            }}
            return {{ok:false,reason:'label_not_found'}};
          }}
          var out={{}};
          out.company=setCompanyName({json.dumps(NEW_COMPANY_NAME, ensure_ascii=False)});
          out.phone=setIfEmpty('联系电话','18977514892');
          out.emp=setIfEmpty('从业人数','3');
          out.addr=setIfEmpty('详细地址','容州镇城西路21号2单元803室');
          out.bizaddr=setIfEmpty('生产经营地详细地址','容州镇城西路21号2单元803室');
          var cap=[...document.querySelectorAll('label,span,div')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('以个人财产出资')>=0);
          if(cap) cap.dispatchEvent(new MouseEvent('click',{{bubbles:true,cancelable:true,view:window}}));
          var save=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('保存并下一步')>=0&&!x.disabled);
          if(save) save.click();
          return out;
        }})()""",
    )
    rec["steps"].append({"step": "S5_basic_fill_save", "data": basic_fill})
    time.sleep(8)
    s_after_basic = snap(ws, "after_basic")["data"]
    rec["steps"].append({"step": "S6_after_basic", "data": s_after_basic})

    # If validation errors, attempt auto-fix once
    if s_after_basic.get("errors"):
        errlog["items"].append(
            {
                "stage": "basic-info",
                "error": s_after_basic.get("errors"),
                "fix": "rerun targeted fills and save",
            }
        )
        ev(
            ws,
            r"""(function(){
              function setByLabel(k,v){
                var items=document.querySelectorAll('.el-form-item');
                for(var i=0;i<items.length;i++){
                  var lb=items[i].querySelector('.el-form-item__label');
                  var t=(lb&&lb.textContent||'').replace(/\s+/g,' ').trim();
                  if(t.indexOf(k)>=0){
                    var inp=items[i].querySelector('input.el-input__inner,textarea.el-textarea__inner');
                    if(inp && !inp.disabled){
                      var setter=Object.getOwnPropertyDescriptor((inp.tagName==='TEXTAREA'?HTMLTextAreaElement:HTMLInputElement).prototype,'value').set;
                      setter.call(inp,v); inp.dispatchEvent(new Event('input',{bubbles:true})); inp.dispatchEvent(new Event('change',{bubbles:true}));
                    }
                  }
                }
              }
              setByLabel('联系电话','18977514892');
              setByLabel('从业人数','3');
              setByLabel('详细地址','容州镇城西路21号2单元803室');
              setByLabel('生产经营地详细地址','容州镇城西路21号2单元803室');
              var save=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('保存并下一步')>=0&&!x.disabled);
              if(save) save.click();
              return true;
            })()""",
        )
        time.sleep(6)
        rec["steps"].append({"step": "S6b_after_basic_fix", "data": snap(ws, "after_basic_fix")["data"]})

    # Attempt member-post
    ws_member, url_member = pick_ws("core.html#/flow/base/member-post")
    if ws_member:
        ws = ws_member
        rec["steps"].append({"step": "S7_member_post", "data": {"url": url_member}})
        ev(
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
                      if(old) return true;
                      var setter=Object.getOwnPropertyDescriptor((inp.tagName==='TEXTAREA'?HTMLTextAreaElement:HTMLInputElement).prototype,'value').set;
                      setter.call(inp,val); inp.dispatchEvent(new Event('input',{bubbles:true})); inp.dispatchEvent(new Event('change',{bubbles:true}));
                      return true;
                    }
                  }
                }
                return false;
              }
              var open=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&/编辑|添加成员/.test((x.textContent||''))&&!x.disabled);
              if(open) open.click();
              setIfEmpty('成员名称','李向晨');
              setIfEmpty('证件号码','450921199202146430');
              setIfEmpty('民族','汉族');
              setIfEmpty('出生日期','1992-02-14');
              setIfEmpty('发证机关','容县公安局');
              setIfEmpty('证件有效期起','2014-01-01');
              setIfEmpty('住址','广西玉林市容县容州镇环城路9号');
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
        time.sleep(8)
        after_member = snap(ws, "after_member")["data"]
        rec["steps"].append({"step": "S8_after_member", "data": after_member})
        if after_member.get("errors"):
            errlog["items"].append({"stage": "member-post", "error": after_member.get("errors"), "fix": "keep default values + retry skipped"})

    # Walk until yunbangban or max rounds; stop without next click once reached
    reached = False
    for i in range(6):
        ws_any, _ = pick_ws("core.html#/flow/base/")
        if not ws_any:
            ws_any, _ = pick_ws()
        s = snap(ws_any, f"loop_{i}")["data"]
        rec["steps"].append({"step": f"S9_loop_{i}", "data": s})
        if is_yunbangban(s):
            reached = True
            break
        # click save/next once to advance (only when not at target page)
        ev(
            ws_any,
            r"""(function(){
              var order=['保存并下一步','下一步','确定'];
              var btns=[...document.querySelectorAll('button,.el-button')].filter(x=>x.offsetParent!==null&&!x.disabled);
              for(var t of order){
                var b=btns.find(x=>(x.textContent||'').replace(/\s+/g,'').indexOf(t.replace(/\s+/g,''))>=0);
                if(b){b.click(); return {clicked:true,text:(b.textContent||'').trim()};}
              }
              return {clicked:false};
            })()""",
        )
        time.sleep(5)

    # Final snapshots
    ws_end, url_end = pick_ws()
    end_s = snap(ws_end, "final")["data"]
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    rec["final_url"] = url_end
    rec["final_hash"] = end_s.get("hash")
    fd = (end_s.get("flowData") or {})
    rec["busiId"] = fd.get("busiId")
    rec["nameId"] = fd.get("nameId")
    rec["network"] = ev(ws_end, "window.__round3_cap || {reqs:[],resps:[]}")
    rec["result"] = "stopped_at_yunbangban" if is_yunbangban(end_s) else "not_reached_yunbangban"
    rec["company_name_observed"] = ev(
        ws_end,
        r"""(function(){
          var t=(document.body.innerText||'');
          var m=t.match(/广西玉林[^\n]{2,40}（个人独资）/);
          return m?m[0]:'';
        })()""",
    )

    stop_ev = {"captured_at": rec["ended_at"], "url": url_end, "snapshot": end_s}

    OUT_MAIN.parent.mkdir(parents=True, exist_ok=True)
    OUT_MAIN.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_ERR.write_text(json.dumps(errlog, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_STOP.write_text(json.dumps(stop_ev, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# 02_4 Round3 到云帮办节点",
        "",
        f"- started_at: {rec.get('started_at','')}",
        f"- ended_at: {rec.get('ended_at','')}",
        f"- target_company_name: {NEW_COMPANY_NAME}",
        f"- observed_company_name: {rec.get('company_name_observed','')}",
        f"- result: {rec.get('result','')}",
        f"- final_hash: {rec.get('final_hash','')}",
        "",
        "## 关键ID",
        f"- busiId: {rec.get('busiId','')}",
        f"- nameId: {rec.get('nameId','')}",
        "",
        "## 错误修复摘要",
        f"- error_count: {len(errlog.get('items',[]))}",
        "",
        "## 证据文件",
        f"- {OUT_MAIN.as_posix()}",
        f"- {OUT_ERR.as_posix()}",
        f"- {OUT_STOP.as_posix()}",
    ]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"Saved: {OUT_MAIN}")
    print(f"Saved: {OUT_MD}")
    print(f"Saved: {OUT_ERR}")
    print(f"Saved: {OUT_STOP}")


if __name__ == "__main__":
    main()

