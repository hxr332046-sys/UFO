#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
第一入口：6087 TopIP 门户 → 点击「企业开办一件事」，XHR/fetch 抓 /icpsp-api/ 与 TopIP 相关请求。
保全 SSO/跳转链上下文，不单跳 9087。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/packet_chain_topip_6087_qiyekaiban.json")

ENTRY_URL = (
    "https://zhjg.scjdglj.gxzf.gov.cn:6087/TopIP/web/web-portal.html#/index/page"
)

HOOK_JS = r"""(function(){
  window.__ufo_cap = window.__ufo_cap || {installed:false,items:[]};
  function pushOne(x){ try{ x.ts=Date.now(); window.__ufo_cap.items.push(x);
    if(window.__ufo_cap.items.length>400) window.__ufo_cap.items.shift(); }catch(e){} }
  if(!window.__ufo_cap.installed){
    var XO=XMLHttpRequest.prototype.open, XS=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open=function(m,u){ this.__ufo={m:m,u:u}; return XO.apply(this,arguments); };
    XMLHttpRequest.prototype.send=function(body){
      var self=this, u=(self.__ufo&&self.__ufo.u)||'';
      var full=String(u);
      if(full.indexOf('/icpsp-api/')>=0 || full.indexOf('6087')>=0 || full.indexOf('9087')>=0 || full.indexOf('TopIP')>=0){
        pushOne({t:'xhr',m:(self.__ufo&&self.__ufo.m)||'',u:full.slice(0,800),body:String(body||'').slice(0,30000)});
        self.addEventListener('loadend',function(){
          pushOne({t:'xhr_end',u:full.slice(0,800),status:self.status,resp:String(self.responseText||'').slice(0,30000)});
        });
      }
      return XS.apply(this,arguments);
    };
    var OF=window.fetch;
    if(typeof OF==='function'){
      window.fetch=function(input,init){
        try{
          var u=(typeof input==='string')?input:(input&&input.url)||'';
          var full=String(u);
          if(full.indexOf('/icpsp-api/')>=0 || full.indexOf('6087')>=0 || full.indexOf('9087')>=0){
            var m=(init&&init.method)||'GET';
            var b=(init&&init.body)?String(init.body).slice(0,30000):'';
            pushOne({t:'fetch',m:m,u:full.slice(0,800),body:b});
            return OF.apply(this,arguments).then(function(res){
              try{
                return res.clone().text().then(function(txt){
                  pushOne({t:'fetch_end',u:full.slice(0,800),status:res.status,resp:String(txt||'').slice(0,30000)});
                  return res;
                });
              }catch(e){ return res; }
            });
          }
        }catch(e){}
        return OF.apply(this,arguments);
      };
    }
    window.__ufo_cap.installed=true;
  }
  window.__ufo_cap.items=[];
  return {ok:true};
})()"""

CLICK_QIYEKAIBAN_VIA_A = r"""(function(){
  function clean(s){ return (s||'').replace(/\s+/g,' ').trim(); }
  var exact='企业开办一件事';
  var links=[...document.querySelectorAll('a[href]')].filter(function(a){return a.offsetParent!==null;});
  var ahit=links.find(function(a){
    var t=clean(a.textContent);
    return t===exact || (t.indexOf(exact)>=0 && t.length<exact.length+10);
  });
  if(ahit){
    ahit.scrollIntoView({block:'center',inline:'nearest'});
    ahit.click();
    return {ok:true,mode:'anchor',href:ahit.href,text:clean(ahit.textContent).slice(0,40)};
  }
  return {ok:false,mode:'anchor'};
})()"""

CLICK_QIYEKAIBAN = r"""(function(){
  function clean(s){ return (s||'').replace(/\s+/g,' ').trim(); }
  function fire(el){
    ['pointerdown','mousedown','mouseup','click'].forEach(function(tp){
      el.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window}));
    });
  }
  var exact='企业开办一件事';
  var cand=[...document.querySelectorAll('*')].filter(function(e){
    if(!e.offsetParent) return false;
    return clean(e.textContent)===exact;
  });
  if(!cand.length) return {ok:false,err:'no_exact_text'};
  cand.sort(function(a,b){
    var ra=a.getBoundingClientRect(), rb=b.getBoundingClientRect();
    return (ra.width*ra.height)-(rb.width*rb.height);
  });
  var hit=cand[0];
  hit.scrollIntoView({block:'center',inline:'nearest'});
  var r=hit.getBoundingClientRect();
  fire(hit);
  try{ hit.click(); }catch(e1){}
  var x=r.left+Math.min(r.width/2,80), y=r.top+Math.min(r.height/2,40);
  var under=document.elementFromPoint(x,y);
  if(under && under!==hit){ fire(under); try{ under.click(); }catch(e2){} }
  return {ok:true,tag:hit.tagName,area:Math.round(r.width*r.height),x:Math.round(x),y:Math.round(y)};
})()"""

