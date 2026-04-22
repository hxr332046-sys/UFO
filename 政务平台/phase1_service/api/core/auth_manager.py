"""Authorization 管理。支持：
1) 请求里显式传 Authorization header（推荐生产）
2) 服务端回退到最新抓包/CDP 捕获（仅开发）
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]
RUNTIME_AUTH_JSON = ROOT / "packet_lab/out/runtime_auth_headers.json"


def validate_authorization(token: str) -> bool:
    if not isinstance(token, str):
        return False
    t = token.strip()
    return len(t) == 32 and all(c in "0123456789abcdefABCDEF" for c in t)


def set_runtime_auth(authorization: str) -> None:
    """把外部传入的 Authorization 写到 runtime_auth_headers.json，
    让 ICPSPClient 的 pick_latest_auth_headers_auto 优先读到它。"""
    if not validate_authorization(authorization):
        raise ValueError(f"invalid authorization format (need 32-hex): {authorization[:8]}...")
    RUNTIME_AUTH_JSON.parent.mkdir(parents=True, exist_ok=True)
    current = {}
    if RUNTIME_AUTH_JSON.exists():
        try:
            current = json.loads(RUNTIME_AUTH_JSON.read_text(encoding="utf-8"))
        except Exception:
            current = {}
    current_headers = current.get("headers") if isinstance(current, dict) else None
    if not isinstance(current_headers, dict):
        current_headers = {}
    current_headers["Authorization"] = authorization.strip()
    current_headers.setdefault("language", "CH")
    current_headers.setdefault("Content-Type", "application/json")
    current_headers.setdefault("Accept", "application/json, text/plain, */*")
    current_headers.setdefault("Origin", "https://zhjg.scjdglj.gxzf.gov.cn:9087")
    current_headers.setdefault(
        "Referer",
        "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html",
    )
    RUNTIME_AUTH_JSON.write_text(
        json.dumps({"headers": current_headers, "ts": int(time.time())}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_current_auth() -> Optional[str]:
    if not RUNTIME_AUTH_JSON.exists():
        return None
    try:
        d = json.loads(RUNTIME_AUTH_JSON.read_text(encoding="utf-8"))
        h = d.get("headers") or {}
        a = h.get("Authorization")
        return a if validate_authorization(a) else None
    except Exception:
        return None
