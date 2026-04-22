#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CDP 单连接跑「第一阶段」UI 链，同时把 /icpsp-api/ 请求按时间序写入 recipe JSON。

思路（与你的问题对齐）：
1. 用浏览器真实会话跑一遍 → 录下接口 URL + POST JSON（顺序即业务依赖的粗逻辑）。
2. 将 recipe 交给 `phase1_recipe_replay_http.py` 做纯 HTTP 重放；**默认 `--recipe auto` 会直接用仓库里
   已有的 `packet_listen_namecheck_once.json` / `stage1_replay_*.json`，不强制你再录一遍。**

前置：9225 CDP、9087 已登录；政务平台根目录执行。

  python system/phase1_recipe_cdp_record.py
  python system/phase1_recipe_cdp_record.py --case docs/case_广西容县李陈梦.json --human-fast
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import websocket

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

from human_pacing import configure_human_pacing, sleep_human  # noqa: E402
from icpsp_entry import pick_icpsp_target_prefer_logged_portal  # noqa: E402
from run_phase1_from_case import (  # noqa: E402
    HOST,
    build_namecheck_fill_js,
    enterprise_zone_establish_js,
    pick_ws,
    _resolve_name_mark,
)


def _cdp_port() -> int:
    try:
        with (ROOT / "config" / "browser.json").open(encoding="utf-8") as f:
            return int(json.load(f).get("cdp_port") or 9225)
    except Exception:
        return 9225

OUT_JSON = ROOT / "dashboard" / "data" / "records" / "phase1_icpsp_recipe_latest.json"


