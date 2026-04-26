"""`/api/auth/*` 的 QR 扫码 + Token 刷新 API。

三条路径：

1) POST /api/auth/token/refresh — 静默续期（~2秒，不扫码）
   复用 `system.login_qrcode_pure_http.refresh_token()`，需要之前已保存过 SESSIONFORTYRZ。

2) POST /api/auth/qr/start + GET /api/auth/qr/status — 分步 QR 扫码
   start 返回 {sid, qr_image_base64}，服务端在内存存 session 对象；
   前端展示 QR → 用户扫码 → 前端每 3~5 秒 GET status → 扫完自动走 SSO 拿 token。

3) POST /api/auth/token/ensure — 智能获取（先 refresh，失败返回"需扫码"标志）
   不 block 等扫码（适合 API 场景）。

所有成功路径最终会调用 `login_qrcode_pure_http._save_auth()` 把 token 写入
`packet_lab/out/runtime_auth_headers.json`（后续所有 API 自动使用）+ 保存 cookies。
"""
from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "system"))

# 复用已有的纯 HTTP 登录模块
import login_qrcode_pure_http as lqp  # type: ignore
from login_qrcode import (  # type: ignore
    QR_CHECK,
    step1_get_login_page,
    step2_get_qrcode,
    step5_submit_login,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ─── 进程级 QR session 池（sid → {s, csrf, created_at}） ───

_qr_sessions: Dict[str, Dict[str, Any]] = {}
_qr_lock = Lock()

_QR_TTL_SEC = 300  # 5 分钟无效清理


def _cleanup_expired():
    now = time.time()
    with _qr_lock:
        expired = [
            sid for sid, info in _qr_sessions.items()
            if now - info.get("created_at", 0) > _QR_TTL_SEC
        ]
        for sid in expired:
            _qr_sessions.pop(sid, None)


# ─── Response 模型 ───

class RefreshResponse(BaseModel):
    success: bool
    authorization: Optional[str] = None
    reason: Optional[str] = None
    reason_detail: Optional[str] = None


class QrStartResponse(BaseModel):
    success: bool
    sid: Optional[str] = None          # 对应 server session_id
    qr_image_base64: Optional[str] = None
    expire_sec: int = _QR_TTL_SEC
    reason: Optional[str] = None
    reason_detail: Optional[str] = None


class QrStatusResponse(BaseModel):
    success: bool                       # 是否成功完成登录
    scanned: bool = False               # 是否已扫码（成功或待确认）
    pending: bool = True                # 是否还在等待（二维码有效、待扫或待确认）
    authorization: Optional[str] = None
    reason: Optional[str] = None
    reason_detail: Optional[str] = None


class EnsureResponse(BaseModel):
    success: bool
    source: Optional[str] = None        # "existing" / "refresh" / "qr_needed"
    authorization: Optional[str] = None
    qr_hint: Optional[Dict[str, Any]] = None  # 若需扫码，引导调 qr/start
    reason: Optional[str] = None
    reason_detail: Optional[str] = None


# ─── API: Token 静默续期 ───

@router.post("/token/refresh", response_model=RefreshResponse)
async def token_refresh() -> RefreshResponse:
    """静默续期 Authorization（不需要扫码）。

    前提：之前通过扫码登录过，`packet_lab/out/http_session_cookies.pkl` 内 SESSIONFORTYRZ 仍有效。
    """
    try:
        token = lqp.refresh_token(verbose=False)
    except Exception as e:
        return RefreshResponse(
            success=False,
            reason="refresh_exception",
            reason_detail=f"{type(e).__name__}: {str(e)[:200]}",
        )
    if not token:
        return RefreshResponse(
            success=False,
            reason="session_expired",
            reason_detail="本地 SESSIONFORTYRZ 已失效（或未扫码过），需要调用 /api/auth/qr/start 重新扫码",
        )
    return RefreshResponse(success=True, authorization=token)


# ─── API: QR 扫码 ───

@router.post("/qr/start", response_model=QrStartResponse)
async def qr_start(
    user_type: int = Query(default=1, ge=1, le=2, description="1=个人（默认），2=法人"),
) -> QrStartResponse:
    """生成二维码 + 返回 sid。前端展示二维码让用户扫码，然后轮询 /qr/status。"""
    _cleanup_expired()

    try:
        s = lqp._make_session()
        csrf = step1_get_login_page(s)
        if not csrf:
            return QrStartResponse(
                success=False,
                reason="login_page_failed",
                reason_detail="获取登录页 csrf_token 失败",
            )
        session_id, qr_bytes = step2_get_qrcode(s, user_type=user_type)
        if not session_id or not qr_bytes:
            return QrStartResponse(
                success=False,
                reason="qr_fetch_failed",
                reason_detail="无法获取二维码（平台接口异常）",
            )
    except Exception as e:
        return QrStartResponse(
            success=False,
            reason="qr_start_exception",
            reason_detail=f"{type(e).__name__}: {str(e)[:200]}",
        )

    # 存进程级池
    with _qr_lock:
        _qr_sessions[session_id] = {
            "s": s,
            "csrf": csrf,
            "created_at": time.time(),
            "user_type": user_type,
            "authorization": None,  # 扫完后填
            "done": False,
        }

    return QrStartResponse(
        success=True,
        sid=session_id,
        qr_image_base64=base64.b64encode(qr_bytes).decode("ascii"),
        expire_sec=_QR_TTL_SEC,
    )


def _check_qr_once(s, session_id: str) -> Dict[str, Any]:
    """调一次 /am/qrCode/checkQrCode，返回 {status, data}。不 block。"""
    try:
        r = s.post(QR_CHECK, data={"random": session_id}, timeout=8)
        return r.json() or {}
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {str(e)[:100]}"}


@router.get("/qr/status", response_model=QrStatusResponse)
async def qr_status(sid: str = Query(..., description="POST /qr/start 返回的 sid")) -> QrStatusResponse:
    """轮询一次扫码状态。若已扫码且成功，自动走 SSO 拿 Authorization。"""
    _cleanup_expired()

    with _qr_lock:
        info = _qr_sessions.get(sid)
    if not info:
        return QrStatusResponse(
            success=False, scanned=False, pending=False,
            reason="sid_not_found",
            reason_detail="sid 不存在或已过期（>5分钟无操作），请重新 /qr/start",
        )

    # 已完成：直接返回缓存的 token
    if info.get("done"):
        token = info.get("authorization")
        return QrStatusResponse(
            success=bool(token),
            scanned=True,
            pending=False,
            authorization=token,
        )

    s = info["s"]
    csrf = info["csrf"]

    check = _check_qr_once(s, sid)
    status = check.get("status", "")
    data_val = check.get("data", "")

    if status != "success":
        # 还在等待扫码
        return QrStatusResponse(
            success=False, scanned=False, pending=True,
        )

    # 扫码成功（data=1）或失败（其他）
    if str(data_val) != "1":
        with _qr_lock:
            info["done"] = True
        return QrStatusResponse(
            success=False, scanned=True, pending=False,
            reason="scan_rejected",
            reason_detail=f"扫码未通过: data={data_val}",
        )

    # 走 SSO 拿 token
    try:
        redirect_url = step5_submit_login(s, csrf, sid)
        if not redirect_url:
            with _qr_lock:
                info["done"] = True
            return QrStatusResponse(
                success=False, scanned=True, pending=False,
                reason="submit_failed",
                reason_detail="扫码成功但提交登录失败",
            )
        token = lqp._sso_steps_234(s, verbose=False)
    except Exception as e:
        with _qr_lock:
            info["done"] = True
        return QrStatusResponse(
            success=False, scanned=True, pending=False,
            reason="sso_exception",
            reason_detail=f"{type(e).__name__}: {str(e)[:200]}",
        )

    if not token:
        with _qr_lock:
            info["done"] = True
        return QrStatusResponse(
            success=False, scanned=True, pending=False,
            reason="sso_no_token",
            reason_detail="SSO 链完成但未拿到 Authorization",
        )

    # 保存 token + cookies
    try:
        lqp._save_auth(token, "API QR login")
        lqp._save_session(s)
    except Exception:
        pass  # 保存失败不影响返回

    with _qr_lock:
        info["done"] = True
        info["authorization"] = token

    return QrStatusResponse(
        success=True, scanned=True, pending=False,
        authorization=token,
    )


# ─── API: 智能 Token 获取 ───

@router.post("/token/ensure", response_model=EnsureResponse)
async def token_ensure() -> EnsureResponse:
    """智能获取 token：
    1) 现有 token 有效 → 直接返回（source=existing）
    2) 静默续期成功 → 返回新 token（source=refresh）
    3) 都不行 → 返回 qr_needed 标志，引导调用方走 /qr/start + /qr/status
    """
    # 1. 检查现有 token
    try:
        auth_file = ROOT / "packet_lab" / "out" / "runtime_auth_headers.json"
        if auth_file.exists():
            j = json.loads(auth_file.read_text(encoding="utf-8"))
            existing = j.get("headers", {}).get("Authorization", "")
            if existing and lqp.check_token_alive(existing):
                return EnsureResponse(
                    success=True, source="existing", authorization=existing,
                )
    except Exception:
        pass

    # 2. 静默续期
    try:
        token = lqp.refresh_token(verbose=False)
        if token:
            return EnsureResponse(
                success=True, source="refresh", authorization=token,
            )
    except Exception:
        pass

    # 3. 需要扫码
    return EnsureResponse(
        success=False,
        source="qr_needed",
        qr_hint={
            "next_step": "POST /api/auth/qr/start",
            "then": "GET /api/auth/qr/status?sid=<sid>",
            "note": "前端接 QR 图 base64 展示 → 每 3~5 秒轮询 status → 扫完返回 token",
        },
        reason="need_qr_scan",
        reason_detail="现有 token 无效 + 静默续期失败，需要扫码登录",
    )
