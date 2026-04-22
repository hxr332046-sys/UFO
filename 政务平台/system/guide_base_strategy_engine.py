#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/guide_base_strategy_engine_run.json")

BASE = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base"
CASES = [
    {"case_id": "case_02_4", "busiType": "02_4", "entType": "1100"},
    {"case_id": "case_07", "busiType": "07", "entType": "1100"},
]


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=20)
        self.idx = 1

    def call(self, method: str, params=None):
        if params is None:
            params = {}
        my_id = self.idx
        self.idx += 1
        self.ws.send(json.dumps({"id": my_id, "method": method, "params": params}))
        started = time.time()
        while True:
            if time.time() - started > 25:
                return {"error": {"message": f"timeout in {method}"}}
            raw = self.ws.recv()
            msg = json.loads(raw)
            if msg.get("id") != my_id:
                continue
            if "error" in msg:
                return {"error": msg["error"]}
            return msg.get("result", {})

    def ev(self, expr: str, timeout=60000):
        data = self.call(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout},
        )
        return (((data or {}).get("result") or {}).get("value"))

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p.get("webSocketDebuggerUrl")
    return None


def ensure_probe(cdp: CDP):
    return cdp.ev(
        r"""(function(){
          window.__se_probe={reqs:[],resps:[]};
          if(window.__se_probe_hooked) return true;
          window.__se_probe_hooked=true;
          var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
          XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__m=m;return oo.apply(this,arguments);};
          XMLHttpRequest.prototype.send=function(b){
            var u=this.__u||'';
            if(u.indexOf('/icpsp-api/')>=0){
              window.__se_probe.reqs.push({t:Date.now(),m:this.__m,u:u.slice(0,240),body:(b||'').slice(0,400)});
              var self=this; self.addEventListener('load',function(){
                window.__se_probe.resps.push({t:Date.now(),u:u.slice(0,240),status:self.status,text:(self.responseText||'').slice(0,400)});
              });
            }
            return os.apply(this,arguments);
          };
          return true;
        })()"""
    )


def get_state(cdp: CDP):
    return cdp.ev(
        r"""(function(){
          function visible(el){return !!(el&&el.offsetParent!==null);}
          function hasTxt(t){return (document.body.innerText||'').indexOf(t)>=0;}
          function inDialogVisible(t){
            var wraps=[...document.querySelectorAll('.el-dialog__wrapper')].filter(w=>visible(w));
            for(var w of wraps){ if((w.innerText||'').indexOf(t)>=0) return true; }
            return false;
          }
          return {
            href:location.href,
            hash:location.hash,
            hasNamePrompt:hasTxt('请选择是否需要名称'),
            hasQualificationPrompt:hasTxt('请确认您属于上述人员范围'),
            dialogCount:[...document.querySelectorAll('.el-dialog__wrapper')].filter(w=>visible(w)).length,
            qDialogVisible:inDialogVisible('请确认您属于上述人员范围'),
            nDialogVisible:inDialogVisible('请选择是否需要名称'),
            hasYunbangban:hasTxt('云帮办流程模式选择'),
            buttons:[...document.querySelectorAll('button,.el-button')].filter(b=>visible(b)).map(b=>({text:(b.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!b.disabled})).slice(0,20),
            probeReqCount:((window.__se_probe||{}).reqs||[]).length
          };
        })()"""
    )


