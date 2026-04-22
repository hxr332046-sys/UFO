#!/usr/bin/env python
# -*- coding: utf-8 -*-
import base64
import json
import time
from pathlib import Path

import requests
import websocket

OUT_MAIN = Path("G:/UFO/政务平台/dashboard/data/records/full_submit_test_02_4_round3_to_yunbangban.json")
OUT_ERR = Path("G:/UFO/政务平台/dashboard/data/records/round3_error_fix_log.json")
OUT_STOP = Path("G:/UFO/政务平台/dashboard/data/records/round3_yunbangban_stop_evidence.json")
OUT_MD = Path("G:/UFO/政务平台/dashboard/data/records/full_submit_test_02_4_round3_to_yunbangban.md")
OUT_SHOT_IDX = Path("G:/UFO/政务平台/dashboard/data/records/round3_cdp_screenshots_index.json")
SHOT_DIR = Path("G:/UFO/政务平台/dashboard/data/records/round3_cdp_shots")

URL_GUIDE = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=1100&marPrId=&marUniscId="
TARGET_NAME = "广西玉林桂柚百货中心（个人独资）"


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=25)
        self.i = 1

    def call(self, method: str, params=None):
        if params is None:
            params = {}
        my_id = self.i
        self.i += 1
        self.ws.send(json.dumps({"id": my_id, "method": method, "params": params}))
        started = time.time()
        while True:
            try:
                raw = self.ws.recv()
            except Exception:
                if time.time() - started > 25:
                    return {"error": {"message": f"timeout waiting for {method}"}}
                continue
            msg = json.loads(raw)
            if msg.get("id") == my_id:
                if "error" in msg:
                    return {"error": msg["error"]}
                return msg.get("result", {})
            if time.time() - started > 25:
                return {"error": {"message": f"timeout waiting for id {my_id} in {method}"}}

    def eval(self, expr: str, timeout=60000):
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


def ensure_hook(cdp: CDP):
    cdp.eval(
        r"""(function(){
          window.__atk_cap=window.__atk_cap||{reqs:[],resps:[]};
          if(!window.__atk_hook){
            window.__atk_hook=true;
            var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__m=m;return oo.apply(this,arguments);};
            XMLHttpRequest.prototype.send=function(b){
              var u=this.__u||'';
              if(u.indexOf('/icpsp-api/')>=0){
                window.__atk_cap.reqs.push({t:Date.now(),m:this.__m,u:u.slice(0,260),body:(b||'').slice(0,700)});
                var self=this; self.addEventListener('load',function(){
                  window.__atk_cap.resps.push({t:Date.now(),u:u.slice(0,260),status:self.status,text:(self.responseText||'').slice(0,1000)});
                });
              }
              return os.apply(this,arguments);
            };
          }
          return true;
        })()"""
    )


def take_shot(cdp: CDP, name: str):
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    data = cdp.call("Page.captureScreenshot", {"format": "png"})
    b64 = data.get("data", "")
    p = SHOT_DIR / f"{name}.png"
    if b64:
        p.write_bytes(base64.b64decode(b64))
    return p.as_posix()


def state(cdp: CDP):
    return cdp.eval(
        r"""(function(){
          function visible(el){return !!(el && el.offsetParent!==null);}
          var text=(document.body.innerText||'');
          var popup=Array.from(document.querySelectorAll('.el-dialog__wrapper,.el-dialog')).some(function(d){return visible(d) && ((d.innerText||'').indexOf('提示')>=0 || (d.innerText||'').indexOf('请选择是否需要名称')>=0);});
          function selected(k){
            var nodes=Array.from(document.querySelectorAll('*')).filter(function(n){return visible(n) && ((n.textContent||'').replace(/\s+/g,' ').trim()===k);});
            for(var n of nodes){
              var c=n.className||'';
              if(typeof c==='string' && /active|checked|is-checked|selected/.test(c)) return true;
              var p=n.parentElement;
              if(p && typeof p.className==='string' && /active|checked|is-checked|selected/.test(p.className)) return true;
            }
            return false;
          }
          var btns=Array.from(document.querySelectorAll('button,.el-button')).filter(function(b){return visible(b)}).map(function(b){return {text:(b.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!b.disabled};});
          return {
            href:location.href,hash:location.hash,text:text.slice(0,1800),
            popupVisible:popup,
            selectedNotApply:selected('未申请'),
            selectedReserved:selected('已办理企业名称预保留'),
            hasYunbangban:text.indexOf('云帮办流程模式选择')>=0,
            buttons:btns.slice(0,20)
          };
        })()"""
    )


