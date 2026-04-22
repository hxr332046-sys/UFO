#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/fix_namecheck_main_industry.json")


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None


def ev(ws_url, expr):
    ws = websocket.create_connection(ws_url, timeout=18)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": 70000},
            }
        )
    )
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close()
            return msg.get("result", {}).get("result", {}).get("value")


def main():
    ws = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    if not ws:
        rec["error"] = "no_namecheck_page"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return
    rec["steps"].append({"step": "before", "data": ev(ws, r"""(function(){var txt=(document.body.innerText||'');return {hash:location.hash,hasMainIndustryEmpty:txt.indexOf('主营行业不能为空')>=0};})()""")})
    rec["steps"].append(
        {
            "step": "set_main_industry",
            "data": ev(
                ws,
                r"""(async function(){
                  function walk(vm,d,pred){if(!vm||d>25)return null;if(pred(vm))return vm;for(var ch of (vm.$children||[])){var r=walk(ch,d+1,pred);if(r)return r;}return null;}
                  var app=document.getElementById('app'); var root=app&&app.__vue__;
                  if(!root) return {ok:false,msg:'no_root'};
                  var idx=walk(root,0,function(v){var n=(v.$options&&v.$options.name)||'';return n==='index'&&v.$parent&&v.$parent.$options&&v.$parent.$options.name==='name-check-info';});
                  if(!idx) return {ok:false,msg:'no_index'};
                  idx.formInfo=idx.formInfo||{};
                  idx.$set(idx.formInfo,'industrySpecial','贸易');
                  idx.$set(idx.formInfo,'allIndKeyWord','贸易');
                  idx.$set(idx.formInfo,'showKeyWord','贸易');
                  if(!idx.formInfo.industryName) idx.$set(idx.formInfo,'industryName','其他未列明零售业');
                  if(!idx.formInfo.industry) idx.$set(idx.formInfo,'industry','5299');
                  // update composed name
                  var pre = idx.formInfo.areaCode || '广西南宁';
                  var mark = idx.formInfo.nameMark || '桂柚百货';
                  var org = idx.formInfo.zhongjainzhi || '802（个人独资）';
                  idx.$set(idx.formInfo,'name', pre + mark + '贸易' + org);
                  // close popup and save
                  var ok=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&((x.textContent||'').replace(/\s+/g,'').indexOf('确定')>=0)&&!x.disabled);
                  if(ok) ok.click();
                  await new Promise(r=>setTimeout(r,200));
                  var save=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').replace(/\s+/g,'').indexOf('保存并下一步')>=0&&!x.disabled);
                  if(save) save.click();
                  return {
                    ok:true,
                    industrySpecial:idx.formInfo.industrySpecial,
                    allIndKeyWord:idx.formInfo.allIndKeyWord,
                    showKeyWord:idx.formInfo.showKeyWord,
                    industry:idx.formInfo.industry,
                    industryName:idx.formInfo.industryName
                  };
                })()""",
            ),
        }
    )
    time.sleep(6)
    rec["steps"].append({"step": "after", "data": ev(ws, r"""(function(){var txt=(document.body.innerText||'');var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);return {href:location.href,hash:location.hash,errors:errs.slice(0,10),hasMainIndustryEmpty:txt.indexOf('主营行业不能为空')>=0,hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0};})()""")})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

