from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
for _path in (ROOT / "system", ROOT / "scripts"):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from cdp_login_keepalive import RUNTIME_AUTH_JSON, STATUS_JSON, TOKENS_JSON, _cdp_port, keepalive_once
from launch_browser import launch_browser


def _brief(status: Dict[str, Any]) -> Dict[str, Any]:
    check = status.get("check_token") if isinstance(status.get("check_token"), dict) else {}
    user = status.get("get_user_info") if isinstance(status.get("get_user_info"), dict) else {}
    cache = status.get("cache_ping") if isinstance(status.get("cache_ping"), dict) else {}
    return {
        "ok": bool(status.get("ok")),
        "reason": status.get("reason") or "",
        "checked_at": status.get("checked_at") or "",
        "user_name": status.get("user_name") or "",
        "href": status.get("href") or status.get("target_tab_url") or "",
        "runtime_auth_synced": bool(status.get("runtime_auth_synced")),
        "check_token": {
            "status": check.get("status"),
            "code": check.get("code"),
            "ok": bool(check.get("ok")),
        },
        "get_user_info": {
            "status": user.get("status"),
            "code": user.get("code"),
            "ok": bool(user.get("ok")),
        },
        "cache_ping": {
            "status": cache.get("status"),
            "code": cache.get("code"),
            "ok": bool(cache.get("ok")),
        },
    }


def _print_payload(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)


def _probe(port: int, open_login_page: bool, login_wait_sec: float) -> Dict[str, Any]:
    status = keepalive_once(port, open_login_page=open_login_page, login_wait_sec=login_wait_sec)
    _print_payload({"phase": "probe", **_brief(status)})
    return status


def _wait_for_login(port: int, timeout_sec: float, poll_sec: float) -> Dict[str, Any]:
    deadline = time.time() + max(5.0, timeout_sec)
    last_fingerprint = ""
    while True:
        status = keepalive_once(port, open_login_page=False, login_wait_sec=0.0)
        brief = _brief(status)
        fingerprint = json.dumps(brief, ensure_ascii=False, sort_keys=True)
        if fingerprint != last_fingerprint:
            _print_payload({"phase": "wait_login", **brief})
            last_fingerprint = fingerprint
        if status.get("ok"):
            return status
        if time.time() >= deadline:
            return status
        time.sleep(max(2.0, poll_sec))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait-login-timeout-sec", type=float, default=300.0)
    ap.add_argument("--poll-sec", type=float, default=5.0)
    ap.add_argument("--keepalive-interval-sec", type=float, default=180.0)
    ap.add_argument("--login-wait-sec", type=float, default=5.0)
    ap.add_argument("--no-loop", action="store_true")
    ap.add_argument("--repair-on-fail", action="store_true")
    ap.add_argument("--with-proxy", action="store_true")
    ap.add_argument("--ignore-cert-errors", action="store_true")
    args = ap.parse_args()

    if not launch_browser(no_proxy=not bool(args.with_proxy), ignore_cert_errors=bool(args.ignore_cert_errors)):
        _print_payload({"phase": "launch", "ok": False, "reason": "launch_browser_failed"})
        return 1

    port = _cdp_port()
    status = _probe(port, open_login_page=False, login_wait_sec=0.0)
    if not status.get("ok"):
        status = _probe(port, open_login_page=True, login_wait_sec=float(args.login_wait_sec))
    if not status.get("ok"):
        _print_payload(
            {
                "phase": "manual_login_required",
                "message": "请在专用 Chrome Dev 中完成登录；脚本会自动轮询并在成功后同步 runtime auth。",
                "timeout_sec": float(args.wait_login_timeout_sec),
            }
        )
        status = _wait_for_login(port, timeout_sec=float(args.wait_login_timeout_sec), poll_sec=float(args.poll_sec))
    if not status.get("ok"):
        _print_payload(
            {
                "phase": "failed",
                "status": _brief(status),
                "runtime_auth_json": str(RUNTIME_AUTH_JSON),
                "tokens_json": str(TOKENS_JSON),
                "status_json": str(STATUS_JSON),
            }
        )
        return 2

    _print_payload(
        {
            "phase": "ready",
            "status": _brief(status),
            "runtime_auth_json": str(RUNTIME_AUTH_JSON),
            "tokens_json": str(TOKENS_JSON),
            "status_json": str(STATUS_JSON),
        }
    )

    if args.no_loop:
        return 0

    _print_payload(
        {
            "phase": "keepalive_loop_started",
            "interval_sec": float(args.keepalive_interval_sec),
            "repair_on_fail": bool(args.repair_on_fail),
        }
    )
    try:
        while True:
            time.sleep(max(15.0, float(args.keepalive_interval_sec)))
            status = keepalive_once(port, open_login_page=False, login_wait_sec=0.0)
            if status.get("ok"):
                _print_payload({"phase": "keepalive", **_brief(status)})
                continue
            _print_payload({"phase": "keepalive_lost", **_brief(status)})
            if not args.repair_on_fail:
                continue
            status = keepalive_once(port, open_login_page=True, login_wait_sec=float(args.login_wait_sec))
            _print_payload({"phase": "repair", **_brief(status)})
    except KeyboardInterrupt:
        _print_payload({"phase": "stopped", "reason": "keyboard_interrupt"})
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
