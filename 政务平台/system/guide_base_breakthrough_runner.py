#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/guide_base_breakthrough_runner.json")

GUIDE_BASE = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base"
CASES = [
    {"case_id": "02_4", "busiType": "02_4", "entType": "4540", "rounds": 3},
    {"case_id": "07", "busiType": "07", "entType": "1100", "rounds": 2},
]


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=20)
        self.seq = 1

    def call(self, method: str, params=None):
        if params is None:
            params = {}
        i = self.seq
        self.seq += 1
        self.ws.send(json.dumps({"id": i, "method": method, "params": params}))
        started = time.time()
        while True:
            if time.time() - started > 25:
                return {"error": {"message": f"timeout {method}"}}
            msg = json.loads(self.ws.recv())
            if msg.get("id") != i:
                continue
            if "error" in msg:
                return {"error": msg["error"]}
            return msg.get("result", {})

    def ev(self, expr: str, timeout=60000):
        ret = self.call(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout},
        )
        return (((ret or {}).get("result") or {}).get("value"))

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def list_pages():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    return [p for p in pages if p.get("type") == "page"]


def pick_ws():
    pages = list_pages()
    for p in pages:
        url = p.get("url", "")
        if "icpsp-web-pc" in url and "zhjg.scjdglj.gxzf.gov.cn:9087" in url:
            return p.get("webSocketDebuggerUrl"), pages
    if pages:
        return pages[0].get("webSocketDebuggerUrl"), pages
    return None, pages


def ensure_probe(cdp: CDP):
    return cdp.ev(
        r"""(function(){
          window.__brk={reqs:[],resps:[]};
          if(window.__brk_hooked) return true;
          window.__brk_hooked=true;
          var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
          XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__m=m;return oo.apply(this,arguments);};
          XMLHttpRequest.prototype.send=function(b){
            var u=this.__u||'';
            if(u.indexOf('/icpsp-api/')>=0){
              window.__brk.reqs.push({t:Date.now(),m:this.__m,u:u.slice(0,260),body:(b||'').slice(0,500)});
              var self=this; self.addEventListener('load',function(){
                window.__brk.resps.push({t:Date.now(),u:u.slice(0,260),status:self.status,text:(self.responseText||'').slice(0,500)});
              });
            }
            return os.apply(this,arguments);
          };
          return true;
        })()"""
    )


def state(cdp: CDP):
    return cdp.ev(
        r"""(function(){
          function visible(el){return !!(el&&el.offsetParent!==null);}
          var txt=(document.body&&document.body.innerText)||'';
          return {
            href:location.href,hash:location.hash,
            hasGuideBase:location.href.indexOf('name-register.html#/guide/base')>=0,
            hasCore:location.href.indexOf('/core.html#')>=0,
            hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0,
            hasNamePrompt:txt.indexOf('请选择是否需要名称')>=0,
            hasQualificationPrompt:txt.indexOf('请确认您属于上述人员范围')>=0,
            buttons:[...document.querySelectorAll('button,.el-button')].filter(b=>visible(b)).map(b=>({text:(b.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!b.disabled})).slice(0,20),
            reqCount:((window.__brk||{}).reqs||[]).length
          };
        })()"""
    )


