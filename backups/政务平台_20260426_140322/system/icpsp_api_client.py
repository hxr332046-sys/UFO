#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
icpsp-api client for reverse engineering & automation.

- Auth source (default): latest usable headers from mitm jsonl (Authorization + Cookie).
- No hardcoded secrets: callers do NOT pass tokens manually.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests


_ROOT = Path(__file__).resolve().parent.parent
MITM_DEFAULT = _ROOT / "dashboard" / "data" / "records" / "mitm_ufo_flows.jsonl"
RECORDS_DIR = _ROOT / "dashboard" / "data" / "records"
RUNTIME_AUTH_JSON = _ROOT / "packet_lab" / "out" / "runtime_auth_headers.json"
HTTP_SESSION_PKL = _ROOT / "packet_lab" / "out" / "http_session_cookies.pkl"

# 类浏览器指纹头：服务端某些接口（如 NameCheckInfo/operationBusinessDataInfo）会检查这组头，
# 若缺失会返回 D0022（越权访问）。下面这组是 Edge Dev 149 + Windows 的默认值。
# 实测：补齐这组头后 D0022 消失，接口返回 00000。
_BROWSER_LIKE_HEADERS: Dict[str, str] = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "sec-ch-ua": '"Microsoft Edge";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0"
    ),
}


def _is_good_auth(h: Dict[str, Any]) -> bool:
    a = h.get("Authorization")
    if not isinstance(a, str) or len(a.strip()) != 32:
        return False
    return True


def pick_latest_auth_headers(mitm_jsonl: Path = MITM_DEFAULT) -> Dict[str, str]:
    """Find latest record with Authorization; return minimal replay headers."""
    if not mitm_jsonl.exists():
        raise FileNotFoundError(f"mitm not found: {mitm_jsonl}")
    lines = mitm_jsonl.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in reversed(lines):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        h = rec.get("req_headers")
        if not isinstance(h, dict) or not _is_good_auth(h):
            continue
        auth = str(h.get("Authorization") or "").strip()
        cookie = str(h.get("Cookie") or "").strip()
        referer = str(h.get("Referer") or "").strip()
        # minimal set; other headers can be added by caller
        out: Dict[str, str] = {
            "Authorization": auth,
            "language": str(h.get("language") or "CH"),
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://zhjg.scjdglj.gxzf.gov.cn:9087",
            "Referer": referer or "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html",
            "User-Agent": str(h.get("User-Agent") or "Mozilla/5.0"),
        }
        if cookie:
            out["Cookie"] = cookie
        return out
    raise RuntimeError("no Authorization found in mitm jsonl")


