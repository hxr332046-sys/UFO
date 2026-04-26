"""Authorization 健康检查端点。"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..core.auth_manager import get_current_auth, RUNTIME_AUTH_JSON

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "system"))

router = APIRouter(prefix="/api/phase1", tags=["auth"])


class AuthStatusResponse(BaseModel):
    valid: bool = Field(..., description="当前是否有可用 Authorization")
    token_preview: Optional[str] = Field(None, description="token 前 8 位（脱敏）")
    token_age_sec: Optional[int] = Field(None, description="token 写入时间距今（秒）")
    remote_ok: Optional[bool] = Field(None, description="如果做了实网探测，远端是否有效")
    remote_msg: Optional[str] = None


def _probe_auth() -> dict:
    """同步探测：用当前 auth 请求一个轻量 API 看是否有效。"""
    try:
        from icpsp_api_client import ICPSPClient  # type: ignore
        client = ICPSPClient()
        resp = client.get_json(
            "/icpsp-api/v4/pc/common/configdata/getSerialTypeCode", {}
        )
        code = str(resp.get("code") or "")
        if code == "00000":
            return {"ok": True, "msg": "token 有效"}
        elif "D0022" in code or "GS52" in code:
            return {"ok": False, "msg": f"认证失效 ({code})"}
        else:
            return {"ok": False, "msg": f"code={code}"}
    except Exception as e:
        return {"ok": False, "msg": str(e)[:200]}


@router.get("/auth/status", response_model=AuthStatusResponse)
async def auth_status(probe: bool = False) -> AuthStatusResponse:
    """检查当前 Authorization 是否有效。

    - probe=false：只看本地文件（0ms）
    - probe=true：额外发一个轻量请求实网校验（~200ms）
    """
    token = get_current_auth()
    age = None

    if RUNTIME_AUTH_JSON.exists():
        try:
            d = json.loads(RUNTIME_AUTH_JSON.read_text(encoding="utf-8"))
            ts = d.get("ts")
            if isinstance(ts, (int, float)):
                age = int(time.time() - ts)
        except Exception:
            pass

    result = AuthStatusResponse(
        valid=token is not None,
        token_preview=token[:8] + "..." if token else None,
        token_age_sec=age,
    )

    if probe and token:
        r = await asyncio.get_event_loop().run_in_executor(None, _probe_auth)
        result.remote_ok = r.get("ok")
        result.remote_msg = r.get("msg")
        # 如果远端返回失效，标记 valid=False
        if result.remote_ok is False:
            result.valid = False

    return result


class KeepaliveResponse(BaseModel):
    alive: bool
    token_preview: Optional[str] = None
    user_name: Optional[str] = None
    ping_ok: bool = False
    business_ok: bool = False
    age_sec: Optional[int] = None
    msg: str = ""


@router.post("/auth/keepalive", response_model=KeepaliveResponse)
async def auth_keepalive() -> KeepaliveResponse:
    """执行一次保活 ping（维持 token 活跃 + 返回健康状态）。

    LLM/CLI 应每 2-3 分钟调用一次此端点来防止 token 过期。
    """
    token = get_current_auth()
    if not token:
        return KeepaliveResponse(alive=False, msg="no_token")

    def _do_keepalive():
        try:
            from auth_keepalive_service import check_token_health
            return check_token_health()
        except Exception as e:
            return {"error": str(e)}

    result = await asyncio.get_event_loop().run_in_executor(None, _do_keepalive)

    if isinstance(result, dict) and "error" in result:
        return KeepaliveResponse(
            alive=False,
            token_preview=token[:8] + "..." if token else None,
            msg=f"keepalive_error: {result['error']}"
        )

    age = None
    if RUNTIME_AUTH_JSON.exists():
        try:
            d = json.loads(RUNTIME_AUTH_JSON.read_text(encoding="utf-8"))
            ts = d.get("ts")
            if isinstance(ts, (int, float)):
                age = int(time.time() - ts)
        except Exception:
            pass

    return KeepaliveResponse(
        alive=result.alive,
        token_preview=result.token_preview,
        user_name=result.user_name,
        ping_ok=result.ping_ok,
        business_ok=result.business_ok,
        age_sec=age,
        msg="alive" if result.alive else result.error,
    )
