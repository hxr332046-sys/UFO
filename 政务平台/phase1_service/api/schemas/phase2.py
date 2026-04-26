"""Phase 2 (信息补充 → 提交 → 设立 BasicInfo) 请求/响应 schema。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Phase2Case(BaseModel):
    """Phase 2 需要的 case 字段（兼容 docs/case_*.json 的结构）。"""

    # Phase 1 兼容字段（允许直接复用 Phase1Case 的 JSON）
    name_mark: Optional[str] = Field(default=None, description="字号，如 有为风")
    phase1_name_pre: Optional[str] = Field(default=None, description="名称前缀，如 广西容县")
    phase1_industry_code: Optional[str] = None
    phase1_industry_name: Optional[str] = None
    phase1_industry_special: Optional[str] = Field(default=None, description="经营范围关键词，如 软件开发")
    phase1_organize: Optional[str] = None
    phase1_dist_codes: List[str] = Field(default_factory=list, description="区划三级 code")
    phase1_check_name: Optional[str] = Field(default=None, description="完整企业名")

    # Phase 2 必需
    company_name_phase1_normalized: Optional[str] = Field(default=None, description="完整企业名（phase1_check_name 的别名）")
    entType_default: str = Field(default="4540")
    busiType_default: str = Field(default="02_4")

    # 投资人/承办人
    person: Dict[str, Any] = Field(default_factory=dict, description="投资人/承办人字段：name / mobile / id_no / email")

    # 兜底允许任意字段（case.json 里还有 address_full / assets 等）
    model_config = {"extra": "allow"}


class Phase2RegisterRequest(BaseModel):
    """POST /api/phase2/register 请求体。

    两种使用模式：
    - 模式 A（推荐）：服务器已持有 Phase 1 的 busi_id（最近一次跑过），只传 case 即可
    - 模式 B：客户端显式传入 busi_id / name_id
    """

    case: Phase2Case
    authorization: Optional[str] = Field(default=None, description="32-hex token；留空则用服务器最新抓包")
    busi_id: Optional[str] = Field(default=None, description="Phase 1 busiId；留空自动读 phase1_protocol_driver_latest.json")
    name_id: Optional[str] = Field(default=None, description="可选：跳过 step 9 时预填")
    stop_after: int = Field(default=14, ge=1, le=28, description="跑到第几步停（默认 14：BasicInfo load；15=BasicInfo save；25=4540终点/28=1151终点）")
    start_from: int = Field(default=1, ge=1, le=28, description="从第几步开始（断点续跑）")
    auto_phase1: bool = Field(default=False, description="当缺 busi_id 时自动先跑 Phase 1")


class Phase2StepReport(BaseModel):
    i: int
    name: str
    ok: bool
    code: Optional[str] = None
    resultType: Optional[str] = None
    msg: Optional[str] = None
    err: Optional[str] = None
    duration_ms: Optional[int] = None
    busiData_preview: Optional[str] = None


class Phase2RegisterResponse(BaseModel):
    success: bool
    busiId: Optional[str] = None
    nameId: Optional[str] = None
    establish_busiId: Optional[str] = None
    basicinfo_signInfo: Optional[str] = None
    stopped_at_step: int = 0
    steps: List[Phase2StepReport] = Field(default_factory=list)
    latency_ms: int
    reason: Optional[str] = None
    reason_detail: Optional[str] = None

    # Phase 1 联跑时的信息
    phase1_executed: bool = False
    phase1_busiId: Optional[str] = None
    phase1_reason: Optional[str] = None