def do_action(cdp: CDP, tag: str):
    expr = {
        "close_q_dialog": r"""(function(){
          var wraps=[...document.querySelectorAll('.el-dialog__wrapper')].filter(w=>w.offsetParent!==null&&(w.innerText||'').indexOf('请确认您属于上述人员范围')>=0);
          for(var w of wraps){
            var close=w.querySelector('.el-dialog__headerbtn,.el-dialog__close');
            if(close){close.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));return true;}
            var btn=[...w.querySelectorAll('button,.el-button,span')].find(e=>((e.textContent||'').replace(/\s+/g,' ').trim()).indexOf('关 闭')>=0||((e.textContent||'').replace(/\s+/g,' ').trim()).indexOf('关闭')>=0);
            if(btn){btn.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));return true;}
          }
          return false;
        })()""",
        "select_not_apply": r"""(function(){
          var el=[...document.querySelectorAll('label,span,div,a,li')].find(e=>e.offsetParent!==null&&((e.textContent||'').replace(/\s+/g,' ').trim()).indexOf('未申请')>=0);
          if(!el) return false;
          el.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
          return true;
        })()""",
        "confirm_name_prompt": r"""(function(){
          var wraps=[...document.querySelectorAll('.el-dialog__wrapper')].filter(w=>w.offsetParent!==null&&(w.innerText||'').indexOf('请选择是否需要名称')>=0);
          for(var w of wraps){
            var ok=[...w.querySelectorAll('button,.el-button,span')].find(e=>((e.textContent||'').replace(/\s+/g,' ').trim()).indexOf('确定')>=0);
            if(ok){ok.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));return true;}
          }
          return false;
        })()""",
        "next": r"""(function(){
          var n=[...document.querySelectorAll('button,.el-button')].find(b=>b.offsetParent!==null&&(b.textContent||'').indexOf('下一步')>=0&&!b.disabled);
          if(!n) return false;
          n.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
          return true;
        })()""",
        "call_flow_save": r"""(function(){
          function walk(vm,d){
            if(!vm||d>12) return null;
            var n=(vm.$options&&vm.$options.name)||'';
            if(n==='index'&&typeof vm.flowSave==='function') return vm;
            for(var c of (vm.$children||[])){var r=walk(c,d+1);if(r) return r;}
            return null;
          }
          var app=document.getElementById('app'); var vm=app&&app.__vue__?walk(app.__vue__,0):null;
          if(!vm) return {ok:false,msg:'no_index_vm'};
          try{vm.flowSave();}catch(e){return {ok:false,msg:String(e)}}
          return {ok:true};
        })()""",
    }.get(tag)
    if not expr:
        return False
    return cdp.ev(expr)


def run_case(cdp: CDP, case: dict):
    url = f"{BASE}?busiType={case['busiType']}&entType={case['entType']}&marPrId=&marUniscId="
    cdp.ev(f"location.href={json.dumps(url, ensure_ascii=False)}")
    time.sleep(4)
    ensure_probe(cdp)

    steps = []
    for _ in range(5):
        before = get_state(cdp) or {}
        req_before = before.get("probeReqCount", 0)
        hash_before = before.get("hash", "")

        if before.get("qDialogVisible"):
            action = "close_q_dialog"
        elif before.get("hasNamePrompt") or before.get("nDialogVisible"):
            action = "confirm_name_prompt"
        elif not before.get("hasYunbangban"):
            action = "select_not_apply"
        else:
            action = "next"

        acted = do_action(cdp, action)
        time.sleep(1)
        if action in {"select_not_apply", "confirm_name_prompt"}:
            do_action(cdp, "next")
            time.sleep(1)
        after = get_state(cdp) or {}
        req_after = after.get("probeReqCount", 0)
        hash_after = after.get("hash", "")
        changed = (req_after > req_before) or (hash_after != hash_before)
        steps.append(
            {
                "before": before,
                "action": action,
                "acted": acted,
                "after": after,
                "assertion_request_or_hash_changed": changed,
            }
        )
        if changed or after.get("hasYunbangban"):
            break

    # fallback: call flowSave once and assert again
    fb_before = get_state(cdp) or {}
    fb_req_before = fb_before.get("probeReqCount", 0)
    fb_hash_before = fb_before.get("hash", "")
    fb_call = do_action(cdp, "call_flow_save")
    time.sleep(1)
    fb_after = get_state(cdp) or {}
    fb_changed = (fb_after.get("probeReqCount", 0) > fb_req_before) or (fb_after.get("hash", "") != fb_hash_before)
    fallback = {
        "before": fb_before,
        "call_flow_save": fb_call,
        "after": fb_after,
        "assertion_request_or_hash_changed": fb_changed,
    }
    return {
        "case": case,
        "url": url,
        "steps": steps,
        "fallback": fallback,
        "result": "passed_transition_assertion" if any(s["assertion_request_or_hash_changed"] for s in steps) or fb_changed else "blocked_no_side_effect",
    }


def main():
    ws = pick_ws()
    if not ws:
        OUT.write_text(json.dumps({"error": "no_page_found"}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    cdp = CDP(ws)
    cdp.call("Page.enable", {})
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "runs": []}
    for case in CASES:
        rec["runs"].append(run_case(cdp, case))
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    cdp.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

