#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L6 会话授权引导器（Session Bootstrap via CDP）

**定位**：L6.5 混合架构里的"浏览器协处理器"——只做一件事：
让浏览器把当前 SESSION 从 portal 状态推到"名称登记"业务上下文，
以便后续 Python 纯协议调用 `NameCheckInfo/operationBusinessDataInfo` 时
服务端不再返回 `code=GS52010103E0302 用户认证失败或用户未认证!`。

**不干什么**：
  · 不填表、不点保存、不做 Vue flowSave（那些由 phase1_protocol_driver.py 走协议跑）
  · 不做 SSO 登录（滑块/账号密码由你手工完成）
  · 不做任何 mutating 操作（只做 GET navigation + 被动等待）

工作方式：
  1) 通过 CDP 找到 9087 下的业务页签；若当前在 tyrz 登录页则报错并提示你先登录
  2) 导航到 guide/base 直达 URL（entType=4540, busiType=02_4）
  3) 等待页面就绪 + 主动发一次 cache_ping（校验 Authorization）
  4) 从 localStorage+document.cookie 同步 Authorization / top-token / Cookie 到
     packet_lab/out/runtime_auth_headers.json（覆盖 ICPSPClient 的头源）
  5) 写状态 JSON 到 dashboard/data/records/session_bootstrap_latest.json

用法:
  .\.venv-portal\Scripts\python.exe system\session_bootstrap_cdp.py
  .\.venv-portal\Scripts\python.exe system\session_bootstrap_cdp.py --ent 4540 --busi 02_4

退出码:
  0 — 成功进入 guide/base 并同步了 Authorization+Cookie
  2 — 没有 9087 页签；需先在浏览器里完成登录
  3 — 进到 guide/base 失败（被统一认证拦截/网络错误）
  4 — 同步 auth 头失败
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import websocket

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

OUT_JSON = ROOT / "dashboard" / "data" / "records" / "session_bootstrap_latest.json"
RUNTIME_AUTH = ROOT / "packet_lab" / "out" / "runtime_auth_headers.json"
CFG_BROWSER = ROOT / "config" / "browser.json"

HOST_9087 = "zhjg.scjdglj.gxzf.gov.cn:9087"
SSO_HOST = "tyrz.zwfw.gxzf.gov.cn"


def _cdp_port() -> int:
    with CFG_BROWSER.open(encoding="utf-8") as f:
        return int(json.load(f)["cdp_port"])


def _pick_page(port: int, prefer_host: str) -> Optional[Dict[str, Any]]:
    try:
        pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
    except Exception:
        return None
    # 优先 9087，其次最近打开的
    for p in pages:
        if p.get("type") != "page":
            continue
        u = str(p.get("url") or "")
        if prefer_host in u:
            return p
    for p in pages:
        if p.get("type") == "page" and p.get("webSocketDebuggerUrl"):
            return p
    return None


def _ev(ws_url: str, expr: str, *, timeout_ms: int = 30000) -> Any:
    ws = websocket.create_connection(ws_url, timeout=12)
    try:
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": expr,
                        "returnByValue": True,
                        "awaitPromise": True,
                        "timeout": timeout_ms,
                    },
                }
            )
        )
        deadline = time.time() + max(30, timeout_ms / 1000 + 10)
        while time.time() < deadline:
            raw = ws.recv()
            try:
                m = json.loads(raw)
            except Exception:
                continue
            if m.get("id") == 1:
                res = m.get("result") or {}
                if res.get("exceptionDetails"):
                    return {"_cdp_exception": res.get("exceptionDetails")}
                return (res.get("result") or {}).get("value")
    finally:
        try:
            ws.close()
        except Exception:
            pass
    return None


def _cdp_call(ws_url: str, method: str, params: Optional[Dict[str, Any]] = None, *, timeout_sec: float = 10.0) -> Any:
    """调用任意 CDP domain 方法（如 Network.getCookies）。返回 result 字段。"""
    ws = websocket.create_connection(ws_url, timeout=8)
    try:
        ws.send(json.dumps({"id": 1, "method": method, "params": params or {}}))
        deadline = time.time() + max(3.0, timeout_sec)
        while time.time() < deadline:
            try:
                raw = ws.recv()
            except Exception:
                continue
            try:
                m = json.loads(raw)
            except Exception:
                continue
            if m.get("id") == 1:
                return m.get("result")
    finally:
        try:
            ws.close()
        except Exception:
            pass
    return None


