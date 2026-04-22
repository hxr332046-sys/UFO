#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从任意 CDP 可见页签定位广西登记平台（9087 / icpsp-web-pc）办件入口。

策略：
- 在多个标签页中按「与 9087 主流程相关程度」打分，优先连接最相关的标签页。
- navigate_policy=host_only：仅在非 9087 或不在 icpsp-web-pc 产品线时，整页跳转到
  portal 企业专区入口（含 busiType），避免打断已在 core / name-register 内的会话。
- navigate_policy=establish_zone：在 host 已正确且当前不在名称/设立核心页时，
  统一拉到企业专区入口（仍保留 core.html / name-register 不打断）。
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Literal, Optional, Tuple
from urllib.parse import parse_qs

import requests
import websocket

ICPSP_HOST = "zhjg.scjdglj.gxzf.gov.cn"
ICPSP_PORT = "9087"
PORTAL_PATH = "/icpsp-web-pc/portal.html"
ENTERPRISE_ZONE_HASH = "#/index/enterprise/enterprise-zone"

NavigatePolicy = Literal["host_only", "establish_zone"]


def enterprise_zone_entry_url(
    busi_type: str = "02_4",
    *,
    from_project: str = "portal",
    from_page: str = "/login/authPage",
    merge: str = "Y",
) -> str:
    """设立类业务常用：门户企业专区 + busiType（与线上一致）。"""
    from urllib.parse import quote

    q = (
        f"fromProject={from_project}"
        f"&fromPage={quote(from_page, safe='')}"
        f"&busiType={busi_type}"
        f"&merge={merge}"
    )
    return f"https://{ICPSP_HOST}:{ICPSP_PORT}{PORTAL_PATH}{ENTERPRISE_ZONE_HASH}?{q}"


def _hash_and_query(url: str) -> Tuple[str, Dict[str, str]]:
    """从 portal.html#/path?a=1 中解析 hash 路径与查询参数。"""
    if "#" not in url:
        return "", {}
    frag = url.split("#", 1)[1]
    path = frag.split("?", 1)[0]
    if "?" not in frag:
        return path, {}
    qstr = frag.split("?", 1)[1]
    raw = parse_qs(qstr)
    return path, {k: v[0] if v else "" for k, v in raw.items()}


def _is_icpsp_9087(url: str) -> bool:
    u = url.lower()
    return ICPSP_HOST in u and f":{ICPSP_PORT}" in u and "icpsp-web-pc" in u


def _in_core_or_name_register(url: str) -> bool:
    u = url.lower()
    return "core.html" in u or "name-register" in u


def _is_enterprise_zone_with_busi(url: str, busi_type: str) -> bool:
    path, q = _hash_and_query(url)
    if "enterprise-zone" not in path and "enterprise-zone" not in url:
        return False
    bt = (q.get("busiType") or q.get("busitype") or "").strip()
    return bt == busi_type


def score_icpsp_relevance(url: str) -> int:
    """分数越高越适合作为政务平台自动化目标页签。"""
    if not url or url.startswith("devtools://"):
        return -1000
    if "chrome-error" in url:
        return -500
    s = 0
    if ICPSP_HOST in url:
        s += 20
    if f":{ICPSP_PORT}" in url:
        s += 80
    if "icpsp-web-pc" in url:
        s += 50
    if "core.html" in url or "name-register" in url:
        s += 40
    if "enterprise-zone" in url:
        s += 25
    if "portal.html" in url:
        s += 15
    # 同主域但 6087 准入门户等较低优先级
    if "TopIP" in url or ":6087" in url:
        s -= 30
    return s


def list_page_targets(cdp_port: int = 9225) -> List[Dict[str, Any]]:
    pages = requests.get(f"http://127.0.0.1:{cdp_port}/json", timeout=5).json()
    return [p for p in pages if p.get("type") == "page" and not p.get("url", "").startswith("devtools://")]


