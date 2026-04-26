"""POST /api/phase2/register — 执行第二阶段协议链，默认到 step 14 BasicInfo load。

流程:
  1. 验证/设置 Authorization
  2. 解析 busi_id（请求传入 > 最新 phase1 文件 > 可选自动 Phase 1）
  3. 幂等检查（5 分钟内同参数命中返回缓存）
  4. 限流
  5. 执行 phase2_adapter.drive_phase2()
  6. 如果 session_expired → 尝试 session_recovery → 重试一次
  7. 返回结构化结果
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import time

from fastapi import APIRouter, HTTPException, Query

from phase1_service.api.core.auth_manager import (
    get_current_auth,
    set_runtime_auth,
    validate_authorization,
)
from phase1_service.api.core.driver_adapter import drive_phase1
from phase1_service.api.core.errors import classify_error
from phase1_service.api.core.phase2_adapter import drive_phase2
from phase1_service.api.core.phase2_idempotency import get_phase2_cache
from phase1_service.api.core.rate_limiter import get_limiter
from phase1_service.api.core.session_recovery import recover_session_async
from phase1_service.api.schemas.phase2 import (
    Phase2RegisterRequest,
    Phase2RegisterResponse,
    Phase2StepReport,
)

router = APIRouter(prefix="/api/phase2", tags=["phase2"])


@router.post("/session/recover")
async def recover_session() -> Dict[str, Any]:
    """手动触发 session 自愈：从 CDP 9225 浏览器同步 Authorization + cookies。

    使用场景：
    - 客户端收到 session_expired 但不想依赖 /register 的自动重试
    - 运维确认浏览器已重新登录后，主动刷新 Python 会话
    """
    result = await recover_session_async()
    return result


@router.get("/cache/stats")
async def cache_stats() -> Dict[str, Any]:
    """幂等缓存统计（便于观察缓存命中率）。"""
    return get_phase2_cache().stats()


@router.get("/progress")
async def progress(
    busi_id: str = Query(..., description="办件 busiId"),
    name_id: str = Query(..., description="对应 nameId"),
    ent_type: str = Query(default="4540"),
    busi_type: str = Query(default="02_4"),
) -> Dict[str, Any]:
    """查询 establish 当前位置（currCompUrl + status + busiCompComb）。

    不依赖 Phase 2 驱动的完整链路，只发一次 establish/loadCurrentLocationInfo。
    适用于断点续跑前先确认"我在哪一步"。
    """
    import sys as _sys
    from pathlib import Path as _P
    _sys.path.insert(0, str(_P(__file__).resolve().parents[3] / "system"))
    from icpsp_api_client import ICPSPClient as _C  # type: ignore

    client = _C()
    body = {
        "flowData": {
            "busiId": busi_id,
            "entType": ent_type,
            "busiType": busi_type,
            "ywlbSign": "4",
            "busiMode": None,
            "nameId": name_id,
            "marPrId": None,
            "secondId": None,
            "vipChannel": None,
        },
        "linkData": {"continueFlag": "continueFlag", "token": ""},
    }
    try:
        r = client.post_json(
            "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
            body,
            extra_headers={"Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html"},
        )
    except Exception as e:
        return {
            "success": False,
            "reason": "http_error",
            "reason_detail": f"{type(e).__name__}: {str(e)[:200]}",
        }

    code = r.get("code")
    if code != "00000":
        return {
            "success": False,
            "reason": f"code_{code}",
            "reason_detail": str(r.get("msg") or "")[:200],
            "busi_id": busi_id,
        }

    bd = (r.get("data") or {}).get("busiData") or {}
    fd = bd.get("flowData") or {}
    bcc = bd.get("busiCompComb") or {}
    return {
        "success": True,
        "busi_id": busi_id,
        "name_id": name_id,
        "currCompUrl": fd.get("currCompUrl"),
        "status": fd.get("status"),
        "busiCompComb": {
            "id": bcc.get("id") if isinstance(bcc, dict) else None,
            "compUrl": bcc.get("compUrl") if isinstance(bcc, dict) else None,
        },
        "flowData": fd,
    }


ROOT = Path(__file__).resolve().parents[3]
PHASE1_LATEST = ROOT / "dashboard" / "data" / "records" / "phase1_protocol_driver_latest.json"


def _read_phase1_latest_busi_id() -> str | None:
    if not PHASE1_LATEST.exists():
        return None
    try:
        data = json.loads(PHASE1_LATEST.read_text(encoding="utf-8"))
        bid = ((data.get("final") or {}).get("busi_id")) or None
        return str(bid) if bid else None
    except Exception:
        return None


def _case_to_phase1_dict(case_dict: Dict[str, Any]) -> Dict[str, Any] | None:
    """把 Phase2Case 转成 Phase1Case 期望的字段结构。缺字段则返回 None。"""
    required = [
        "name_mark", "phase1_industry_code", "phase1_industry_name",
        "phase1_industry_special", "phase1_organize", "phase1_dist_codes",
    ]
    for k in required:
        if not case_dict.get(k):
            return None
    return {
        "name_mark": case_dict["name_mark"],
        "phase1_name_pre": case_dict.get("phase1_name_pre") or "广西容县",
        "phase1_industry_code": case_dict["phase1_industry_code"],
        "phase1_industry_name": case_dict["phase1_industry_name"],
        "phase1_industry_special": case_dict["phase1_industry_special"],
        "phase1_organize": case_dict["phase1_organize"],
        "phase1_dist_codes": list(case_dict["phase1_dist_codes"]),
        "phase1_check_name": case_dict.get("phase1_check_name") or case_dict.get("company_name_phase1_normalized"),
        "entType_default": case_dict.get("entType_default") or "4540",
        "busiType_default": case_dict.get("busiType_default") or "02_4",
        "phase1_main_business_desc": case_dict.get("phase1_main_business_desc") or case_dict.get("phase1_industry_special"),
    }


@router.post("/register", response_model=Phase2RegisterResponse)
async def register_phase2(req: Phase2RegisterRequest) -> Phase2RegisterResponse:
    # 1. Authorization
    if req.authorization:
        if not validate_authorization(req.authorization):
            raise HTTPException(status_code=400, detail="Authorization 必须是 32 位十六进制")
        set_runtime_auth(req.authorization)
    else:
        if not get_current_auth():
            raise HTTPException(
                status_code=401,
                detail="未提供 Authorization，且服务器上没有有效 token",
            )

    case_dict: Dict[str, Any] = req.case.model_dump()

    # 2. 解析 busi_id
    busi_id = req.busi_id or _read_phase1_latest_busi_id()

    phase1_executed = False
    phase1_busiId: str | None = None
    phase1_reason: str | None = None

    if not busi_id and req.auto_phase1:
        # 尝试自动跑 Phase 1
        p1_case = _case_to_phase1_dict(case_dict)
        if p1_case is None:
            raise HTTPException(
                status_code=400,
                detail="auto_phase1=True 但 case 缺少 Phase 1 必需字段（name_mark / phase1_industry_code / phase1_dist_codes 等）",
            )
        limiter = get_limiter()
        await limiter.acquire()
        p1 = await drive_phase1(p1_case)
        phase1_executed = True
        if p1.get("reason") and "D0029" in str(p1.get("reason")):
            limiter.report_d0029()
        else:
            limiter.report_success()
        phase1_busiId = p1.get("busiId")
        phase1_reason = p1.get("reason")
        if not phase1_busiId:
            return Phase2RegisterResponse(
                success=False,
                busiId=None,
                stopped_at_step=0,
                steps=[],
                latency_ms=int(p1.get("latency_ms", 0)),
                reason="phase1_failed",
                reason_detail=f"Phase 1 未能拿到 busiId: {phase1_reason}",
                phase1_executed=True,
                phase1_busiId=None,
                phase1_reason=phase1_reason,
            )
        busi_id = phase1_busiId

    if not busi_id:
        raise HTTPException(
            status_code=400,
            detail="缺少 busi_id：请传 busi_id 参数、先跑 Phase 1 写入 phase1_protocol_driver_latest.json、或传 auto_phase1=true",
        )

    # 3. 幂等缓存检查
    cache = get_phase2_cache()
    idem_key = cache.make_key(
        case_dict, busi_id,
        start_from=req.start_from, stop_after=req.stop_after,
        name_id=req.name_id,
    )
    cached = cache.get(idem_key)
    if cached and cached.get("success"):
        return Phase2RegisterResponse(
            success=True,
            busiId=cached.get("busiId"),
            nameId=cached.get("nameId"),
            establish_busiId=cached.get("establish_busiId"),
            basicinfo_signInfo=cached.get("basicinfo_signInfo"),
            stopped_at_step=int(cached.get("stopped_at_step") or 0),
            steps=[Phase2StepReport(**s) for s in cached.get("steps", [])],
            latency_ms=0,
            reason="cached",
            reason_detail=f"幂等缓存命中（TTL 内的重复请求）",
            phase1_executed=phase1_executed,
            phase1_busiId=phase1_busiId,
            phase1_reason=phase1_reason,
        )

    # 4. 限流
    limiter = get_limiter()
    await limiter.acquire()

    # 5. 执行
    result = await drive_phase2(
        case_dict=case_dict,
        busi_id=busi_id,
        stop_after=req.stop_after,
        start_from=req.start_from,
        preset_name_id=req.name_id,
    )

    # 6. session_expired 自愈重试（一次）
    if result.get("reason") == "session_expired":
        recovery = await recover_session_async()
        if recovery.get("ok"):
            # 恢复成功 → 重试
            result = await drive_phase2(
                case_dict=case_dict,
                busi_id=busi_id,
                stop_after=req.stop_after,
                start_from=req.start_from,
                preset_name_id=req.name_id,
            )
            result["_session_recovered"] = True
        else:
            # 恢复失败（浏览器在 SSO 登录页等）→ 在 reason_detail 加恢复提示
            result["reason_detail"] = (
                f"{result.get('reason_detail') or ''} | session 自愈失败：{recovery.get('hint') or recovery.get('reason')}"
            ).strip(" |")

    # 7. 反馈限流
    reason = result.get("reason") or ""
    if "rate_limit" in reason or "D0029" in str(result.get("reason_detail") or ""):
        limiter.report_d0029()
    else:
        limiter.report_success()

    # 8. 成功则写幂等缓存
    if result.get("success"):
        try:
            cache.put(idem_key, {
                "success": True,
                "busiId": result.get("busiId"),
                "nameId": result.get("nameId"),
                "establish_busiId": result.get("establish_busiId"),
                "basicinfo_signInfo": result.get("basicinfo_signInfo"),
                "stopped_at_step": result.get("stopped_at_step"),
                "steps": result.get("steps", []),
            })
        except Exception:
            pass

    return Phase2RegisterResponse(
        success=bool(result.get("success")),
        busiId=result.get("busiId"),
        nameId=result.get("nameId"),
        establish_busiId=result.get("establish_busiId"),
        basicinfo_signInfo=result.get("basicinfo_signInfo"),
        stopped_at_step=int(result.get("stopped_at_step") or 0),
        steps=[Phase2StepReport(**s) for s in result.get("steps", [])],
        latency_ms=int(result.get("latency_ms", 0)),
        reason=result.get("reason"),
        reason_detail=result.get("reason_detail"),
        phase1_executed=phase1_executed,
        phase1_busiId=phase1_busiId,
        phase1_reason=phase1_reason,
    )
