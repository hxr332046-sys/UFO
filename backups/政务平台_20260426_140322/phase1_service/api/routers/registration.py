"""POST /api/phase1/register — 执行第一阶段协议链，返回 busiId。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from phase1_service.api.core.auth_manager import set_runtime_auth, validate_authorization, get_current_auth
from phase1_service.api.core.driver_adapter import drive_phase1
from phase1_service.api.core.rate_limiter import get_limiter
from phase1_service.api.core.errors import classify_error
from phase1_service.api.core.idempotency import get_cache
from phase1_service.api.schemas.case import RegisterRequest
from phase1_service.api.schemas.response import RegisterResponse, StepReport

router = APIRouter(prefix="/api/phase1", tags=["phase1"])


@router.post("/register", response_model=RegisterResponse)
async def register(req: RegisterRequest) -> RegisterResponse:
    # 1. Authorization 管理
    if req.authorization:
        if not validate_authorization(req.authorization):
            raise HTTPException(status_code=400, detail="Authorization 必须是 32 位十六进制")
        set_runtime_auth(req.authorization)
    else:
        if not get_current_auth():
            raise HTTPException(
                status_code=401,
                detail="未提供 Authorization，且服务器上没有有效 token（请登录政务服务后把 token 传入）",
            )

    # 2. 幂等性检查
    case_id = req.case.name_mark + "|" + "|".join(req.case.phase1_dist_codes)
    cache = get_cache()
    cached = cache.get(case_id)
    if cached and cached.get("success") and cached.get("busiId"):
        return RegisterResponse(
            success=True,
            busiId=cached["busiId"],
            hit_count=cached.get("hit_count"),
            checkState=cached.get("checkState"),
            similar_names=cached.get("similar_names") or [],
            steps=[StepReport(**s) for s in cached.get("steps", [])],
            latency_ms=0,
            reason=None,
            cached=True,
        )

    # 3. 令牌桶限流
    limiter = get_limiter()
    await limiter.acquire()

    # 4. 驱动器执行
    result = await drive_phase1(req.case.model_dump())

    # 5. 反馈限流
    if result.get("reason") and "D0029" in str(result.get("reason")):
        limiter.report_d0029()
    else:
        limiter.report_success()

    # 6. 错误分类
    error_code = None
    if not result.get("success"):
        err = classify_error(result.get("reason"), result.get("steps"))
        error_code = err.value if err else None

    # 7. 缓存成功结果
    if result.get("success") and result.get("busiId"):
        cache.put(case_id, result)

    return RegisterResponse(
        success=bool(result["success"]),
        busiId=result.get("busiId"),
        hit_count=result.get("hit_count"),
        checkState=result.get("checkState"),
        similar_names=result.get("similar_names") or [],
        steps=[StepReport(**s) for s in result.get("steps", [])],
        latency_ms=int(result.get("latency_ms", 0)),
        reason=result.get("reason"),
        reason_detail=result.get("reason_detail"),
        error_code=error_code,
    )
