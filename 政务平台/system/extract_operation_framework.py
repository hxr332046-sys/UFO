#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT_JSON = Path("G:/UFO/政务平台/data/operation_framework_02_4.json")
OUT_MD = Path("G:/UFO/政务平台/data/operation_framework_02_4.md")

URLS = [
    "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone?fromProject=portal&fromPage=%2Findex%2Fpage&busiType=02_4&merge=Y",
    "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/namenotice/declaration-instructions?fromProject=portal&fromPage=%2Findex%2Fenterprise%2Fenterprise-zone&entType=1100&busiType=02_4",
    "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=1100&marPrId=&marUniscId=",
]


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url, expr, timeout=30000):
    ws = websocket.create_connection(ws_url, timeout=8)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout},
            }
        )
    )
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            ws.close()
            return m.get("result", {}).get("result", {}).get("value")


def inspect_page(ws_url):
    return ev(
        ws_url,
        r"""(function(){
  function txt(s){return (s||'').replace(/\s+/g,' ').trim();}
  var btns=Array.from(document.querySelectorAll('button,.el-button,a,span,div'))
    .filter(function(e){return e.offsetParent!==null;})
    .map(function(e){
      var t=txt(e.textContent);
      if(!t || t.length>40) return null;
      var role='other';
      if(/开始办理|下一步|继续办理|保存并下一步|完成并提交|确定|同意|关闭/.test(t)) role='primary-action';
      else if(/添加|删除|编辑/.test(t)) role='list-action';
      return {text:t, role:role, tag:e.tagName, cls:(e.className||'').slice(0,80)};
    })
    .filter(Boolean);

  var inputs=Array.from(document.querySelectorAll('.el-form-item')).map(function(item){
    var lb=item.querySelector('.el-form-item__label');
    var label=txt(lb&&lb.textContent||'');
    var inp=item.querySelector('input.el-input__inner,textarea.el-textarea__inner');
    var sel=item.querySelector('.el-select,.el-cascader,.el-radio-group,.el-checkbox-group');
    var typ='none';
    var val='';
    if(inp){ typ=inp.tagName==='TEXTAREA'?'textarea':'input'; val=txt(inp.value||''); }
    else if(sel){ typ='selector'; }
    if(!label) return null;
    return {label:label,type:typ,value:val,required:(item.className||'').indexOf('is-required')>=0};
  }).filter(Boolean);

  var popups=Array.from(document.querySelectorAll('.el-dialog__wrapper,.el-message-box__wrapper'))
    .filter(function(e){return e.offsetParent!==null;})
    .map(function(e){return txt(e.textContent).slice(0,240);});

  var steps=Array.from(document.querySelectorAll('.el-step__title,.steps-title, .flow-step'))
    .map(function(e){return txt(e.textContent)})
    .filter(Boolean)
    .slice(0,20);

  return {
    href:location.href,
    hash:location.hash,
    title:document.title,
    buttonCandidates:btns.slice(0,120),
    formFields:inputs.slice(0,120),
    popups:popups.slice(0,8),
    steps:steps
  };
})()""",
    )


def to_markdown(data):
    lines = ["# 02_4 链路操作框架", ""]
    lines.append("## 页面与操作清单")
    lines.append("")
    for i, p in enumerate(data["pages"], 1):
        lines.append(f"### {i}. `{p['url']}`")
        snap = p["snapshot"]
        lines.append(f"- 当前哈希: `{snap.get('hash','')}`")
        if snap.get("popups"):
            lines.append("- 弹窗/提示:")
            for t in snap["popups"][:3]:
                lines.append(f"  - {t}")
        primary = [b["text"] for b in snap.get("buttonCandidates", []) if b.get("role") == "primary-action"]
        uniq_primary = []
        for t in primary:
            if t not in uniq_primary:
                uniq_primary.append(t)
        lines.append("- 关键动作按钮:")
        for t in uniq_primary[:12]:
            lines.append(f"  - {t}")
        required = [f for f in snap.get("formFields", []) if f.get("required")]
        if required:
            lines.append("- 必填字段框架:")
            for f in required[:20]:
                lines.append(f"  - {f['label']} ({f['type']})")
        lines.append("")

    lines.append("## 建议执行顺序")
    lines.append("- 入口页 `enterprise-zone`：关闭提示弹窗 -> 点击“开始办理”")
    lines.append("- 说明页 `declaration-instructions`：等待“我已阅读并同意”按钮可点 -> 点击同意/下一步")
    lines.append("- 指引页 `guide/base`：选择主体类型、名称是否已申报、所在地区 -> 点击“下一步”")
    lines.append("- 进入名称申报成功页后：点击“继续办理设立登记”进入信息填报")
    lines.append("- 信息填报页优先处理剩余必填空项，再执行“保存并下一步”")
    lines.append("")
    return "\n".join(lines)


def main():
    ws, cur = pick_ws()
    if not ws:
        raise RuntimeError("No zhjg page in CDP")

    result = {"captured_at": time.strftime("%Y-%m-%d %H:%M:%S"), "pages": []}
    for u in URLS:
        ev(ws, f"location.href='{u}'", timeout=15000)
        time.sleep(7)
        ws, _ = pick_ws()
        snap = inspect_page(ws)
        result["pages"].append({"url": u, "snapshot": snap})

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text(to_markdown(result), encoding="utf-8")
    print(f"Saved: {OUT_JSON}")
    print(f"Saved: {OUT_MD}")


if __name__ == "__main__":
    main()

