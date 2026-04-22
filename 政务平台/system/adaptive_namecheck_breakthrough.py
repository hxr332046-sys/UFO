#!/usr/bin/env python
# -*- coding: utf-8 -*-
import base64
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/adaptive_namecheck_breakthrough.json")
SHOT_ROOT = Path("G:/UFO/政务平台/dashboard/data/records/adaptive_namecheck_shots")
GUIDE_URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=4540&marPrId=&marUniscId="
CORE_URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html#/flow/base/name-check-info"
MYSPACE_URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/company/my-space/space-index"


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        u = p.get("url", "")
        if p.get("type") == "page" and ":9087" in u and "icpsp-web-pc" in u:
            return p["webSocketDebuggerUrl"], u
    for p in pages:
        if p.get("type") == "page":
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, ""


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=20)
        self.ws.settimeout(1.0)
        self.i = 1

    def call(self, method, params=None, timeout=12):
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
        return {"error": {"message": f"timeout:{method}"}}

    def ev(self, expr, timeout=70000):
        r = self.call(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout},
            timeout=15,
        )
        return (((r or {}).get("result") or {}).get("value"))

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def shot(cdp: CDP, shot_dir: Path, tag: str):
    shot_dir.mkdir(parents=True, exist_ok=True)
    p = shot_dir / f"{tag}.png"
    # Retry screenshot once to reduce transient blank/missing capture.
    for _ in range(2):
        data = cdp.call("Page.captureScreenshot", {"format": "png"}, timeout=15).get("data", "")
        if data:
            p.write_bytes(base64.b64decode(data))
            break
        time.sleep(0.3)
    return {"path": p.as_posix(), "exists": p.exists()}


def read_state(cdp: CDP):
    return cdp.ev(
        r"""(function(){
          function clean(s){return String(s||'').replace(/\s+/g,' ').trim();}
          var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>clean(e.textContent)).filter(Boolean);
          var txt=(document.body.innerText||'');
          return {
            href:location.href,
            hash:location.hash,
            errors:errs.slice(0,10),
            hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0,
            hasNameCheck:location.href.indexOf('name-check-info')>=0,
            hasGuide:location.href.indexOf('guide/base')>=0,
            hasMySpace:location.href.indexOf('my-space/space-index')>=0 || (txt.indexOf('我的办件')>=0 && txt.indexOf('继续办理')>=0),
            textHint:clean(txt).slice(0,180)
          };
        })()"""
    )


def action_nav_guide(cdp: CDP):
    return cdp.ev(f"location.href={json.dumps(GUIDE_URL, ensure_ascii=False)}")


def action_nav_core(cdp: CDP):
    return cdp.ev(f"location.href={json.dumps(CORE_URL, ensure_ascii=False)}")


def action_nav_my_space(cdp: CDP):
    return cdp.ev(f"location.href={json.dumps(MYSPACE_URL, ensure_ascii=False)}")


