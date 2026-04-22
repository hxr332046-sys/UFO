#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从 portal 全部服务页起步，逐步普查“设立登记”页面框架。"""

import json
import time
from pathlib import Path

import requests
import websocket


OUT = Path("G:/UFO/政务平台/data/flow_stepwise_survey.json")


def find_ws(url_kw: str):
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and url_kw in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def find_any_zhjg_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url: str, expr: str, timeout: int = 12):
    ws = websocket.create_connection(ws_url, timeout=8)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "timeout": timeout * 1000},
            }
        )
    )
    ws.settimeout(timeout + 2)
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def snapshot(ws_url: str):
    expr = r"""(function(){
  var nameList=[];
  function walk(vm,d){
    if(!vm||d>8) return;
    var n=(vm.$options&&vm.$options.name)||'';
    if(n) nameList.push(n);
    (vm.$children||[]).forEach(function(c){walk(c,d+1);});
  }
  var app=document.getElementById('app');
  if(app&&app.__vue__) walk(app.__vue__,0);
  var uniq = Array.from(new Set(nameList));
  var btns=Array.from(document.querySelectorAll('button,.el-button')).filter(function(b){return b.offsetParent!==null;}).map(function(b){
    return {text:(b.textContent||'').trim().slice(0,30), disabled:!!b.disabled};
  });
  var cards=Array.from(document.querySelectorAll('[class*="card"],.server-item,.all-server-item,li,div'))
    .filter(function(e){return e.offsetParent!==null;})
    .map(function(e){return (e.textContent||'').trim().replace(/\s+/g,' ').slice(0,80);})
    .filter(Boolean)
    .slice(0,20);
  var errs=Array.from(document.querySelectorAll('.el-form-item__error')).map(function(e){return (e.textContent||'').trim();}).filter(Boolean);
  return {
    title:document.title,
    href:location.href,
    hash:location.hash,
    forms:document.querySelectorAll('.el-form-item').length,
    compNames:uniq.slice(0,40),
    buttons:btns.slice(0,20),
    errors:errs.slice(0,10),
    samples:cards
  };
})()"""
    return ev(ws_url, expr, timeout=15)


def click_entry(ws_url: str):
    expr = r"""(function(){
  // 优先找标题精确“设立登记”
  var exact = Array.from(document.querySelectorAll('*')).filter(function(e){
    if(e.offsetParent===null) return false;
    var t=(e.textContent||'').trim();
    return t==='设立登记';
  });
  for(var i=0;i<exact.length;i++){
    var el = exact[i];
    // 尝试自身、父级、祖父级点击
    var chain=[el, el.parentElement, el.parentElement?el.parentElement.parentElement:null];
    for(var k=0;k<chain.length;k++){
      if(!chain[k]) continue;
      try{
        chain[k].dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
        return {clicked:true,mode:'exact-chain',text:(el.textContent||'').trim().slice(0,30),tag:chain[k].tagName,cls:(chain[k].className||'').slice(0,60)};
      }catch(e){}
    }
  }

  // 兜底：找包含“设立登记/开始办理”且文本较短的节点
  var nodes=Array.from(document.querySelectorAll('a,button,div,li,span')).filter(function(e){
    if(e.offsetParent===null) return false;
    var t=(e.textContent||'').trim();
    return (t.indexOf('设立登记')>=0 || t.indexOf('开始办理')>=0 || t.indexOf('立即办理')>=0) && t.length<80;
  });
  for(var j=0;j<nodes.length;j++){
    var n=nodes[j];
    n.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
    return {clicked:true,mode:'fuzzy-short',text:(n.textContent||'').trim().slice(0,40),tag:n.tagName,cls:(n.className||'').slice(0,60)};
  }
  return {clicked:false,mode:'none'};
})()"""
    return ev(ws_url, expr, timeout=10)


def main():
    result = {"steps": []}

    ws, url = find_ws("portal.html#/index/page")
    if not ws:
        ws, url = find_any_zhjg_ws()
    if not ws:
        print("No zhjg page found.")
        return

    s1 = snapshot(ws)
    result["steps"].append({"step": "S1_portal_snapshot", "url": url, "data": s1})
    print("S1 portal:", s1.get("hash"), "forms=", s1.get("forms"))

    c = click_entry(ws)
    result["steps"].append({"step": "S2_click_establish", "data": c})
    print("S2 click:", c)
    time.sleep(4)

    # 点击后可能还是 portal hash，也可能进入 name-register/core 等页
    ws2, url2 = find_ws("name-register.html#/guide/base")
    if not ws2:
        ws2, url2 = find_ws("core.html#/flow/base")
    if not ws2:
        ws2, url2 = find_any_zhjg_ws()

    if not ws2:
        result["steps"].append({"step": "S3_after_click_snapshot", "url": None, "data": {"error": "no_target_page"}})
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    s3 = snapshot(ws2)
    result["steps"].append({"step": "S3_after_click_snapshot", "url": url2, "data": s3})
    print("S3 after-click:", s3.get("hash"), "forms=", s3.get("forms"))

    # 若未发生跳转，尝试路由方式进入设立登记
    if s3.get("hash", "").startswith("#/index/page"):
        route_try_expr = r"""(function(){
  var app=document.getElementById('app');
  if(!app||!app.__vue__||!app.__vue__.$router) return {ok:false,err:'no_router'};
  var r=app.__vue__.$router;
  var tries=['/index/enterprise/establish','/guide/base','/index/enterprise/enterprise-zone'];
  var out=[];
  for(var i=0;i<tries.length;i++){
    try{
      r.push(tries[i]);
      out.push({path:tries[i],ok:true,hash:location.hash});
    }catch(e){
      out.push({path:tries[i],ok:false,err:String(e).slice(0,120)});
    }
  }
  return {ok:true,out:out,hash:location.hash};
})()"""
        tr = ev(ws2, route_try_expr, timeout=10)
        result["steps"].append({"step": "S4_router_push_try", "data": tr})
        print("S4 router-try:", tr)
        time.sleep(3)

        s5 = snapshot(ws2)
        result["steps"].append({"step": "S5_after_router_snapshot", "url": url2, "data": s5})
        print("S5 after-router:", s5.get("hash"), "forms=", s5.get("forms"))

        # 若已到 enterprise-zone，尝试点击“开始办理/设立登记”继续
        if "enterprise-zone" in (s5.get("hash") or ""):
            click_next_expr = r"""(function(){
  var btns=Array.from(document.querySelectorAll('button,.el-button,a,div')).filter(function(e){return e.offsetParent!==null;});
  for(var i=0;i<btns.length;i++){
    var t=(btns[i].textContent||'').trim();
    if(/开始办理|设立登记|立即办理/.test(t)){
      btns[i].dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
      return {clicked:true,text:t.slice(0,40),tag:btns[i].tagName,cls:(btns[i].className||'').slice(0,60)};
    }
  }
  return {clicked:false};
})()"""
            c2 = ev(ws2, click_next_expr, timeout=10)
            result["steps"].append({"step": "S6_click_start_handle", "data": c2})
            print("S6 click-start:", c2)
            time.sleep(4)

            s7 = snapshot(ws2)
            result["steps"].append({"step": "S7_after_start_snapshot", "url": url2, "data": s7})
            print("S7 after-start:", s7.get("hash"), "forms=", s7.get("forms"))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