def pick_best_target(pages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not pages:
        return None
    ranked = sorted(pages, key=lambda p: -score_icpsp_relevance(p.get("url") or ""))
    return ranked[0]


# 9087 页头：已登录常见「办件中心」；未登录常见「登录 / 注册」
_PORTAL_LOGIN_PROBE_JS = r"""(function(){
  var t=(document.body&&document.body.innerText)||'';
  var head=t.slice(0,1400);
  return {
    hasTaskCenter: head.indexOf('办件中心')>=0,
    guestHeaderLogin: /登录\s*\/\s*注册/.test(head),
    href: location.href
  };
})()"""


def _score_icpsp_tab_for_portal(
    page: Dict[str, Any], hint: Optional[Dict[str, Any]]
) -> int:
    u = page.get("url") or ""
    s = score_icpsp_relevance(u)
    if isinstance(hint, dict) and hint.get("hasTaskCenter") and not hint.get("guestHeaderLogin"):
        s += 300
    if isinstance(hint, dict) and hint.get("guestHeaderLogin"):
        s -= 200
    if "portal.html" in u and "#/index/page" in u:
        s += 40
    return s


def pick_icpsp_target_prefer_logged_portal(
    cdp_port: int = 9225,
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    在多个 9087 标签页中探测登录态，优先选「办件中心」且非访客顶栏的页签。
    避免脚本连到未登录标签却误以为会话无效。
    """
    pages = list_page_targets(cdp_port)
    icpsp = [p for p in pages if _is_icpsp_9087(p.get("url") or "")]
    debug: List[Dict[str, Any]] = []
    scored: List[Tuple[int, Dict[str, Any], Any]] = []
    for p in icpsp:
        ws = p.get("webSocketDebuggerUrl")
        hint: Any = None
        if ws:
            try:
                hint = _cdp_eval_value(ws, _PORTAL_LOGIN_PROBE_JS, timeout_ms=12000)
            except Exception as e:
                hint = {"error": str(e)}
        debug.append({"url": p.get("url"), "hint": hint})
        sc = _score_icpsp_tab_for_portal(p, hint if isinstance(hint, dict) else None)
        scored.append((sc, p, hint))
    if not scored:
        return pick_best_target(pages), debug
    scored.sort(key=lambda x: -x[0])
    best = scored[0][1]
    return best, debug


def _cdp_eval_value(ws_url: str, expression: str, timeout_ms: int = 20000) -> Any:
    ws = websocket.create_connection(ws_url, timeout=10)
    try:
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": expression,
                        "returnByValue": True,
                        "awaitPromise": True,
                        "timeout": timeout_ms,
                    },
                }
            )
        )
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == 1:
                return m.get("result", {}).get("result", {}).get("value")
    finally:
        try:
            ws.close()
        except Exception:
            pass


def _navigate_href(ws_url: str, target_url: str, wait_sec: float = 3.0) -> None:
    # 使用 assign 保留历史；单页应用整页跳转后需等待加载
    expr = f"location.href = {json.dumps(target_url, ensure_ascii=False)}"
    _cdp_eval_value(ws_url, expr, timeout_ms=60000)
    time.sleep(wait_sec)


def ensure_icpsp_entry(
    cdp_port: int = 9225,
    *,
    busi_type: str = "02_4",
    navigate_policy: NavigatePolicy = "host_only",
    wait_after_nav_sec: float = 3.0,
) -> Dict[str, Any]:
    """
    选中最佳页签，并在需要时导航到 9087 企业专区入口。

    Returns:
        ok, ws_url, url_before, url_after, navigated, reason
    """
    pages = list_page_targets(cdp_port)
    best = pick_best_target(pages)
    if not best:
        return {"ok": False, "error": "no_page_targets"}

    ws_url = best["webSocketDebuggerUrl"]
    url_before = best.get("url") or ""
    entry = enterprise_zone_entry_url(busi_type)

    need_nav = False
    reason = "undecided"

    if not _is_icpsp_9087(url_before):
        need_nav = True
        reason = "not_icpsp_9087"
    elif navigate_policy == "establish_zone":
        if _in_core_or_name_register(url_before):
            reason = "keep_core_or_name_register"
        elif _is_enterprise_zone_with_busi(url_before, busi_type):
            reason = "already_enterprise_zone"
        else:
            need_nav = True
            reason = "establish_zone_policy"
    else:
        # host_only：已在 9087 icpsp 产品线，不强制拉回 enterprise-zone
        reason = "host_only_skip_nav"

    if not need_nav:
        url_after = _cdp_eval_value(ws_url, "location.href", timeout_ms=5000)
        return {
            "ok": True,
            "ws_url": ws_url,
            "url_before": url_before,
            "url_after": url_after or url_before,
            "navigated": False,
            "reason": reason,
        }

    _navigate_href(ws_url, entry, wait_sec=wait_after_nav_sec)
    url_after = _cdp_eval_value(ws_url, "location.href", timeout_ms=15000)
    return {
        "ok": True,
        "ws_url": ws_url,
        "url_before": url_before,
        "url_after": url_after or entry,
        "navigated": True,
        "reason": reason,
    }


def get_ws_url_for_icpsp(
    cdp_port: int = 9225,
    *,
    busi_type: str = "02_4",
    navigate_policy: NavigatePolicy = "host_only",
) -> Optional[str]:
    """供脚本一行获取「已纠偏入口」的 WebSocket URL。"""
    r = ensure_icpsp_entry(cdp_port, busi_type=busi_type, navigate_policy=navigate_policy)
    return r.get("ws_url") if r.get("ok") else None