def action_continue_route(cdp: CDP):
    return cdp.ev(
        r"""(async function(){
          function clean(s){return String(s||'').replace(/\s+/g,' ').trim();}
          function buildRouteUrl(route){
            if(!route||!route.project||!route.path) return '';
            var base='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/'+route.project+'.html#'+route.path;
            var p=route.params||{};
            var q=Object.keys(p).map(function(k){return encodeURIComponent(k)+'='+encodeURIComponent(String(p[k]===undefined?'':p[k]));}).join('&');
            return q ? (base+'?'+q) : base;
          }
          window.__route_cap = {resps:[]};
          var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
          XMLHttpRequest.prototype.open=function(m,u){this.__u=u; return oo.apply(this,arguments);};
          XMLHttpRequest.prototype.send=function(b){
            var self=this; self.addEventListener('loadend', function(){
              var t=String(self.responseText||'');
              if((self.__u||'').indexOf('/mattermanager/matters/operate')>=0 || t.indexOf('"route"')>=0){
                window.__route_cap.resps.push({u:String(self.__u||''),s:self.status,t:t.slice(0,5000)});
              }
            });
            return os.apply(this,arguments);
          };
          function parseRouteFromText(t){
            if(!t) return null;
            try{
              var j=JSON.parse(t);
              var d=(j&&j.data)||{};
              if(d && d.route) return d.route;
              if(d && d.data && d.data.route) return d.data.route;
            }catch(e){}
            var m = String(t).match(/"route"\s*:\s*(\{[\s\S]*?\})\s*[,\}]/);
            if(m && m[1]){
              try{return JSON.parse(m[1]);}catch(e){}
            }
            return null;
          }
          try{
            var btns=[].slice.call(document.querySelectorAll('button,.el-button')).filter(function(b){
              return b.offsetParent!==null && !b.disabled && clean(b.textContent).indexOf('继续办理')>=0;
            });
            if(!btns.length){ return {ok:false,msg:'no_continue_button'}; }
            var pickedRoute=null, pickedUrl='', pickedIdx=-1;
            var attempts=[];
            for(var bi=0; bi<btns.length; bi++){
              var before = window.__route_cap.resps.length;
              btns[bi].click();
              await new Promise(function(r){setTimeout(r,2200);});
              var after = window.__route_cap.resps.length;
              var newResps = window.__route_cap.resps.slice(before, after);
              var r = null;
              for(var k=0;k<newResps.length;k++){
                r = parseRouteFromText(newResps[k].t||'');
                if(r) break;
              }
              attempts.push({
                idx: bi,
                captures: newResps.length,
                hasRoute: !!r,
                sample: (newResps[0] && String(newResps[0].t||'').slice(0,220)) || ''
              });
              if(r){
                pickedRoute = r;
                pickedIdx = bi;
                pickedUrl = buildRouteUrl(r);
                break;
              }
            }
            var route = pickedRoute;
            if(route){
              if(pickedUrl) location.href=pickedUrl;
              return {ok:true,route:route,url:pickedUrl,buttonIdx:pickedIdx,attempts:attempts};
            }
            return {
              ok:false,
              msg:'no_route_captured',
              captures:window.__route_cap.resps.length,
              attempts:attempts,
              samples:window.__route_cap.resps.slice(0,2).map(function(x){
                return {u:x.u,s:x.s,t:String(x.t||'').slice(0,800)};
              })
            };
          } finally {
            XMLHttpRequest.prototype.open=oo;
            XMLHttpRequest.prototype.send=os;
          }
        })()""",
        timeout=120000,
    )


def action_fix_org(cdp: CDP):
    return cdp.ev(
        r"""(async function(){
          function walk(vm,d,p){if(!vm||d>25)return null;if(p(vm))return vm;for(var c of (vm.$children||[])){var r=walk(c,d+1,p);if(r)return r;}return null;}
          var app=document.getElementById('app'), root=app&&app.__vue__;
          var idx=walk(root,0,function(v){var n=(v.$options&&v.$options.name)||'';return n==='index'&&v.$parent&&v.$parent.$options&&v.$parent.$options.name==='name-check-info';});
          var org=walk(root,0,function(v){return (v.$options&&v.$options.name)==='organization-select';});
          if(!idx||!org) return {ok:false,msg:'no_idx_or_org'};
          var first=(org.groupList||[])[0]||{};
          var code=String(first.code||'802');
          var label=String(first.name||'院');
          idx.$set(idx.formInfo,'organize',code);
          idx.$set(idx.formInfo,'organizeName',label);
          org.formInline=org.formInline||{};
          org.$set(org.formInline,'groupval',code);
          org.$set(org.formInline,'radio1',code);
          org.$set(org,'searchvalue',label);
          org.$set(org,'zhongjainzhi',label);
          var save=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').replace(/\s+/g,'').indexOf('保存并下一步')>=0&&!x.disabled);
          if(save) save.click();
          return {ok:true,code:code,label:label};
        })()"""
    )


def action_fix_industry(cdp: CDP):
    return cdp.ev(
        r"""(function(){
          function clean(s){return String(s||'').replace(/\s+/g,' ').trim();}
          function setInput(inp,val){
            var setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
            setter.call(inp,val);
            inp.dispatchEvent(new Event('input',{bubbles:true}));
            inp.dispatchEvent(new Event('change',{bubbles:true}));
          }
          var items=[...document.querySelectorAll('.el-form-item')];
          var target=items.find(it=>{
            var lb=it.querySelector('.el-form-item__label');
            return lb && clean(lb.textContent).indexOf('行业')>=0;
          });
          if(!target) return {ok:false,msg:'no_industry_item'};
          var inp=target.querySelector('input.el-input__inner');
          if(!inp) return {ok:false,msg:'no_industry_input'};
          inp.click();
          setInput(inp,'批发');
          return {ok:true,msg:'industry_typed'};
        })()"""
    )


