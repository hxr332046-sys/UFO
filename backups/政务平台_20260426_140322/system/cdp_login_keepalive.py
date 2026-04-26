from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import websocket

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

from icpsp_entry import list_page_targets, pick_icpsp_target_prefer_logged_portal

BROWSER_CFG = ROOT / "config" / "browser.json"
RUNTIME_AUTH_JSON = ROOT / "packet_lab" / "out" / "runtime_auth_headers.json"
TOKENS_JSON = ROOT / "data" / "tokens.json"
STATUS_JSON = ROOT / "dashboard" / "data" / "records" / "login_keepalive_status.json"
LOGIN_URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/login/authPage"

PROBE_JS = r"""(function(){
  function text(v){ return String(v || ''); }
  function parseJson(s){ try{ return JSON.parse(s); }catch(e){ return null; } }
  function req(method, url, body){
    var xhr = new XMLHttpRequest();
    try{
      xhr.open(method, url + (url.indexOf('?') >= 0 ? '&' : '?') + '_t=' + Date.now(), false);
      xhr.setRequestHeader('Authorization', localStorage.getItem('Authorization') || '');
      var top = localStorage.getItem('top-token') || '';
      if(top) xhr.setRequestHeader('top-token', top);
      if(method !== 'GET') xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.send(method === 'GET' ? null : JSON.stringify(body || {}));
    }catch(e){
      return {status: 0, ok: false, code: '', msg: text(e).slice(0, 160), body: '', data: null};
    }
    var raw = xhr.responseText || '';
    var js = parseJson(raw) || {};
    return {
      status: xhr.status || 0,
      ok: xhr.status >= 200 && xhr.status < 300,
      code: text(js.code || ''),
      msg: text(js.msg || '').slice(0, 160),
      body: raw.slice(0, 240),
      data: js.data || null
    };
  }
  function pickName(obj){
    if(!obj || typeof obj !== 'object') return '';
    return text(obj.realName || obj.username || obj.name || obj.elename || '');
  }
  var top = localStorage.getItem('top-token') || '';
  var auth = localStorage.getItem('Authorization') || '';
  var app = document.getElementById('app');
  var root = app && app.__vue__;
  var store = root && root.$store;
  var vueUser = null;
  var vueUserName = '';
  try{
    vueUser = (store && store.state && store.state.login && store.state.login.userInfo) ||
      (store && store.state && store.state.common && store.state.common.userInfo) || null;
    vueUserName = pickName(vueUser);
  }catch(e){}
  try{ if(store && top && store.commit) store.commit('login/SET_TOKEN', top); }catch(e){}
  try{ if(store && auth && store.commit) store.commit('user/SET_TOKEN', auth); }catch(e){}
  var checkToken = auth || top ? req('POST', '/icpsp-api/v4/pc/login/checkToken', {}) : {status: 0, ok: false, code: '', msg: 'missing_token', body: '', data: null};
  var getUserInfo = auth || top ? req('GET', '/icpsp-api/v4/pc/user/getUserInfo', null) : {status: 0, ok: false, code: '', msg: 'missing_token', body: '', data: null};
  var cachePing = auth || top ? req('GET', '/icpsp-api/v4/pc/common/tools/getCacheCreateTime', null) : {status: 0, ok: false, code: '', msg: 'missing_token', body: '', data: null};
  var userData = (getUserInfo && getUserInfo.data && (getUserInfo.data.userInfo || getUserInfo.data.busiData || getUserInfo.data)) || null;
  return {
    href: location.href,
    hash: location.hash,
    title: document.title || '',
    readyState: document.readyState || '',
    authorization: auth,
    topToken: top,
    cookie: document.cookie || '',
    localStorageKeys: Object.keys(localStorage).sort(),
    guestWords: /登录|注册|扫码/.test((document.body && document.body.innerText) || ''),
    vueUserName: vueUserName,
    userName: pickName(userData) || vueUserName,
    checkToken: checkToken,
    getUserInfo: getUserInfo,
    cachePing: cachePing
  };
})()"""


def _cdp_port() -> int:
    with BROWSER_CFG.open(encoding="utf-8") as f:
        return int(json.load(f)["cdp_port"])


def _now_text() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _mask(value: str, head: int = 8) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= head + 4:
        return "***"
    return f"{text[:head]}…(len={len(text)})"


def _is_9087(url: str) -> bool:
    text = str(url or "")
    return "zhjg.scjdglj.gxzf.gov.cn:9087" in text and "icpsp-web-pc" in text