class CDPRecipeRecorder:
    """单 WebSocket：CDP 命令与 Network.requestWillBeSent 同流读取。"""

    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=35)
        self._seq = 1
        self.icpsp: List[Dict[str, Any]] = []

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass

    def _sniff_net(self, msg: Dict[str, Any]) -> None:
        p = msg.get("params") or {}
        req = p.get("request") or {}
        url = str(req.get("url") or "")
        if "/icpsp-api/" not in url:
            return
        method = str(req.get("method") or "GET").upper()
        pd = str(req.get("postData") or "")
        row: Dict[str, Any] = {
            "ts": time.time(),
            "method": method,
            "url": url[:900],
            "postData_len": len(pd),
        }
        if method == "POST" and pd.strip():
            try:
                row["post_json"] = json.loads(pd)
            except json.JSONDecodeError:
                row["postData_preview"] = pd[:4000]
        self.icpsp.append(row)

    def _drain_until_id(self, cid: int, timeout: float = 150.0) -> Dict[str, Any]:
        end = time.time() + timeout
        while time.time() < end:
            try:
                self.ws.settimeout(1.0)
                raw = self.ws.recv()
            except Exception:
                continue
            msg = json.loads(raw)
            if msg.get("method") == "Network.requestWillBeSent":
                self._sniff_net(msg)
                continue
            if msg.get("id") == cid:
                return msg
        raise TimeoutError(f"CDP 等待 id={cid} 超时")

    def _cmd(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        cid = self._seq
        self._seq += 1
        self.ws.send(json.dumps({"id": cid, "method": method, "params": params or {}}))
        return self._drain_until_id(cid)

    def enable(self) -> None:
        self._cmd("Network.enable", {})
        self._cmd("Page.enable", {})

    def evaluate(self, expression: str, timeout_ms: int = 120000) -> Any:
        m = self._cmd(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
                "timeout": timeout_ms,
            },
        )
        return ((m.get("result") or {}).get("result") or {}).get("value")

    def sleep_drain(self, seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            try:
                self.ws.settimeout(0.12)
                raw = self.ws.recv()
                msg = json.loads(raw)
                if msg.get("method") == "Network.requestWillBeSent":
                    self._sniff_net(msg)
            except Exception:
                pass


def main() -> int:
    ap = argparse.ArgumentParser(description="CDP 跑第一阶段并录制 icpsp-api 请求链")
    ap.add_argument("--case", type=Path, default=ROOT / "docs" / "case_广西容县李陈梦.json")
    ap.add_argument("--human-fast", action="store_true")
    ap.add_argument("-o", "--output", type=Path, default=OUT_JSON)
    args = ap.parse_args()

    configure_human_pacing(ROOT / "config" / "human_pacing.json", fast=bool(args.human_fast))

    if not args.case.is_file():
        print("ERROR: case 不存在", args.case)
        return 2

    case = json.loads(args.case.read_text(encoding="utf-8"))
    busi = str(case.get("busiType_default") or "02_4").strip()
    ent = str(case.get("entType_default") or "1100").strip()
    name_mark = _resolve_name_mark(case)
    dist_codes = case.get("phase1_dist_codes")
    if not isinstance(dist_codes, list) or len(dist_codes) < 3:
        dist_codes = ["450000", "450900", "450921"]

    port = _cdp_port()
    best, tab_dbg = pick_icpsp_target_prefer_logged_portal(port)
    ws = best.get("webSocketDebuggerUrl") if isinstance(best, dict) else None
    cur = best.get("url") if isinstance(best, dict) else None
    if not ws:
        ws, cur = pick_ws()
    rec: Dict[str, Any] = {
        "schema": "ufo.phase1_icpsp_recipe.v1",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "case_path": str(args.case),
        "picked_tab_url": cur,
        "tab_pick_debug": tab_dbg,
        "ui_steps": [],
        "replay_notes": [
            "顺序即浏览器内实际发出的 icpsp-api 请求（仅 Network.requestWillBeSent，含部分异步尾包）。",
            "含 busiId / nameId 的保存类接口：重放时常需把上一响应里的 id 写回后续 body，见各接口返回 JSON。",
            "Authorization 为会话态：与 mitm/runtime_auth_headers 同步刷新；纯后台不等于无 Cookie。",
        ],
    }
    if not ws:
        rec["error"] = "no_cdp_page"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print("ERROR: 无 9087 页签")
        return 2

    r = CDPRecipeRecorder(ws)
    try:
        r.enable()
        URL_ENTERPRISE = (
            f"https://{HOST}/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone"
            f"?fromProject=portal&fromPage=%2Findex%2Fpage&busiType={busi}&merge=Y"
        )
        URL_DECL = (
            f"https://{HOST}/icpsp-web-pc/name-register.html#/namenotice/declaration-instructions"
            f"?fromProject=portal&fromPage=%2Findex%2Fenterprise%2Fenterprise-zone&entType={ent}&busiType={busi}"
        )
        URL_GUIDE = (
            f"https://{HOST}/icpsp-web-pc/name-register.html#/guide/base"
            f"?busiType={busi}&entType={ent}&marPrId=&marUniscId="
        )

        r.evaluate(f"location.href={json.dumps(URL_ENTERPRISE)}", 60000)
        rec["ui_steps"].append({"step": "enterprise_zone_nav"})
        sleep_human(5.5)
        r.sleep_drain(1.5)
        ws, _ = pick_ws("enterprise-zone")

        ez = r.evaluate(enterprise_zone_establish_js(ent, [str(x) for x in dist_codes]), 90000)
        rec["ui_steps"].append({"step": "enterprise_zone_establish_wizard", "data": ez})
        sleep_human(2.5)
        r.sleep_drain(2.0)

        clicked = r.evaluate(
            r"""(function(){
          var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('开始办理')>=0&&!x.disabled);
          if(b){b.click();return true;}return false;
        })()""",
            30000,
        )
        rec["ui_steps"].append({"step": "click_start_banli", "data": clicked})
        sleep_human(2.0)
        r.sleep_drain(1.5)

        r.evaluate(f"location.href={json.dumps(URL_DECL)}", 60000)
        rec["ui_steps"].append({"step": "declaration_nav"})
        sleep_human(5.5)
        r.sleep_drain(2.0)
        ws, _ = pick_ws("declaration-instructions")

        r.evaluate(
            r"""(function(){
          var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('我已阅读并同意')>=0&&!x.disabled);
          if(b){b.click();return true;}return false;
        })()""",
            30000,
        )
        rec["ui_steps"].append({"step": "declaration_agree"})
        sleep_human(2.0)
        r.sleep_drain(1.5)

        r.evaluate(f"location.href={json.dumps(URL_GUIDE)}", 60000)
        rec["ui_steps"].append({"step": "guide_base_nav"})
        sleep_human(6.0)
        r.sleep_drain(2.0)
        ws, _ = pick_ws("guide/base")

        guide_click = r.evaluate(
            r"""(function(){
          var els=[...document.querySelectorAll('label,span,div,li,a')].filter(e=>e.offsetParent!==null);
          for(var e of els){
            var t=(e.textContent||'').replace(/\s+/g,' ').trim();
            if(t.indexOf('未办理企业名称预保留')>=0){e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));return 'picked_unreserved';}
          }
          var n=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0&&!x.disabled);
          if(n){n.click();return 'next';}
          var ok=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&((x.textContent||'').replace(/\s+/g,'').indexOf('确定')>=0)&&!x.disabled);
          if(ok){ok.click();return 'ok';}
          return 'no_click';
        })()""",
            45000,
        )
        rec["ui_steps"].append({"step": "guide_base_click", "data": guide_click})
        sleep_human(7.0)
        r.sleep_drain(4.0)

        fill_js = build_namecheck_fill_js(case, name_mark, dist_codes)
        fill = r.evaluate(fill_js, 120000)
        rec["ui_steps"].append({"step": "namecheck_fill_attempt", "data": fill})
        r.sleep_drain(8.0)

        rec["icpsp_requests_chronological"] = r.icpsp
        rec["icpsp_post_count"] = sum(1 for x in r.icpsp if str(x.get("method") or "").upper() == "POST")
        rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        rec["error"] = str(e)
        rec["icpsp_requests_chronological"] = getattr(r, "icpsp", [])
    finally:
        r.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"saved": str(args.output), "icpsp_total": len(rec.get("icpsp_requests_chronological") or []), "posts": rec.get("icpsp_post_count")}, ensure_ascii=False))
    return 2 if rec.get("error") == "no_cdp_page" else 0


if __name__ == "__main__":
    raise SystemExit(main())