def action(cdp: CDP, tag: str):
    scripts = {
        "select_not_apply": r"""(function(){
          var keys=['未申请','未办理企业名称预保留','未办理'];
          var els=[...document.querySelectorAll('label,span,div,a,li')].filter(x=>x.offsetParent!==null);
          for(var k of keys){
            var e=els.find(x=>((x.textContent||'').replace(/\s+/g,' ').trim()).indexOf(k)>=0);
            if(e){e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));return {ok:true,hit:k,text:(e.textContent||'').trim().slice(0,40)};}
          }
          return {ok:false};
        })()""",
        "check_qualification": r"""(function(){
          // 勾选所有可见未勾选的checkbox（常见：资格范围确认、须知同意）
          var cbs=[...document.querySelectorAll('.el-checkbox, label.el-checkbox')].filter(x=>x.offsetParent!==null);
          var clicked=0;
          for(var cb of cbs){
            var txt=(cb.textContent||'').replace(/\s+/g,' ').trim();
            var isChecked=cb.classList && cb.classList.contains('is-checked');
            if(!isChecked){
              cb.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
              clicked++;
            }
          }
          // 也尝试 radio 选择“未办理/未申请”
          var rs=[...document.querySelectorAll('.el-radio, label.el-radio')].filter(x=>x.offsetParent!==null);
          for(var r of rs){
            var t=(r.textContent||'').replace(/\s+/g,' ').trim();
            if(t.indexOf('未办理')>=0||t.indexOf('未申请')>=0){
              r.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
              break;
            }
          }
          return {clicked:clicked,cbCount:cbs.length,radioCount:rs.length};
        })()""",
        "next": r"""(function(){var e=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0&&!x.disabled);if(e){e.click();return true;}return false;})()""",
        "confirm": r"""(function(){var e=[...document.querySelectorAll('button,.el-button,span')].find(x=>x.offsetParent!==null&&((x.textContent||'').replace(/\s+/g,' ').trim()).indexOf('确定')>=0);if(e){e.click();return true;}return false;})()""",
        "close": r"""(function(){var e=[...document.querySelectorAll('button,.el-button,span,.el-dialog__close')].find(x=>x.offsetParent!==null&&(((x.textContent||'').replace(/\s+/g,' ').trim()).indexOf('关 闭')>=0||((x.textContent||'').replace(/\s+/g,' ').trim()).indexOf('关闭')>=0));if(e){e.click();return true;}return false;})()""",
        "vm_flow_save": r"""(function(){function walk(vm,d){if(!vm||d>12)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='index'&&typeof vm.flowSave==='function')return vm;for(var c of (vm.$children||[])){var r=walk(c,d+1);if(r)return r;}return null;}var app=document.getElementById('app');var vm=app&&app.__vue__?walk(app.__vue__,0):null;if(!vm)return {ok:false,msg:'no_vm'};try{vm.flowSave();return {ok:true};}catch(e){return {ok:false,msg:String(e)}}})()""",
    }
    return cdp.ev(scripts[tag]) if tag in scripts else False


def run_round(cdp: CDP, busi_type: str, ent_type: str):
    target = f"{GUIDE_BASE}?busiType={busi_type}&entType={ent_type}&marPrId=&marUniscId="
    cdp.ev(f"location.href={json.dumps(target, ensure_ascii=False)}")
    time.sleep(4)
    ensure_probe(cdp)
    logs = []
    for _ in range(6):
        before = state(cdp) or {}
        req_before = before.get("reqCount", 0)
        hash_before = before.get("hash", "")
        if before.get("hasCore") or before.get("hasYunbangban"):
            logs.append({"before": before, "action": "noop", "changed": True})
            break
        a0 = action(cdp, "check_qualification")
        a1 = action(cdp, "close")
        a2 = action(cdp, "confirm")
        a3 = action(cdp, "select_not_apply")
        a4 = action(cdp, "next")
        if not any([a0, a1, a2, a3, a4]):
            action(cdp, "vm_flow_save")
        time.sleep(1)
        after = state(cdp) or {}
        changed = (after.get("reqCount", 0) > req_before) or (after.get("hash", "") != hash_before)
        logs.append(
            {
                "before": before,
                "actions": {"check_qualification": a0, "close": a1, "confirm": a2, "select_not_apply": a3, "next": a4},
                "after": after,
                "changed": changed,
            }
        )
        if changed:
            break
    last = logs[-1] if logs else {}
    return {
        "target": target,
        "logs": logs,
        "result": "transition_detected" if any(x.get("changed") for x in logs) else "blocked_no_side_effect",
        "final": last.get("after") or last.get("before"),
    }


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "cases": []}
    ws_url, pages = pick_ws()
    rec["environment"] = {
        "pages": [p.get("url") for p in pages],
        "has_icpsp_page": any("icpsp-web-pc" in (p.get("url") or "") for p in pages),
    }
    if not ws_url:
        rec["error"] = "no_page_target"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    cdp = CDP(ws_url)
    cdp.call("Page.enable", {})
    for case in CASES:
        case_rec = {"case": case, "round_runs": []}
        for _ in range(case["rounds"]):
            case_rec["round_runs"].append(run_round(cdp, case["busiType"], case["entType"]))
        case_rec["summary"] = {
            "any_transition": any(r["result"] == "transition_detected" for r in case_rec["round_runs"]),
            "all_blocked": all(r["result"] != "transition_detected" for r in case_rec["round_runs"]),
        }
        rec["cases"].append(case_rec)
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    cdp.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