def _looks_sso_failure_page(state: Dict[str, Any]) -> bool:
    href = str(state.get("href") or "")
    title = str(state.get("title") or "")
    return (
        "/icpsp-api/sso/oauth2" in href
        or "portal.html#/login/" in href
        or "#/login/authPage" in href
        or "#/login/page" in href
        or "单点登录失败" in title
        or ("统一认证" in title and "登录" in title)
    )


def _response_ok(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    status = int(item.get("status") or 0)
    code = str(item.get("code") or "").strip()
    return 200 <= status < 300 or code in {"00000", "200"}


def _pick_target(port: int) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    debug: List[Dict[str, Any]] = []
    try:
        best, debug = pick_icpsp_target_prefer_logged_portal(port)
    except Exception as e:
        best = None
        debug = [{"error": f"pick_icpsp_target_prefer_logged_portal:{e}"}]
    if best:
        return best, debug
    try:
        pages = list_page_targets(port)
    except Exception as e:
        debug = debug + [{"error": f"list_page_targets:{e}"}]
        return None, debug
    for page in pages:
        if page.get("webSocketDebuggerUrl"):
            return page, debug
    return None, debug


def _eval_value(ws_url: str, expression: str, timeout_ms: int = 45000) -> Any:
    ws = websocket.create_connection(ws_url, timeout=18)
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
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                inner = msg.get("result", {}).get("result", {})
                return inner.get("value")
    finally:
        try:
            ws.close()
        except Exception:
            pass


def _page_navigate(ws_url: str, url: str, wait_sec: float) -> None:
    ws = websocket.create_connection(ws_url, timeout=18)
    try:
        ws.send(json.dumps({"id": 1, "method": "Page.navigate", "params": {"url": url}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                break
    finally:
        try:
            ws.close()
        except Exception:
            pass
    time.sleep(max(0.5, wait_sec))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sync_runtime_auth(state: Dict[str, Any]) -> bool:
    auth = str(state.get("authorization") or "").strip()
    top = str(state.get("topToken") or "").strip()
    cookie = str(state.get("cookie") or "").strip()
    if len(auth) != 32:
        return False
    headers: Dict[str, str] = {
        "Authorization": auth,
        "language": "CH",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://zhjg.scjdglj.gxzf.gov.cn:9087",
        "Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html",
        "User-Agent": "Mozilla/5.0",
    }
    if top:
        headers["top-token"] = top
    if cookie:
        headers["Cookie"] = cookie
    _write_json(
        RUNTIME_AUTH_JSON,
        {
            "created_at": _now_text(),
            "base_url": "https://zhjg.scjdglj.gxzf.gov.cn:9087",
            "source": {"kind": "cdp_keepalive", "page_url": state.get("href")},
            "headers": headers,
        },
    )
    _write_json(
        TOKENS_JSON,
        {
            "authorization": auth,
            "top_token": top,
            "user_info": {"name": state.get("userName") or ""},
            "refresh_time": time.time(),
            "update_time": _now_text(),
            "source_page": state.get("href") or "",
        },
    )
    return True


def _build_status(ok: bool, reason: str, port: int, tab_url: str, state: Optional[Dict[str, Any]], debug: List[Dict[str, Any]], sync_ok: bool) -> Dict[str, Any]:
    state = state or {}
    check = state.get("checkToken") if isinstance(state.get("checkToken"), dict) else {}
    user = state.get("getUserInfo") if isinstance(state.get("getUserInfo"), dict) else {}
    cache = state.get("cachePing") if isinstance(state.get("cachePing"), dict) else {}
    sso_failure_page = _looks_sso_failure_page(state)
    return {
        "ok": ok,
        "reason": reason,
        "checked_at": _now_text(),
        "cdp_port": port,
        "target_tab_url": tab_url,
        "href": state.get("href") or "",
        "hash": state.get("hash") or "",
        "title": state.get("title") or "",
        "ready_state": state.get("readyState") or "",
        "local_storage_keys": state.get("localStorageKeys") or [],
        "likely_logged_in_storage": len(str(state.get("authorization") or "")) >= 16 and len(str(state.get("topToken") or "")) >= 16,
        "authorization": _mask(str(state.get("authorization") or "")),
        "top_token": _mask(str(state.get("topToken") or "")),
        "user_name": state.get("userName") or state.get("vueUserName") or "",
        "guest_words": bool(state.get("guestWords")),
        "sso_failure_page": sso_failure_page,
        "check_token": {
            "status": check.get("status"),
            "code": check.get("code"),
            "ok": bool(check.get("ok")),
            "msg": check.get("msg"),
        },
        "get_user_info": {
            "status": user.get("status"),
            "code": user.get("code"),
            "ok": bool(user.get("ok")),
            "msg": user.get("msg"),
        },
        "cache_ping": {
            "status": cache.get("status"),
            "code": cache.get("code"),
            "ok": bool(cache.get("ok")),
            "msg": cache.get("msg"),
        },
        "runtime_auth_synced": sync_ok,
        "tab_probe": debug,
    }


def keepalive_once(port: int, open_login_page: bool = False, login_wait_sec: float = 5.0) -> Dict[str, Any]:
    target, debug = _pick_target(port)
    if not target or not target.get("webSocketDebuggerUrl"):
        status = _build_status(False, "no_cdp_target", port, "", None, debug, False)
        _write_json(STATUS_JSON, status)
        return status
    tab_url = str(target.get("url") or "")
    ws_url = str(target.get("webSocketDebuggerUrl") or "")
    if open_login_page and not _is_9087(tab_url):
        try:
            _page_navigate(ws_url, LOGIN_URL, login_wait_sec)
            tab_url = LOGIN_URL
        except Exception as e:
            status = _build_status(False, f"open_login_page_failed:{e}", port, tab_url, None, debug, False)
            _write_json(STATUS_JSON, status)
            return status
    try:
        state = _eval_value(ws_url, PROBE_JS)
    except Exception as e:
        status = _build_status(False, f"cdp_eval_failed:{e}", port, tab_url, None, debug, False)
        _write_json(STATUS_JSON, status)
        return status
    if not isinstance(state, dict):
        status = _build_status(False, "unexpected_state", port, tab_url, None, debug, False)
        _write_json(STATUS_JSON, status)
        return status
    if open_login_page and len(str(state.get("authorization") or "")) < 16 and len(str(state.get("topToken") or "")) < 16:
        try:
            _page_navigate(ws_url, LOGIN_URL, login_wait_sec)
            state_retry = _eval_value(ws_url, PROBE_JS)
            if isinstance(state_retry, dict):
                state = state_retry
        except Exception:
            pass
    sync_ok = _sync_runtime_auth(state)
    user_name = str(state.get("userName") or state.get("vueUserName") or "").strip()
    sso_failure_page = _looks_sso_failure_page(state)
    user_name_alive = bool(user_name) and not bool(state.get("guestWords")) and not sso_failure_page
    weak_ping_only = _response_ok(state.get("cachePing")) and not (
        _response_ok(state.get("checkToken"))
        or _response_ok(state.get("getUserInfo"))
        or user_name_alive
    )
    portal_logged_hint = any(
        isinstance(item, dict)
        and isinstance(item.get("hint"), dict)
        and bool(item["hint"].get("hasTaskCenter"))
        and not bool(item["hint"].get("guestHeaderLogin"))
        for item in debug
    )
    alive = sync_ok and not sso_failure_page and (
        _response_ok(state.get("checkToken"))
        or _response_ok(state.get("getUserInfo"))
        or user_name_alive
        or portal_logged_hint
        or (_response_ok(state.get("cachePing")) and not bool(state.get("guestWords")) and not weak_ping_only)
    )
    if alive:
        reason = "alive"
    elif sso_failure_page:
        reason = "sso_failure_or_login_required"
    else:
        reason = "token_missing_or_ping_failed"
    status = _build_status(alive, reason, port, tab_url, state, debug, sync_ok)
    _write_json(STATUS_JSON, status)
    return status


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=float, default=180.0)
    ap.add_argument("--loops", type=int, default=0)
    ap.add_argument("--open-login-page", action="store_true")
    ap.add_argument("--login-wait-sec", type=float, default=5.0)
    args = ap.parse_args()

    port = _cdp_port()
    round_index = 0
    last_code = 0
    while True:
        round_index += 1
        status = keepalive_once(port, open_login_page=bool(args.open_login_page), login_wait_sec=float(args.login_wait_sec))
        print(json.dumps(status, ensure_ascii=False, indent=2))
        last_code = 0 if status.get("ok") else 1
        if args.once:
            return last_code
        if args.loops and round_index >= int(args.loops):
            return last_code
        time.sleep(max(15.0, float(args.interval)))


if __name__ == "__main__":
    raise SystemExit(main())