def _read_session_cookies(ws_url: str, origin: str = "https://zhjg.scjdglj.gxzf.gov.cn:9087") -> tuple[str, Dict[str, Any]]:
    """用 CDP Network.getAllCookies 读取所有 cookies（含 httpOnly），合成 Cookie 头。

    ★ 已知 bug：Network.getCookies(urls=[...带端口...]) 会遗漏 SESSION cookie，
    因为 SESSION cookie 的 domain 是 zhjg.scjdglj.gxzf.gov.cn（无端口），
    getCookies 的 URL 过滤在某些 Chromium 版本下匹配不到。
    因此改用 getAllCookies + 手动域名过滤。
    """
    try:
        _cdp_call(ws_url, "Network.enable")
    except Exception:
        pass
    # ★ 用 getAllCookies 替代 getCookies，避免端口过滤 bug
    res = _cdp_call(ws_url, "Network.getAllCookies", {}, timeout_sec=8.0)
    all_cookies = []
    if isinstance(res, dict):
        all_cookies = res.get("cookies") or []
    # 过滤相关域名的 cookies，去重处理
    target_domain = "scjdglj.gxzf.gov.cn"
    # ★ 用 dict 去重：同名 cookie 只保留最优的（path 含 /icpsp 的优先，否则后出现的覆盖）
    best: Dict[str, tuple] = {}  # name → (value, path, priority)
    for c in all_cookies:
        if not isinstance(c, dict):
            continue
        domain = str(c.get("domain") or "")
        if target_domain not in domain:
            continue
        n = str(c.get("name") or "")
        v = str(c.get("value") or "")
        path = str(c.get("path") or "/")
        if not n:
            continue
        # 优先级：/icpsp 路径 > / 路径 > 其他
        prio = 2 if "/icpsp" in path else (1 if path == "/" else 0)
        existing = best.get(n)
        if existing is None or prio >= existing[2]:
            best[n] = (v, path, prio)
    pairs = []
    saw = {"SESSION": False, "topIP": False, "cookieNames": []}
    for n, (v, path, _) in best.items():
        pairs.append(f"{n}={v}")
        saw["cookieNames"].append(n)
        if n == "SESSION":
            saw["SESSION"] = True
    return "; ".join(pairs), saw


def _navigate(ws_url: str, target_url: str, wait_sec: float = 4.0) -> None:
    _ev(ws_url, f"location.href = {json.dumps(target_url, ensure_ascii=False)}", timeout_ms=30000)
    time.sleep(wait_sec)


def _build_probe_js() -> str:
    return r"""(async function(){
      function getItem(k){ try { return localStorage.getItem(k) || ''; } catch(e){ return ''; } }
      var auth = getItem('Authorization');
      var top = getItem('top-token');
      var href = location.href;
      var host = location.host;
      var cookie = document.cookie || '';
      // 主动 ping 一次看服务端是否承认当前 Authorization
      var ping = null;
      try {
        var resp = await fetch('/icpsp-api/v4/pc/manager/usermanager/getUserInfo?t=' + Date.now(), {
          method: 'GET',
          credentials: 'include',
          headers: {
            'Authorization': auth || '',
            'language': 'CH',
            'Accept': 'application/json, text/plain, */*'
          }
        });
        var txt = await resp.text();
        try { ping = { status: resp.status, body: JSON.parse(txt) }; }
        catch(e){ ping = { status: resp.status, text: txt.slice(0, 300) }; }
      } catch(e){ ping = { error: String(e) }; }
      return {
        href: href,
        host: host,
        authLen: (auth || '').length,
        hasAuth32: (auth || '').length === 32,
        hasTopToken: (top || '').length > 8,
        cookieLen: cookie.length,
        cookieHasSession: /\bSESSION=/.test(cookie),
        ping: ping
      };
    })()"""


def _sync_runtime_auth(ws_url: str, *, referer_override: Optional[str] = None) -> Dict[str, Any]:
    """
    从浏览器读 Authorization / top-token，并用 CDP `Network.getCookies` 读**所有** cookies（含 httpOnly SESSION），
    合成完整 Cookie 头写入 runtime_auth_headers.json。

    这是 L6.5 架构的核心：SESSION cookie 被服务端设为 httpOnly，document.cookie 读不到；
    但 CDP 的 Network domain 可以绕过 httpOnly 限制。
    """
    js = r"""(function(){
      function getItem(k){ try { return localStorage.getItem(k) || ''; } catch(e){ return ''; } }
      return {
        href: location.href,
        Authorization: getItem('Authorization'),
        topToken: getItem('top-token'),
        docCookie: document.cookie || ''
      };
    })()"""
    val = _ev(ws_url, js, timeout_ms=20000)
    if not isinstance(val, dict):
        return {"ok": False, "reason": "cdp_eval_unexpected", "raw": val}
    auth = str(val.get("Authorization") or "").strip()
    top = str(val.get("topToken") or "").strip()
    doc_cookie = str(val.get("docCookie") or "").strip()
    if len(auth) != 32:
        return {"ok": False, "reason": "auth_not_32", "authLen": len(auth)}

    # 关键：用 CDP getCookies 读 httpOnly 的 SESSION
    full_cookie, cookie_meta = _read_session_cookies(ws_url)
    if not full_cookie:
        # 退化到 document.cookie
        full_cookie = doc_cookie

    # Referer：默认按页面 URL 自动推断；允许外部覆盖
    href = str(val.get("href") or "")
    if referer_override:
        referer = referer_override
    elif "core.html" in href:
        referer = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html"
    elif "name-register.html" in href:
        referer = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html"
    else:
        referer = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"

    headers: Dict[str, str] = {
        "Authorization": auth,
        "language": "CH",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://zhjg.scjdglj.gxzf.gov.cn:9087",
        "Referer": referer,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/149.0.0.0",
    }
    if top:
        headers["top-token"] = top
    if full_cookie:
        headers["Cookie"] = full_cookie
    payload = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "notes": "Synced by session_bootstrap_cdp.py via CDP Network.getCookies (httpOnly aware). Do not commit.",
        "base_url": "https://zhjg.scjdglj.gxzf.gov.cn:9087",
        "source": {"kind": "session_bootstrap_cdp", "page_url": href, "referer": referer},
        "headers": headers,
    }
    RUNTIME_AUTH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_AUTH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "auth_last8": auth[-8:],
        "cookie_has_session": bool(cookie_meta.get("SESSION")),
        "cookie_names": cookie_meta.get("cookieNames") or [],
        "referer_used": referer,
    }