def action_submit_once(cdp: CDP):
    return cdp.ev(
        r"""(function(){
          var ok=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').replace(/\s+/g,'').indexOf('确定')>=0&&!x.disabled);
          if(ok) ok.click();
          var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').replace(/\s+/g,'').indexOf('保存并下一步')>=0&&!x.disabled);
          if(b){b.click(); return {ok:true,clicked:'save_next'};}
          return {ok:false,msg:'no_save_button'};
        })()"""
    )


def choose_action(state, used_actions):
    # Never repeat the same action under the same state signature.
    candidates = []
    if state.get("hasMySpace"):
        candidates = ["continue_route", "nav_core", "nav_guide"]
    elif state.get("hasGuide"):
        candidates = ["nav_core", "submit_once"]
    elif state.get("hasNameCheck"):
        errs = state.get("errors") or []
        if any(("企业类型不能为空" in e) or ("名称登记传参无效" in e) for e in errs):
            candidates = ["nav_my_space", "nav_guide", "submit_once"]
        elif "请选择组织形式" in errs:
            candidates = ["fix_org", "fix_industry", "submit_once", "nav_guide"]
        elif any("行业" in e for e in errs) or "主营行业不能为空" in (state.get("textHint") or ""):
            candidates = ["fix_industry", "submit_once", "fix_org", "nav_guide"]
        else:
            candidates = ["submit_once", "fix_industry", "fix_org", "nav_guide"]
    else:
        candidates = ["nav_core", "nav_guide", "submit_once"]
    for c in candidates:
        if c not in used_actions:
            return c
    return None


def run_action(cdp, name):
    if name == "nav_guide":
        return action_nav_guide(cdp)
    if name == "nav_core":
        return action_nav_core(cdp)
    if name == "nav_my_space":
        return action_nav_my_space(cdp)
    if name == "continue_route":
        return action_continue_route(cdp)
    if name == "fix_org":
        return action_fix_org(cdp)
    if name == "fix_industry":
        return action_fix_industry(cdp)
    if name == "submit_once":
        return action_submit_once(cdp)
    return {"ok": False, "msg": f"unknown_action:{name}"}


def main():
    ws_url, start_url = pick_ws()
    run_id = time.strftime("%Y%m%d_%H%M%S")
    shot_dir = SHOT_ROOT / run_id
    rec = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "run_id": run_id,
        "shot_dir": shot_dir.as_posix(),
        "start_url": start_url,
        "steps": [],
    }
    if not ws_url:
        rec["result"] = "no_ws"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    cdp = CDP(ws_url)
    cdp.call("Page.enable", {})

    state_action_history = {}
    for i in range(8):
        s0 = read_state(cdp) or {}
        sig = f"{s0.get('hash','')}|{'|'.join(s0.get('errors') or [])}|{s0.get('textHint','')[:50]}"
        used = state_action_history.get(sig, [])

        before_shot = shot(cdp, shot_dir, f"step_{i:02d}_before")
        action = choose_action(s0, used)
        if not action:
            rec["steps"].append(
                {"i": i, "state": s0, "action": "none", "reason": "all_actions_used_for_state", "shot_before": before_shot}
            )
            break

        state_action_history.setdefault(sig, []).append(action)
        out = run_action(cdp, action)
        time.sleep(5)
        s1 = read_state(cdp) or {}
        after_shot = shot(cdp, shot_dir, f"step_{i:02d}_after")

        rec["steps"].append(
            {
                "i": i,
                "sig": sig,
                "action": action,
                "action_out": out,
                "state_before": s0,
                "state_after": s1,
                "shot_before": before_shot,
                "shot_after": after_shot,
            }
        )

        if s1.get("hasYunbangban"):
            rec["result"] = "reached_yunbangban"
            break

    if "result" not in rec:
        final_state = read_state(cdp) or {}
        rec["result"] = "not_reached"
        rec["final_state"] = final_state

    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    cdp.close()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

