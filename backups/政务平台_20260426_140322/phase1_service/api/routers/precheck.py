"""POST /api/phase1/precheck_name

名字预检 —— 在跑 7 步 API 前先 ~200ms 判定名字能不能用，节省网络和时间。

两级校验：
  1) 本地禁用词库（必校验，~0ms）
  2) 服务端 bannedLexiconCalibration（可选，remote=true，~100-300ms）
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.banned_words_loader import check_banned
from ..core.auth_manager import (
    validate_authorization,
    set_runtime_auth,
    get_current_auth,
)

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "system"))

router = APIRouter(prefix="/api/phase1", tags=["precheck"])


class PrecheckRequest(BaseModel):
    name_mark: str = Field(..., description="企业字号（如 李陈梦、裕鑫）", min_length=1, max_length=30)
    remote: bool = Field(False, description="是否调服务端 bannedLexiconCalibration 实网校验（需要有效 Authorization）")
    authorization: Optional[str] = Field(None, description="可选：32-hex Authorization，remote=true 时用")


class PrecheckResponse(BaseModel):
    name_mark: str
    verdict: str = Field(..., description="ok / restricted / prohibited / region_name")
    local_matched: List[str] = Field(default_factory=list, description="本地词库命中的词")
    local_category: Optional[str] = None
    remote_checked: bool = False
    remote_msg: Optional[str] = None
    remote_success: Optional[bool] = None
    latency_ms: int = 0


def _call_banned_lexicon(name_mark: str, authorization: Optional[str]) -> Dict[str, Any]:
    """同步调 bannedLexiconCalibration，返回 {ok, msg, success}"""
    from icpsp_api_client import ICPSPClient  # type: ignore

    client = ICPSPClient()
    resp = client.get_json(
        "/icpsp-api/v4/pc/register/verifidata/bannedLexiconCalibration",
        {"nameMark": name_mark},
    )
    code = str(resp.get("code") or "")
    data = resp.get("data") or {}
    bd = data.get("busiData") or {}
    success = bd.get("success")
    tip = str(bd.get("tipStr") or "") or str(data.get("msg") or "")
    return {
        "ok": code == "00000",
        "code": code,
        "msg": tip,
        "success": bool(success) if isinstance(success, bool) else success,
    }


@router.post("/precheck_name", response_model=PrecheckResponse)
async def precheck_name(req: PrecheckRequest) -> PrecheckResponse:
    started = time.time()

    # 1) 本地词库校验
    is_banned, matched, cat = check_banned(req.name_mark)

    if is_banned:
        # 本地已拦截，无需远程调用
        verdict = "prohibited" if cat == "prohibited" else "region_name"
        return PrecheckResponse(
            name_mark=req.name_mark,
            verdict=verdict,
            local_matched=matched,
            local_category=cat,
            remote_checked=False,
            latency_ms=int((time.time() - started) * 1000),
        )

    # 2) 本地仅 warn（限制词）或 ok
    verdict = "restricted" if matched else "ok"

    # 3) 可选实网校验
    remote_msg = None
    remote_success = None
    remote_checked = False

    if req.remote:
        if req.authorization:
            if not validate_authorization(req.authorization):
                raise HTTPException(status_code=400, detail="Authorization 必须是 32 位十六进制")
            set_runtime_auth(req.authorization)
        elif not get_current_auth():
            raise HTTPException(
                status_code=401,
                detail="remote=true 但未提供 Authorization，服务器也没有有效 token",
            )
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, _call_banned_lexicon, req.name_mark, req.authorization
            )
            remote_checked = True
            remote_msg = result.get("msg")
            remote_success = result.get("success")
            # 服务端判定覆盖本地 verdict
            if remote_success is False:
                verdict = "prohibited"
            elif remote_msg:
                # 有 tipStr 但 success=True 意味着"有警告但可用"
                verdict = "restricted" if verdict == "ok" else verdict
        except Exception as e:
            remote_msg = f"remote check failed: {e!r}"

    return PrecheckResponse(
        name_mark=req.name_mark,
        verdict=verdict,
        local_matched=matched,
        local_category=cat,
        remote_checked=remote_checked,
        remote_msg=remote_msg,
        remote_success=remote_success,
        latency_ms=int((time.time() - started) * 1000),
    )