def bootstrap(ent_type: str = "4540", busi_type: str = "02_4") -> Dict[str, Any]:
    port = _cdp_port()
    rec: Dict[str, Any] = {
        "schema": "ufo.session_bootstrap.v1",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cdp_port": port,
        "ent_type": ent_type,
        "busi_type": busi_type,
        "steps": [],
        "final": {},
    }
    page = _pick_page(port, HOST_9087)
    if not page:
        rec["error"] = "no_cdp_page"
        rec["hint"] = "请先打开浏览器并访问 9087，或检查 CDP 端口"
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        return rec

    ws_url = str(page.get("webSocketDebuggerUrl") or "")
    cur_url = str(page.get("url") or "")
    rec["steps"].append({"step": "pick_page", "url": cur_url})

    if SSO_HOST in cur_url:
        rec["error"] = "sso_login_pending"
        rec["hint"] = f"当前在统一认证登录页（{SSO_HOST}），请先在浏览器里完成登录再运行本脚本"
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        return rec

    # 1) 导航到 guide/base 直达 URL（entType/busiType 从参数带入）
    target = (
        f"https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#"
        f"/guide/base?busiType={busi_type}&entType={ent_type}&marPrId=&marUniscId="
    )
    _navigate(ws_url, target, wait_sec=3.5)
    rec["steps"].append({"step": "navigate_guide_base", "target": target})

    # 2) 等页面稳定 + 主动 probe
    state1 = _ev(ws_url, _build_probe_js(), timeout_ms=30000)
    rec["steps"].append({"step": "probe_after_navigate", "data": state1})

    # 若落回统一认证，立即返回
    if isinstance(state1, dict) and SSO_HOST in str(state1.get("host") or ""):
        rec["error"] = "sso_redirect_after_navigate"
        rec["hint"] = "guide/base 导航后被统一认证拦截，说明会话已经失效，请重新登录"
        OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        return rec

    # 3) 再等几秒让页面的前置接口（queryRegcodeAndStreet / checkGreenChannel / loadCurrentLocationInfo 等）
    #    都跑完，再次探针
    time.sleep(4.0)
    state2 = _ev(ws_url, _build_probe_js(), timeout_ms=30000)
    rec["steps"].append({"step": "probe_after_settle", "data": state2})

    # 4) 同步 Authorization / Cookie 到 runtime_auth_headers.json
    sync_res = _sync_runtime_auth(ws_url)
    rec["steps"].append({"step": "sync_runtime_auth", "data": sync_res})

    if not sync_res.get("ok"):
        rec["error"] = "sync_failed"
        OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        return rec

    # 5) 终局判定：Authorization+Cookie 就绪 && 页面在 name-register.html
    final_href = ""
    if isinstance(state2, dict):
        final_href = str(state2.get("href") or "")
    ok = (
        "name-register.html" in final_href
        and bool(sync_res.get("cookie_has_session"))
        and isinstance(state2, dict)
        and bool(state2.get("hasAuth32"))
    )
    rec["final"] = {
        "ok": ok,
        "href": final_href,
        "authorization_synced": sync_res.get("ok"),
        "cookie_has_session": sync_res.get("cookie_has_session"),
    }
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ent", dest="ent_type", default="4540", help="entType，默认 4540（个人独资企业）")
    ap.add_argument("--busi", dest="busi_type", default="02_4", help="busiType，默认 02_4")
    args = ap.parse_args()
    rec = bootstrap(ent_type=args.ent_type, busi_type=args.busi_type)
    print(json.dumps({
        "final": rec.get("final"),
        "error": rec.get("error"),
        "hint": rec.get("hint"),
        "saved": str(OUT_JSON),
    }, ensure_ascii=False, indent=2))
    final = rec.get("final") or {}
    if final.get("ok"):
        return 0
    err = rec.get("error")
    if err == "no_cdp_page":
        return 2
    if err in ("sso_login_pending", "sso_redirect_after_navigate"):
        return 3
    if err == "sync_failed":
        return 4
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