def action(cdp: CDP):
    return cdp.eval(
        r"""(function(){
          function clickByExact(t){
            var els=Array.from(document.querySelectorAll('button,.el-button,label,span,div,a,li')).filter(function(e){return e.offsetParent!==null;});
            for(var e of els){
              var tx=(e.textContent||'').replace(/\s+/g,' ').trim();
              if(tx===t){
                e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
                return true;
              }
            }
            return false;
          }
          function clickContains(t){
            var els=Array.from(document.querySelectorAll('button,.el-button,label,span,div,a,li')).filter(function(e){return e.offsetParent!==null;});
            for(var e of els){
              var tx=(e.textContent||'').replace(/\s+/g,' ').trim();
              if(tx.indexOf(t)>=0){
                e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
                return true;
              }
            }
            return false;
          }
          var txt=(document.body.innerText||'');
          // priority 1: blocking dialogs (close first)
          if(clickContains('关 闭') || clickContains('关闭')) return 'ui_block_popup:click_关闭';
          if(txt.indexOf('请选择是否需要名称')>=0){
            if(clickContains('确定')) return 'ui_block_popup:click_确定';
          }
          // priority 2: ensure selections
          clickContains('个人独资企业');
          if(clickContains('未申请')) return 'selection_not_applied:click_未申请';
          // priority 3: next
          if(clickContains('下一步')) return 'next_no_transition:click_下一步';
          return 'backend_silent_no_request:no_click';
        })()"""
    )


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "target_company_name": TARGET_NAME, "steps": []}
    err = {"started_at": rec["started_at"], "items": []}
    shot_idx = []

    ws_url, _ = pick_ws("name-register.html#/guide/base")
    if not ws_url:
        ws_url, _ = pick_ws()
    cdp = CDP(ws_url)
    cdp.call("Page.enable", {})
    cdp.eval(f"location.href={json.dumps(URL_GUIDE, ensure_ascii=False)}")
    time.sleep(4)
    ensure_hook(cdp)

    prev_hash = ""
    prev_req = 0
    reached = False
    for i in range(8):
        s = state(cdp)
        cap_before = ""
        action_tag = action(cdp)
        time.sleep(2)
        s2 = state(cdp)
        cap_after = take_shot(cdp, f"step_{i:02d}_after")
        net = cdp.eval("window.__atk_cap||{reqs:[],resps:[]}") or {"reqs": [], "resps": []}
        req_count = len(net.get("reqs", []))
        changed = (s2.get("hash") != prev_hash) or (req_count > prev_req)
        prev_hash = s2.get("hash")
        prev_req = req_count

        rec["steps"].append(
            {
                "i": i,
                "state_before": s,
                "action": action_tag,
                "state_after": s2,
                "assert_transition": changed,
                "req_count": req_count,
                "resp_count": len(net.get("resps", [])),
            }
        )
        shot_idx.append({"i": i, "before": cap_before, "after": cap_after, "action": action_tag})

        if not changed:
            err["items"].append(
                {
                    "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "stage": "guide/base",
                    "tag": action_tag.split(":")[0] if ":" in action_tag else action_tag,
                    "error": "动作后无状态变化（hash/请求均无变化）",
                    "fix": action_tag,
                }
            )
        if s2.get("hasYunbangban"):
            reached = True
            stop_ev = {"captured_at": time.strftime("%Y-%m-%d %H:%M:%S"), "url": s2.get("href"), "snapshot": s2}
            OUT_STOP.write_text(json.dumps(stop_ev, ensure_ascii=False, indent=2), encoding="utf-8")
            break

    net_final = cdp.eval("window.__atk_cap||{reqs:[],resps:[]}") or {"reqs": [], "resps": []}
    end_state = state(cdp)
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    rec["result"] = "stopped_at_yunbangban" if reached else "still_blocked_guide"
    rec["final_url"] = end_state.get("href")
    rec["final_hash"] = end_state.get("hash")
    rec["network"] = {"reqs": net_final.get("reqs", [])[-20:], "resps": net_final.get("resps", [])[-20:]}
    OUT_MAIN.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_ERR.write_text(json.dumps(err, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_SHOT_IDX.write_text(json.dumps(shot_idx, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text(
        "\n".join(
            [
                "# 02_4 Round3 CDP 攻坚",
                "",
                f"- started_at: {rec['started_at']}",
                f"- ended_at: {rec['ended_at']}",
                f"- result: {rec['result']}",
                f"- final_hash: {rec['final_hash']}",
                f"- screenshot_index: {OUT_SHOT_IDX.as_posix()}",
                f"- error_count: {len(err['items'])}",
            ]
        ),
        encoding="utf-8",
    )
    cdp.close()
    print(f"Saved: {OUT_MAIN}")
    print(f"Saved: {OUT_ERR}")
    print(f"Saved: {OUT_SHOT_IDX}")
    print(f"Saved: {OUT_MD}")
    if OUT_STOP.exists():
        print(f"Saved: {OUT_STOP}")


if __name__ == "__main__":
    main()

