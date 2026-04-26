#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Authorization Token 保活服务 + 自动续期检测。

功能：
  1) 周期性 ping getCacheCreateTime + checkEstablishName 维持会话
  2) 检测到 token 失效时，通过 CDP 自动触发 SSO 重新登录
  3) 登录成功后自动同步新 token 到 runtime_auth_headers.json
  4) 提供 HTTP endpoint /auth/heartbeat 供 Phase1 API 轮询

用法：
  # 独立运行（守护模式，180s 轮询）
  python system/auth_keepalive_service.py --daemon --interval 180

  # 单次检查
  python system/auth_keepalive_service.py --once

  # 检查 + 失效时自动打开登录页
  python system/auth_keepalive_service.py --once --auto-relogin

退出码：
  0 — token alive
  1 — token dead，已触发 relogin（等待人工完成滑块）
  2 — token dead，无法触发 relogin（CDP 不可用）
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

from icpsp_api_client import pick_latest_auth_headers_auto, _BROWSER_LIKE_HEADERS

BASE = "https://zhjg.scjdglj.gxzf.gov.cn:9087"
RUNTIME_AUTH = ROOT / "packet_lab" / "out" / "runtime_auth_headers.json"
STATUS_JSON = ROOT / "dashboard" / "data" / "records" / "auth_keepalive_status.json"
BROWSER_CFG = ROOT / "config" / "browser.json"

# ── 保活 ping 端点（轻量级，不触发业务状态变更）──
PING_ENDPOINTS = [
    ("GET", "/icpsp-api/v4/pc/common/tools/getCacheCreateTime"),
    ("GET", "/icpsp-api/v4/pc/manager/usermanager/getUserInfo"),
]

# ── 业务端点（用来验证 token 真正可用）──
BUSINESS_CHECK = (
    "POST",
    "/icpsp-api/v4/pc/register/guide/establishname/checkEstablishName",
    {"entType": "4540", "nameCode": "0", "distCode": "450921",
     "distCodeArr": ["450000", "450900", "450921"]},
)


@dataclass
class AuthStatus:
    alive: bool = False
    token_preview: str = ""
    ping_ok: bool = False
    business_ok: bool = False
    user_name: str = ""
    last_check: float = 0.0
    last_alive: float = 0.0
    dead_since: float = 0.0
    relogin_triggered: bool = False
    consecutive_fails: int = 0
    check_count: int = 0
    error: str = ""


def _now_text() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _get_headers() -> Dict[str, str]:
    """获取当前完整请求头（含浏览器指纹）"""
    try:
        h = pick_latest_auth_headers_auto()
        return {**h, **_BROWSER_LIKE_HEADERS}
    except Exception:
        return dict(_BROWSER_LIKE_HEADERS)


def _api_call(method: str, path: str, headers: Dict[str, str],
              body: Optional[Dict] = None, timeout: float = 15) -> Dict[str, Any]:
    """发一次 API 请求，返回 {ok, code, msg, data}"""
    url = f"{BASE}{path}?t={int(time.time() * 1000)}"
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=timeout, verify=False)
        else:
            r = requests.post(url, headers=headers, json=body or {}, timeout=timeout, verify=False)
        j = r.json()
        code = str(j.get("code", j.get("status", "")))
        return {"ok": code == "00000", "code": code,
                "msg": str(j.get("msg", ""))[:100], "data": j.get("data")}
    except Exception as e:
        return {"ok": False, "code": "EXCEPTION", "msg": str(e)[:100], "data": None}


def check_token_health(headers: Optional[Dict[str, str]] = None) -> AuthStatus:
    """全面检查当前 token 健康状态"""
    status = AuthStatus()
    status.last_check = time.time()
    status.check_count += 1

    if headers is None:
        headers = _get_headers()

    auth = headers.get("Authorization", "")
    status.token_preview = f"{auth[:8]}..." if len(auth) >= 8 else "(empty)"

    # Step 1: Lightweight ping
    for method, path in PING_ENDPOINTS:
        result = _api_call(method, path, headers)
        if result["ok"]:
            status.ping_ok = True
            # Extract user name from getUserInfo
            if "getUserInfo" in path and isinstance(result.get("data"), dict):
                bd = result["data"].get("busiData") or result["data"]
                if isinstance(bd, dict):
                    status.user_name = str(bd.get("elename", ""))
            break

    # Step 2: Business API check (the real test)
    method, path, body = BUSINESS_CHECK
    result = _api_call(method, path, headers, body)
    status.business_ok = result["ok"]

    # Verdict
    status.alive = status.business_ok
    if status.alive:
        status.last_alive = time.time()
        status.consecutive_fails = 0
        status.dead_since = 0
    else:
        status.consecutive_fails += 1
        if status.dead_since == 0:
            status.dead_since = time.time()
        status.error = f"business_check: code={result['code']} msg={result['msg']}"

    return status


def _write_status(status: AuthStatus) -> None:
    """写状态 JSON 文件"""
    payload = {
        "alive": status.alive,
        "token_preview": status.token_preview,
        "ping_ok": status.ping_ok,
        "business_ok": status.business_ok,
        "user_name": status.user_name,
        "last_check": _now_text(),
        "last_alive": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(status.last_alive)) if status.last_alive else "",
        "dead_since": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(status.dead_since)) if status.dead_since else "",
        "consecutive_fails": status.consecutive_fails,
        "relogin_triggered": status.relogin_triggered,
        "error": status.error,
    }
    STATUS_JSON.parent.mkdir(parents=True, exist_ok=True)
    STATUS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _try_cdp_relogin() -> bool:
    """尝试通过 CDP 打开登录页触发重新登录"""
    try:
        from cdp_login_keepalive import keepalive_once, _cdp_port
        port = _cdp_port()
        result = keepalive_once(port, open_login_page=True, login_wait_sec=8.0)
        return bool(result.get("ok"))
    except Exception as e:
        print(f"[auth_keepalive] CDP relogin failed: {e}")
        return False


