"""Phase 1 结构化错误分类。

所有 API 返回的 reason 统一归类到这些枚举值，前端可做针对性提示。
"""
from __future__ import annotations

from enum import Enum


class Phase1Error(str, Enum):
    # 名称相关
    NAME_PROHIBITED = "name_prohibited"        # resultType=1，含禁止词
    NAME_RESTRICTED = "name_restricted"        # resultType=2，含限制词
    NAME_CONFLICT = "name_conflict"            # 同名冲突过多
    NAME_PRECHECK_FAIL = "name_precheck_fail"  # 本地禁用词库拦截

    # 认证相关
    AUTH_EXPIRED = "auth_expired"              # Authorization 过期 / 无效
    AUTH_MISSING = "auth_missing"              # 未提供 Authorization

    # 服务端限制
    RATE_LIMITED = "rate_limited"              # D0029 操作频繁
    PRIVILEGE_DENIED = "privilege_denied"      # D0022 越权访问

    # 协议链步骤失败
    STEP_FAILED = "step_failed"               # 某步返回非 00000
    STEP7_NO_BUSI_ID = "step7_no_busi_id"     # 7 步全过但未拿到 busiId

    # 系统
    UPSTREAM_DOWN = "upstream_down"            # 远端 5xx / 超时
    INTERNAL_ERROR = "internal_error"          # 本服务内部异常


def classify_error(reason: str | None, steps: list | None = None) -> Phase1Error | None:
    """从 driver_adapter 返回的 reason 字符串推断错误枚举。"""
    if not reason:
        return None
    r = reason.lower()

    if "name_prohibited" in r:
        return Phase1Error.NAME_PROHIBITED
    if "name_restricted" in r:
        return Phase1Error.NAME_RESTRICTED
    if "name_conflict" in r:
        return Phase1Error.NAME_CONFLICT
    if "d0029" in r or "rate" in r:
        return Phase1Error.RATE_LIMITED
    if "d0022" in r or "privilege" in r:
        return Phase1Error.PRIVILEGE_DENIED
    if "401" in r or "403" in r or "auth" in r:
        return Phase1Error.AUTH_EXPIRED
    if "step7_no_busi_id" in r:
        return Phase1Error.STEP7_NO_BUSI_ID
    if "step" in r and "failed" in r:
        return Phase1Error.STEP_FAILED
    if "timeout" in r or "5xx" in r or "500" in r:
        return Phase1Error.UPSTREAM_DOWN

    return Phase1Error.INTERNAL_ERROR
