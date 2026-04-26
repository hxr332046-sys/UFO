"""Session 自愈模块。

当协议调用返回 session_expired（GS52010103E0302）时，尝试从浏览器 CDP（9225 端口）
重新同步 Authorization 和 /icpsp-api 域的 cookie。

恢复流程：
1. 检查 CDP 9225 是否可达
2. 查找 zhjg.scjdglj.gxzf.gov.cn 的 Tab
3. 如果 Tab 存在且在 portal/core 页面 → 提取 localStorage.Authorization + 所有 cookies
4. 写回 phase1_service.auth_manager（内存 token）+ http_session_cookies.pkl（requests.Session cookie jar）

如果浏览器当前在 SSO login 页，恢复失败 → 必须人工重新扫码。
"""
from __future__ import annotations

import asyncio
import json
import pickle
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[3]
COOKIES_PKL = ROOT / "packet_lab" / "out" / "http_session_cookies.pkl"

CDP_BASE = "http://127.0.0.1:9225"


def _find_icpsp_tab() -> Optional[Dict[str, Any]]:
    """返回 icpsp 域的活跃 Tab，找不到返回 None。"""
    try:
        with urllib.request.urlopen(f"{CDP_BASE}/json", timeout=3) as resp:
            tabs = json.loads(resp.read())
    except Exception:
        return None
    for t in tabs:
        if t.get("type") != "page":
            continue
        url = t.get("url", "")
        if "zhjg.scjdglj.gxzf.gov.cn" in url and ("icpsp-web-pc" in url or "9087" in url):
            return t
    return None


def _cdp_eval(ws_url: str, expr: str, timeout: float = 5.0) -> Any:
    """对 WebSocket URL 执行 Runtime.evaluate。"""
    import websocket
    ws = websocket.create_connection(ws_url, timeout=timeout)
    try:
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": expr, "returnByValue": True, "awaitPromise": True},
        }))
        end = time.time() + timeout
        while time.time() < end:
            try:
                ws.settimeout(1.5)
                r = json.loads(ws.recv())
                if r.get("id") == 1:
                    res = r.get("result", {}).get("result", {})
                    return res.get("value", res.get("description"))
            except Exception:
                continue
    finally:
        ws.close()
    return None


def _cdp_get_cookies(ws_url: str, timeout: float = 5.0) -> list:
    """通过 CDP Network.getAllCookies 拿 cookies。"""
    import websocket
    ws = websocket.create_connection(ws_url, timeout=timeout)
    try:
        ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
        time.sleep(0.2)
        ws.send(json.dumps({"id": 2, "method": "Network.getAllCookies"}))
        end = time.time() + timeout
        while time.time() < end:
            try:
                ws.settimeout(1.5)
                r = json.loads(ws.recv())
                if r.get("id") == 2:
                    return r.get("result", {}).get("cookies", []) or []
            except Exception:
                continue
    finally:
        ws.close()
    return []


def _write_cookies_pkl(cookies: list) -> int:
    """把浏览器 cookie 写入 pickle（ICPSPClient 会加载）。只保留 icpsp 相关域。"""
    from http.cookiejar import Cookie
    from requests.cookies import RequestsCookieJar

    jar = RequestsCookieJar()
    kept = 0
    for c in cookies:
        dom = c.get("domain", "")
        path = c.get("path", "/")
        if not (("scjdglj" in dom or "gxzf" in dom) and
                ("/icpsp-api" in path or "/TopIP" in path or path == "/")):
            continue
        cookie = Cookie(
            version=0,
            name=c.get("name", ""),
            value=c.get("value", ""),
            port=None, port_specified=False,
            domain=dom, domain_specified=True, domain_initial_dot=dom.startswith("."),
            path=path, path_specified=True,
            secure=c.get("secure", False),
            expires=int(c.get("expires")) if c.get("expires", -1) > 0 else None,
            discard=False, comment=None, comment_url=None,
            rest={"HttpOnly": None} if c.get("httpOnly") else {},
            rfc2109=False,
        )
        jar.set_cookie(cookie)
        kept += 1

    COOKIES_PKL.parent.mkdir(parents=True, exist_ok=True)
    with open(COOKIES_PKL, "wb") as f:
        pickle.dump(jar, f)
    return kept


def recover_session_from_browser() -> Dict[str, Any]:
    """从 CDP 浏览器同步 Authorization + cookie 到 Python 会话。

    返回：
        {"ok": bool, "authorization": str|None, "cookies_count": int, "reason": str|None}
    """
    tab = _find_icpsp_tab()
    if not tab:
        return {
            "ok": False,
            "authorization": None,
            "cookies_count": 0,
            "reason": "no_icpsp_tab",
            "hint": "CDP 9225 没找到 zhjg.scjdglj.gxzf.gov.cn 页面。浏览器可能跳回 SSO 登录页，需要人工扫码。",
        }

    ws_url = tab["webSocketDebuggerUrl"]

    # 1. 拿 Authorization
    auth = _cdp_eval(ws_url, "localStorage.getItem('Authorization')")
    if not auth or len(str(auth)) < 20:
        return {
            "ok": False,
            "authorization": None,
            "cookies_count": 0,
            "reason": "no_authorization",
            "hint": "浏览器 localStorage 没有 Authorization，会话未建立。",
        }
    auth = str(auth)

    # 2. 拿 cookies
    cookies = _cdp_get_cookies(ws_url)
    if not cookies:
        return {
            "ok": False,
            "authorization": auth,
            "cookies_count": 0,
            "reason": "no_cookies",
            "hint": "CDP 拿不到 cookies，可能 WebSocket 超时。",
        }

    kept = _write_cookies_pkl(cookies)

    # 3. 写回 auth_manager（内存 token）
    try:
        from phase1_service.api.core import auth_manager
        auth_manager.set_runtime_auth(auth)
    except Exception:
        pass

    return {
        "ok": True,
        "authorization": auth[:8] + "...",
        "cookies_count": kept,
        "reason": None,
        "hint": f"已同步 {kept} 个 cookie 到 {COOKIES_PKL}。",
    }


async def recover_session_async() -> Dict[str, Any]:
    """异步包装：session 恢复是 IO 操作，放到 thread executor。"""
    return await asyncio.get_event_loop().run_in_executor(None, recover_session_from_browser)