def pick_latest_auth_headers_from_cdp(records_dir: Path = RECORDS_DIR) -> Dict[str, str]:
    """Find latest Authorization/Cookie from CDP watch jsonl."""
    files = sorted(records_dir.glob("manual_cdp_watch*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for fp in files:
        try:
            lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for line in reversed(lines):
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "req":
                continue
            url = str(rec.get("url") or "")
            if "/icpsp-api/" not in url:
                continue
            h = rec.get("req_headers")
            if not isinstance(h, dict) or not _is_good_auth(h):
                continue
            auth = str(h.get("Authorization") or "").strip()
            cookie = str(h.get("Cookie") or "").strip()
            referer = str(h.get("Referer") or "").strip()
            origin = str(h.get("Origin") or "https://zhjg.scjdglj.gxzf.gov.cn:9087").strip()
            out: Dict[str, str] = {
                "Authorization": auth,
                "language": str(h.get("language") or "CH"),
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Origin": origin,
                "Referer": referer or "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html",
                "User-Agent": str(h.get("User-Agent") or "Mozilla/5.0"),
            }
            if cookie:
                out["Cookie"] = cookie
            return out
    raise RuntimeError("no Authorization found in CDP watch jsonl")


def pick_latest_auth_headers_auto(mitm_jsonl: Path = MITM_DEFAULT, records_dir: Path = RECORDS_DIR) -> Dict[str, str]:
    """Prefer freshest source: CDP watch, then mitm fallback."""
    errs = []
    try:
        if RUNTIME_AUTH_JSON.exists():
            payload = json.loads(RUNTIME_AUTH_JSON.read_text(encoding="utf-8", errors="replace"))
            h = payload.get("headers") if isinstance(payload, dict) else None
            if isinstance(h, dict) and _is_good_auth(h):
                out = {str(k): str(v) for k, v in h.items() if isinstance(k, str) and isinstance(v, str)}
                # drop non-protocol helper keys
                for k in list(out.keys()):
                    if k.startswith("X-"):
                        out.pop(k, None)
                out.setdefault("Content-Type", "application/json")
                out.setdefault("Accept", "application/json, text/plain, */*")
                out.setdefault("Origin", "https://zhjg.scjdglj.gxzf.gov.cn:9087")
                out.setdefault("Referer", "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html")
                out.setdefault("User-Agent", "Mozilla/5.0")
                out.setdefault("language", "CH")
                return out
    except Exception as e:
        errs.append(f"runtime_json={e!r}")
    try:
        return pick_latest_auth_headers_from_cdp(records_dir)
    except Exception as e:
        errs.append(f"cdp={e!r}")
    try:
        return pick_latest_auth_headers(mitm_jsonl)
    except Exception as e:
        errs.append(f"mitm={e!r}")
    raise RuntimeError("no auth headers from any source: " + "; ".join(errs))


def _load_http_session_cookies() -> Optional[Any]:
    """加载纯 HTTP 扫码登录后保存的 session cookies（含 9087 SESSION / SESSIONFORTYRZ）。
    Phase 2 的 name/loadCurrentLocationInfo 等接口必须带 9087 SESSION。"""
    if not HTTP_SESSION_PKL.exists():
        return None
    try:
        import pickle
        with open(HTTP_SESSION_PKL, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


@dataclass
class ICPSPClient:
    mitm_jsonl: Path = MITM_DEFAULT
    base: str = "https://zhjg.scjdglj.gxzf.gov.cn:9087"
    timeout: float = 30.0

    def __post_init__(self) -> None:
        self.s = requests.Session()
        self.s.verify = False
        self.s.proxies = {"http": None, "https": None}
        # 加载 pure-HTTP 登录保存的 session cookies（Phase 2 必需）
        cj = _load_http_session_cookies()
        if cj is not None:
            try:
                self.s.cookies = cj
            except Exception:
                pass

    def _headers(self) -> Dict[str, str]:
        h = pick_latest_auth_headers_auto(self.mitm_jsonl, RECORDS_DIR)
        # 若 runtime_auth_headers.json 缺 Cookie，从 mitm 同 Authorization 记录补 Cookie
        # （注：实测本站登录态主要靠 Authorization header，Cookie 可选）
        if not h.get("Cookie"):
            try:
                mh = pick_latest_auth_headers(self.mitm_jsonl)
                if mh.get("Cookie") and mh.get("Authorization") == h.get("Authorization"):
                    h["Cookie"] = mh["Cookie"]
            except Exception:
                pass
        # 类浏览器指纹头强制补全：某些接口（operationBusinessDataInfo 等）会校验
        # sec-ch-ua-* / Sec-Fetch-* / UA，缺失则 D0022 "越权访问"。
        # 只在 runtime 没显式覆盖时补；UA 特殊——已有 "Mozilla/5.0" 占位时替换成完整 Edge UA。
        for k, v in _BROWSER_LIKE_HEADERS.items():
            cur = h.get(k, "")
            if not cur:
                h[k] = v
            elif k == "User-Agent" and cur.strip() in ("Mozilla/5.0", "python-requests"):
                h[k] = v
        # session 已加载 pkl cookies，requests 会自动发送；
        # 但若 header 已有 Cookie 字符串（来自 mitm 或旧逻辑），requests 会优先用 session cookies
        # 所以删掉 header 里的 Cookie，让 session 管
        if _load_http_session_cookies() is not None:
            h.pop("Cookie", None)
        return h

    def get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = self.base + path
        h = self._headers()
        if params is None:
            params = {}
        params = dict(params)
        params.setdefault("t", int(time.time() * 1000))
        r = self.s.get(url, headers=h, params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def post_json(self, path: str, body: Dict[str, Any],
                   extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        url = self.base + path
        h = self._headers()
        if extra_headers:
            h.update(extra_headers)
        # keep a t param in url to mimic frontend; harmless
        if "?" not in url:
            url = url + f"?t={int(time.time()*1000)}"
        r = self.s.post(url, headers=h, json=body, timeout=self.timeout)
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {"_non_json": True, "text": (r.text or "")[:4000]}

