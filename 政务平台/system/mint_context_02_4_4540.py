#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
目标：在当前登录态下，强制拿到可用的 flow 上下文（nameId/busiId/itemId）
用于打破 NameCheckRepeat A0002（通常由 busiId/nameId/itemId 缺失导致）。

策略（尽量不依赖页面初始位置）：
- 选中最相关页签；若不在 9087，则跳转到企业专区入口（busiType=02_4）
- 企业专区点击“开始办理” → without-name.toSelectName() → select-prise
- 从 select-prise 的数据里抽取 nameId（优先已存在的列表项）；调用 startSheli({nameId,entType:4540})
- 若未跳转 core，则尝试 getHandleBusiness({entType:4540,nameId}) 触发动态路由/跳转
- 最后抓取 location + localStorage + （若已进入 core）flow-control.params.flowData
"""

import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/mint_context_02_4_4540.json")
ROUND2_EVID = Path("G:/UFO/政务平台/dashboard/data/records/round2_submit_success_evidence.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    # 优先 9087 icpsp
    ranked = []
    for p in pages:
        if p.get("type") != "page":
            continue
        u = p.get("url", "") or ""
        s = 0
        if "zhjg.scjdglj.gxzf.gov.cn" in u:
            s += 10
        if ":9087" in u:
            s += 100
        if "icpsp-web-pc" in u:
            s += 50
        if "core.html" in u or "name-register" in u:
            s += 30
        if "enterprise-zone" in u:
            s += 20
        ranked.append((s, p))
    ranked.sort(key=lambda x: -x[0])
    if not ranked:
        return None, None
    return ranked[0][1]["webSocketDebuggerUrl"], ranked[0][1].get("url", "")


def ev(ws, expr, timeout_ms=30000, msg_id=1, await_promise=True):
    ws.send(
        json.dumps(
            {
                "id": msg_id,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": expr,
                    "returnByValue": True,
                    "awaitPromise": await_promise,
                    "timeout": timeout_ms,
                },
            }
        )
    )
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == msg_id:
            return m.get("result", {}).get("result", {}).get("value")


def main():
    rec = {"steps": []}
    ws_url, url0 = pick_ws()
    rec["steps"].append({"step": "S0_pick", "data": {"url": url0}})
    if not ws_url:
        rec["error"] = "no_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    ws = websocket.create_connection(ws_url, timeout=30)
    mid = 0

    def e(js, timeout_ms=30000):
        nonlocal mid
        mid += 1
        return ev(ws, js, timeout_ms=timeout_ms, msg_id=mid)

    # 1) 若不在 9087，则整页跳到企业专区入口
    entry = (
        "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"
        "#/index/enterprise/enterprise-zone?fromProject=portal&fromPage=%2Flogin%2FauthPage&busiType=02_4&merge=Y"
    )
    cur = e("location.href")
    if isinstance(cur, str) and (":9087" not in cur or "icpsp-web-pc" not in cur):
        rec["steps"].append({"step": "S1_nav_entry", "data": e(f"location.href={json.dumps(entry,ensure_ascii=False)}", timeout_ms=60000)})
        time.sleep(6)

    # 2) 尽量进入 select-prise
    rec["steps"].append({"step": "S2_hash_before", "data": e("({href:location.href,hash:location.hash,title:document.title})")})

    # push enterprise-zone（如果 vue router 可用）
    e(
        r"""(function(){
          var app=document.getElementById('app');
          if(app&&app.__vue__&&app.__vue__.$router){
            try{app.__vue__.$router.push('/index/enterprise/enterprise-zone');}catch(e){}
            return {ok:true};
          }
          return {ok:false};
        })()""",
        timeout_ms=15000,
    )
    time.sleep(3)

    # 点击“开始办理”
    rec["steps"].append(
        {
            "step": "S3_click_start",
            "data": e(
                r"""(function(){
                  var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').includes('开始办理'));
                  if(b){b.click();return {ok:true,text:(b.textContent||'').trim()};}
                  return {ok:false,topBtns:[...document.querySelectorAll('button,.el-button')].slice(0,6).map(x=>(x.textContent||'').trim())};
                })()"""
            ),
        }
    )
    time.sleep(6)

    # 若在 without-name，调用 toSelectName
    rec["steps"].append(
        {
            "step": "S4_toSelectName",
            "data": e(
                r"""(function(){
                  var vm=document.getElementById('app')?.__vue__;
                  function find(vm,name,d){if(!vm||d>15)return null; if(vm.$options?.name===name)return vm; for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],name,d+1); if(r)return r;} return null;}
                  var wn=find(vm,'without-name',0);
                  if(wn&&typeof wn.toSelectName==='function'){wn.toSelectName();return {called:true};}
                  return {called:false,hash:location.hash};
                })()"""
            ),
        }
    )
    time.sleep(4)

    rec["steps"].append({"step": "S5_hash_after_select", "data": e("({href:location.href,hash:location.hash})")})

    # 3) 触发 select-prise 拉取历史名称列表（priseList）
    rec["steps"].append(
        {
            "step": "S6_call_getData",
            "data": e(
                r"""(function(){
                  var vm=document.getElementById('app')?.__vue__;
                  function find(vm,name,d){if(!vm||d>15)return null; if(vm.$options?.name===name)return vm; for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],name,d+1); if(r)return r;} return null;}
                  var sp=find(vm,'select-prise',0);
                  if(!sp) return {error:'no_select_prise'};
                  try{
                    if(typeof sp.getData==='function'){ sp.getData(); return {called:'getData'}; }
                    if(typeof sp.initData==='function'){ sp.initData(); return {called:'initData'}; }
                    if(typeof sp.refreshList==='function'){ sp.refreshList(); return {called:'refreshList'}; }
                  }catch(e){ return {error:String(e)}; }
                  return {error:'no_method'};
                })()"""
            ),
        }
    )
    time.sleep(6)

    # 4) 提取 nameId：优先 select-prise 数据里已有的 nameId/priseList
    name_info = e(
        r"""(function(){
          var vm=document.getElementById('app')?.__vue__;
          function find(vm,name,d){if(!vm||d>15)return null; if(vm.$options?.name===name)return vm; for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],name,d+1); if(r)return r;} return null;}
          var sp=find(vm,'select-prise',0);
          if(!sp) return {error:'no_select_prise',hash:location.hash};
          var data=sp.$data||{};
          var nid=data.nameId || data.dataInfo?.nameId || data.dataInfo?.nId || data.dataInfo?.id || '';
          var pl=data.priseList || [];
          // 常见字段：nameId / nId / id
          var nid2='';
          if(!nid && Array.isArray(pl) && pl.length){
            var p=pl[0]||{};
            nid2=p.nameId||p.nId||p.id||'';
          }
          return {
            hasList:Array.isArray(pl),
            listLen:Array.isArray(pl)?pl.length:0,
            picked:{name:pl&&pl[0]?String(pl[0].name||pl[0].entName||'').slice(0,40):'', raw:pl&&pl[0]?JSON.stringify(pl[0]).slice(0,260):''},
            nameId:nid||nid2||'',
            keys:Object.keys(data).slice(0,20)
          };
        })()"""
    )
    rec["steps"].append({"step": "S7_extract_nameId", "data": name_info})
    nid = (name_info or {}).get("nameId") if isinstance(name_info, dict) else ""

    # 4.5) 如果没有历史 nameId，尝试使用已知成功证据里的 nameId（有机会直接复用旧上下文）
    if not nid and ROUND2_EVID.exists():
        try:
            evid = json.loads(ROUND2_EVID.read_text(encoding="utf-8"))
            nid = ((evid.get("snapshot") or {}).get("flowData") or {}).get("nameId") or ""
        except Exception:
            nid = ""
        rec["steps"].append({"step": "S7b_fallback_nameId_from_round2", "data": {"nameId": nid}})

    # 5) 调 startSheli / getHandleBusiness（entType=4540）
    if nid:
        rec["steps"].append(
            {
                "step": "S8_call_startSheli",
                "data": e(
                    rf"""(function(){{
                      var vm=document.getElementById('app')?.__vue__;
                      function find(vm,name,d){{if(!vm||d>15)return null; if(vm.$options?.name===name)return vm; for(var i=0;i<(vm.$children||[]).length;i++){{var r=find(vm.$children[i],name,d+1); if(r)return r;}} return null;}}
                      var sp=find(vm,'select-prise',0);
                      if(sp&&typeof sp.startSheli==='function'){{ sp.startSheli({{nameId:'{nid}',entType:'4540'}}); return {{ok:true}}; }}
                      return {{ok:false}};
                    }})()"""
                ),
            }
        )
        time.sleep(10)

        rec["steps"].append({"step": "S8_after_startSheli", "data": e("({href:location.href,hash:location.hash,title:document.title})")})

        # 若还没进 core，尝试 getHandleBusiness
        rec["steps"].append(
            {
                "step": "S9_call_getHandleBusiness",
                "data": e(
                    rf"""(function(){{
                      var vm=document.getElementById('app')?.__vue__;
                      function findAny(vm,d){{if(!vm||d>15)return null; if(vm.getHandleBusiness)return vm; for(var i=0;i<(vm.$children||[]).length;i++){{var r=findAny(vm.$children[i],d+1); if(r)return r;}} return null;}}
                      var x=findAny(vm,0);
                      if(x&&typeof x.getHandleBusiness==='function'){{ try{{ x.getHandleBusiness({{entType:'4540',nameId:'{nid}'}}); return {{ok:true,on:x.$options?.name||''}}; }}catch(e){{ return {{ok:false,err:String(e)}}; }} }}
                      return {{ok:false,reason:'no_method'}};
                    }})()"""
                ),
            }
        )
        time.sleep(8)

    # 5) 抓 core flow-control params（如果存在）
    snap = e(
        r"""(function(){
          var href=location.href, hash=location.hash;
          var vm=document.getElementById('app')?.__vue__;
          function find(vm,name,d){if(!vm||d>25)return null; if(vm.$options?.name===name)return vm; for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],name,d+1); if(r)return r;} return null;}
          var fc=find(vm,'flow-control',0);
          var p=fc&&fc.params?fc.params:null;
          var fd=p&&p.flowData?p.flowData:null;
          return {
            href:href, hash:hash, title:document.title,
            hasFlowControl:!!fc,
            flowData:fd,
            itemId:(p&&p.itemId)||'',
            tokenKeys:{
              topToken:!!localStorage.getItem('top-token'),
              auth:!!localStorage.getItem('Authorization')
            }
          };
        })()"""
    )
    rec["steps"].append({"step": "S10_final_snapshot", "data": snap})

    ws.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