def _try_cdp_sync_token() -> Optional[str]:
    """从 CDP 浏览器 localStorage 同步最新 token"""
    try:
        port = _cdp_port()
        pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
        target = None
        for p in pages:
            if p.get("type") == "page" and "9087" in (p.get("url") or ""):
                target = p
                break
        if not target or not target.get("webSocketDebuggerUrl"):
            return None

        import websocket
        ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=10)
        try:
            ws.send(json.dumps({
                "id": 1, "method": "Runtime.evaluate",
                "params": {
                    "expression": "localStorage.getItem('Authorization')",
                    "returnByValue": True,
                }
            }))
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == 1:
                    val = msg.get("result", {}).get("result", {}).get("value")
                    if isinstance(val, str) and len(val) == 32:
                        return val
                    return None
        finally:
            ws.close()
    except Exception:
        return None


def _cdp_port() -> int:
    with BROWSER_CFG.open(encoding="utf-8") as f:
        return int(json.load(f)["cdp_port"])


def keepalive_loop(interval: float = 180, auto_relogin: bool = True,
                   max_loops: int = 0, once: bool = False) -> int:
    """主循环：周期性检查 token + 自动续期"""
    loop = 0
    last_alive_ts = time.time()  # 假设启动时 token 是活的

    while True:
        loop += 1
        headers = _get_headers()
        status = check_token_health(headers)
        _write_status(status)

        # 控制台输出
        state = "ALIVE" if status.alive else "DEAD"
        icon = "+" if status.alive else "!"
        print(f"[{_now_text()}] [{icon}] token={status.token_preview} "
              f"state={state} user={status.user_name} "
              f"ping={status.ping_ok} biz={status.business_ok}")

        if status.alive:
            last_alive_ts = time.time()
        else:
            dead_duration = time.time() - last_alive_ts
            print(f"  !! Token dead for {dead_duration:.0f}s. fails={status.consecutive_fails}")

            if auto_relogin and not status.relogin_triggered:
                # 尝试从 CDP 同步最新 token（可能用户在浏览器里已经重新登录了）
                new_token = _try_cdp_sync_token()
                if new_token and new_token != headers.get("Authorization"):
                    print(f"  >> Found new token from CDP: {new_token[:8]}...")
                    # 写入 runtime_auth
                    from auth_manager_standalone import set_runtime_auth_standalone
                    set_runtime_auth_standalone(new_token)
                    # 重新检查
                    headers2 = _get_headers()
                    status2 = check_token_health(headers2)
                    if status2.alive:
                        print(f"  >> Token refreshed! Now alive.")
                        status = status2
                        _write_status(status)
                        last_alive_ts = time.time()
                    else:
                        print(f"  >> New token also dead, triggering CDP relogin...")
                        ok = _try_cdp_relogin()
                        status.relogin_triggered = True
                        if ok:
                            print(f"  >> CDP relogin triggered, waiting for human to complete slider...")
                        else:
                            print(f"  >> CDP relogin failed (browser not available?)")
                else:
                    # 没有新 token，直接触发 CDP 重登录
                    print(f"  >> No new token from CDP, triggering relogin...")
                    ok = _try_cdp_relogin()
                    status.relogin_triggered = True
                    _write_status(status)

        if once:
            return 0 if status.alive else (1 if status.relogin_triggered else 2)

        if max_loops and loop >= max_loops:
            return 0 if status.alive else 1

        time.sleep(max(30, interval))
        # 如果之前触发了 relogin，下一轮重置标记
        if status.relogin_triggered:
            status.relogin_triggered = False


def set_runtime_auth_standalone(token: str) -> None:
    """写 token 到 runtime_auth_headers.json（独立版，不依赖 FastAPI）"""
    RUNTIME_AUTH.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "Authorization": token,
        "language": "CH",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://zhjg.scjdglj.gxzf.gov.cn:9087",
        "Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html",
        "User-Agent": "Mozilla/5.0",
    }
    RUNTIME_AUTH.write_text(
        json.dumps({"headers": headers, "ts": int(time.time()),
                     "created_at": _now_text(), "source": "keepalive_service"},
                    ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Authorization Token 保活服务")
    ap.add_argument("--once", action="store_true", help="单次检查后退出")
    ap.add_argument("--daemon", action="store_true", help="守护模式（持续运行）")
    ap.add_argument("--interval", type=float, default=180, help="检查间隔（秒，默认 180）")
    ap.add_argument("--auto-relogin", action="store_true", default=True,
                    help="token 失效时自动触发 CDP 重登录")
    ap.add_argument("--no-relogin", action="store_true", help="禁用自动重登录")
    ap.add_argument("--loops", type=int, default=0, help="最大循环次数（0=无限）")
    args = ap.parse_args()

    auto_relogin = not args.no_relogin
    max_loops = 0 if args.daemon else (1 if args.once else args.loops)

    print(f"[auth_keepalive] Starting... interval={args.interval}s auto_relogin={auto_relogin}")
    return keepalive_loop(
        interval=args.interval,
        auto_relogin=auto_relogin,
        max_loops=max_loops,
        once=args.once,
    )


if __name__ == "__main__":
    raise SystemExit(main())
