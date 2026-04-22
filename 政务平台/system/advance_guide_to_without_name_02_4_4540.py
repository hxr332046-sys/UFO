#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/advance_guide_to_without_name_02_4_4540.json")
GUIDE = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=4540&marPrId=&marUniscId="


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "icpsp-web-pc" in (p.get("url") or "") and ":9087" in (p.get("url") or ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    for p in pages:
        if p.get("type") == "page":
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def main():
    ws_url, cur = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": [{"step": "S0_pick", "data": {"url": cur}}]}
    if not ws_url:
        rec["error"] = "no_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    ws = websocket.create_connection(ws_url, timeout=20)
    mid = 0

    def ev(expr, timeout=60000, awaitp=True):
        nonlocal mid
        mid += 1
        ws.send(
            json.dumps(
                {
                    "id": mid,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expr, "returnByValue": True, "awaitPromise": awaitp, "timeout": timeout},
                }
            )
        )
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == mid:
                return m.get("result", {}).get("result", {}).get("value")

    def snap(tag):
        return {
            "tag": tag,
            "data": ev(
                r"""(function(){
                  var txt=(document.body&&document.body.innerText)||'';
                  var btns=[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null).map(b=>({text:(b.textContent||'').replace(/\s+/g,' ').trim(),disabled:!!b.disabled,cls:(b.className||'').slice(0,40)}));
                  return {href:location.href,hash:location.hash,title:document.title,hasWithoutName:txt.indexOf('未申请')>=0||txt.indexOf('是否已申请名称')>=0,buttons:btns.slice(0,12),text:txt.slice(0,520)};
                })()""",
                20000,
            ),
        }

    rec["steps"].append({"step": "S1_nav_guide", "data": ev(f"location.href={json.dumps(GUIDE,ensure_ascii=False)}", 60000)})
    time.sleep(6)
    rec["steps"].append({"step": "S2_state", "data": snap("after_nav")["data"]})

    # 点击提示弹窗“确定”（资格提示）
    rec["steps"].append(
        {
            "step": "S3_confirm_tip",
            "data": ev(
                r"""(function(){
                  var btns=[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null);
                  var ok=btns.find(b=>((b.textContent||'').replace(/\s+/g,'').indexOf('确定')>=0));
                  if(ok){ok.click();return {clicked:true};}
                  return {clicked:false};
                })()""",
                15000,
            ),
        }
    )
    time.sleep(1)

    # 选择市场主体类型：个人独资企业
    rec["steps"].append(
        {
            "step": "S4_pick_enttype",
            "data": ev(
                r"""(function(){
                  function clean(s){return (s||'').replace(/\s+/g,'').trim();}
                  var candidates=[...document.querySelectorAll('span,div,li,a,label')].filter(e=>e.offsetParent!==null);
                  var hit=candidates.find(e=>clean(e.textContent)==='个人独资企业'||clean(e.textContent).indexOf('个人独资企业')>=0);
                  if(hit){hit.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));return {clicked:true,text:(hit.textContent||'').trim().slice(0,20)};}
                  return {clicked:false};
                })()""",
                20000,
            ),
        }
    )
    time.sleep(1)

    # 选择“未申请”（不走预保留号）
    rec["steps"].append(
        {
            "step": "S5_pick_unapplied",
            "data": ev(
                r"""(function(){
                  function clean(s){return (s||'').replace(/\s+/g,'').trim();}
                  var candidates=[...document.querySelectorAll('span,div,li,a,label')].filter(e=>e.offsetParent!==null);
                  var hit=candidates.find(e=>clean(e.textContent)==='未申请');
                  if(!hit){hit=candidates.find(e=>clean(e.textContent).indexOf('未申请')>=0);}
                  if(hit){hit.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));return {clicked:true,text:(hit.textContent||'').trim().slice(0,20)};}
                  return {clicked:false};
                })()""",
                20000,
            ),
        }
    )
    time.sleep(1)

    # 下一步
    rec["steps"].append(
        {
            "step": "S6_next",
            "data": ev(
                r"""(function(){
                  var btns=[...document.querySelectorAll('button,.el-button')].filter(b=>b.offsetParent!==null&&!b.disabled);
                  var n=btns.find(b=>((b.textContent||'').replace(/\s+/g,' ').trim()).indexOf('下一步')>=0);
                  if(n){n.click();return {clicked:true};}
                  return {clicked:false,btns:btns.map(b=>(b.textContent||'').trim()).slice(0,8)};
                })()""",
                20000,
            ),
        }
    )
    time.sleep(8)
    rec["steps"].append({"step": "S7_final", "data": snap("after_next")["data"]})

    ws.close()
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