WAIT_PORTAL_READY = r"""(function(){
  var t=(document.body&&document.body.innerText)||'';
  var on6087=location.href.indexOf(':6087')>=0 && location.href.indexOf('TopIP')>=0;
  var hasTile=t.indexOf('企业开办一件事')>=0;
  var hasTitle=t.indexOf('市场监管准入')>=0;
  return {ok:on6087&&hasTile&&hasTitle,href:location.href};
})()"""


def list_pages(port: int = 9225) -> List[Dict[str, Any]]:
    return requests.get(f"http://127.0.0.1:{port}/json", timeout=8).json()


def score_target(url: str) -> int:
    if not url or url.startswith("devtools://"):
        return -1000
    s = 0
    if "zhjg.scjdglj.gxzf.gov.cn" in url:
        s += 50
    if ":6087" in url and "TopIP" in url:
        s += 120
    if "web-portal.html" in url:
        s += 40
    if ":9087" in url:
        s += 30
    return s


def pick_ws(port: int = 9225) -> Tuple[Optional[str], str, List[str]]:
    pages = [p for p in list_pages(port) if p.get("type") == "page"]
    ranked = sorted(pages, key=lambda p: -score_target(p.get("url") or ""))
    urls = [p.get("url") or "" for p in ranked[:8]]
    if not ranked:
        return None, "", urls
    p = ranked[0]
    return p.get("webSocketDebuggerUrl"), p.get("url") or "", urls


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=25)
        self.ws.settimeout(2.0)
        self.i = 1

    def call(self, method: str, params: Optional[dict] = None, timeout: float = 25):
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

    def ev(self, expr: str, timeout_ms: int = 120000):
        m = self.call(
            "Runtime.evaluate",
            {
                "expression": expr,
                "returnByValue": True,
                "awaitPromise": True,
                "timeout": timeout_ms,
            },
            timeout=28,
        )
        return ((m.get("result") or {}).get("result") or {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def snap(c: CDP) -> Any:
    return c.ev(
        r"""(function(){
          var t=(document.body&&document.body.innerText)||'';
          return {
            href:location.href,
            title:document.title,
            snippet:t.replace(/\s+/g,' ').trim().slice(0,400)
          };
        })()"""
    )


def dump_cap(c: CDP) -> Any:
    return c.ev(
        r"""(function(){
          var x=window.__ufo_cap||{items:[]};
          return {count:(x.items||[]).length,items:(x.items||[])};
        })()"""
    )


def list_page_urls(port: int = 9225) -> List[str]:
    try:
        return [
            (p.get("url") or "")
            for p in list_pages(port)
            if p.get("type") == "page" and not (p.get("url") or "").startswith("devtools://")
        ]
    except Exception:
        return []


def main():
    ws_url, cur, candidates = pick_ws(9225)
    rec: Dict[str, Any] = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "entry_url": ENTRY_URL,
        "cdp_page_before": cur,
        "cdp_candidate_urls": candidates,
        "steps": [],
    }
    if not ws_url:
        rec["error"] = "no_cdp_9225"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    c = CDP(ws_url)
    err: Optional[str] = None
    try:
        rec["cdp_urls_before_run"] = list_page_urls(9225)
        rec["steps"].append({"step": "nav_entry", "data": ENTRY_URL})
        c.ev(f"location.href={json.dumps(ENTRY_URL, ensure_ascii=False)}")
        time.sleep(6)
        rec["steps"].append({"step": "snap_after_nav", "data": snap(c)})
        wait_log = []
        for _ in range(90):
            w = c.ev(WAIT_PORTAL_READY)
            wait_log.append(w)
            if isinstance(w, dict) and w.get("ok"):
                break
            time.sleep(0.5)
        rec["steps"].append({"step": "wait_portal_ready", "polls": wait_log[-5:]})
        rec["steps"].append({"step": "install_hook", "data": c.ev(HOOK_JS)})
        time.sleep(2)
        rec["steps"].append({"step": "try_vue_data_nav", "data": c.ev(
            r"""(function(){
              var found=null;
              function scanVm(vm,d){
                if(!vm||d>28||found) return;
                var data=vm.$data||{};
                var keys=['menuList','cardList','featureList','bannerList','teseList','list','items','childrenList','children','quickList'];
                for(var ki=0;ki<keys.length;ki++){
                  var arr=data[keys[ki]];
                  if(!Array.isArray(arr)) continue;
                  for(var j=0;j<arr.length;j++){
                    var it=arr[j];
                    if(!it||typeof it!=='object') continue;
                    var title=(it.title||it.name||it.text||it.label||it.businessName||'')+'';
                    if(title.indexOf('企业开办一件事')>=0){ found={it:it,key:keys[ki],vm:vm}; return; }
                  }
                }
                var ch=vm.$children||[];
                for(var c=0;c<ch.length;c++) scanVm(ch[c],d+1);
              }
              var root=document.getElementById('app')&&document.getElementById('app').__vue__;
              scanVm(root,0);
              if(!found) return {ok:false,err:'not_in_vm_lists'};
              var it=found.it;
              var p=it.path||it.route||it.url||it.link||it.href||it.to||'';
              p=(p||'')+'';
              if(p.indexOf('http')===0){ location.href=p; return {ok:true,mode:'location',p:p.slice(0,200),keys:Object.keys(it).slice(0,20)}; }
              if(p && p.indexOf('#')===0){ location.hash=p.replace(/^#/,'#'); return {ok:true,mode:'hash',p:p.slice(0,200)}; }
              if(p && p.charAt(0)==='/'){
                if(window.$router) window.$router.push(p);
                else location.hash='#'+p.replace(/^\//,'');
                return {ok:true,mode:'push',p:p.slice(0,200)};
              }
              return {ok:true,mode:'found_no_path',keys:Object.keys(it),sample:JSON.stringify(it).slice(0,400)};
            })()"""
        )})
        time.sleep(5)
        rec["steps"].append({"step": "snap_after_vue_data_nav", "data": snap(c)})
        rec["steps"].append({"step": "probe_tile_links", "data": c.ev(
            r"""(function(){
              function clean(s){ return (s||'').replace(/\s+/g,' ').trim(); }
              return [...document.querySelectorAll('a[href]')].filter(function(a){return a.offsetParent!==null;})
                .filter(function(a){ return clean(a.textContent).indexOf('企业开办')>=0; })
                .map(function(a){ return {href:a.href.slice(0,200),text:clean(a.textContent).slice(0,50)}; })
                .slice(0,12);
            })()"""
        )})
        click_r = None
        for attempt in range(3):
            click_r = c.ev(CLICK_QIYEKAIBAN_VIA_A)
            rec["steps"].append({"step": f"click_via_a_try_{attempt}", "data": click_r})
            if isinstance(click_r, dict) and click_r.get("ok"):
                break
            click_r = c.ev(CLICK_QIYEKAIBAN)
            rec["steps"].append({"step": f"click_qiyekaiban_try_{attempt}", "data": click_r})
            if isinstance(click_r, dict) and click_r.get("ok"):
                break
            time.sleep(2)
        time.sleep(12)
        rec["steps"].append({"step": "cdp_urls_after_click", "data": list_page_urls(9225)})
        rec["steps"].append({"step": "install_hook_post_click", "data": c.ev(HOOK_JS)})
        time.sleep(6)
        rec["steps"].append({"step": "snap_after_click", "data": snap(c)})
        rec["steps"].append({"step": "vue_click_probe", "data": c.ev(
            r"""(function(){
              var exact='企业开办一件事';
              function clean(s){ return (s||'').replace(/\s+/g,' ').trim(); }
              var cand=[...document.querySelectorAll('*')].filter(function(e){
                return e.offsetParent && clean(e.textContent)===exact;
              });
              if(!cand.length) return {ok:false,err:'no_node'};
              cand.sort(function(a,b){
                var ra=a.getBoundingClientRect(), rb=b.getBoundingClientRect();
                return (ra.width*ra.height)-(rb.width*rb.height);
              });
              var el=cand[0];
              for(var up=0;up<8;up++){
                var vm=el.__vue__;
                if(vm){
                  var tried=[];
                  if(vm.$listeners&&typeof vm.$listeners.click==='function'){
                    try{ vm.$listeners.click(); tried.push('listeners.click'); }catch(e){ tried.push('listeners.err:'+e); }
                  }
                  if(typeof vm.handleClick==='function'){
                    try{ vm.handleClick(); tried.push('handleClick'); }catch(e){ tried.push('handleClick.err'); }
                  }
                  if(typeof vm.onClick==='function'){
                    try{ vm.onClick(); tried.push('onClick'); }catch(e){}
                  }
                  if(tried.length) return {ok:true,up:up,tried:tried};
                }
                if(!el.parentElement) break;
                el=el.parentElement;
              }
              return {ok:false,err:'no_vue_handler'};
            })()"""
        )})
        time.sleep(5)
        rec["steps"].append({"step": "snap_after_vue_probe", "data": snap(c)})
        rec["steps"].append({"step": "captured", "data": dump_cap(c)})
    except Exception as e:
        err = repr(e)
        rec["steps"].append({"step": "error", "data": err})
    finally:
        rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if err:
            rec["run_error"] = err
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        try:
            c.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
