"""响应体 schema。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StepReport(BaseModel):
    name: str
    ok: bool
    code: str
    result_type: str
    msg: Optional[str] = None
    server_msg: Optional[str] = None
    duration_ms: Optional[int] = None
    extracted: Dict[str, Any] = Field(default_factory=dict)


class RegisterResponse(BaseModel):
    success: bool
    busiId: Optional[str] = None
    hit_count: Optional[int] = None
    checkState: Optional[int] = None
    similar_names: List[Dict[str, Any]] = Field(default_factory=list)
    steps: List[StepReport] = Field(default_factory=list)
    latency_ms: int
    reason: Optional[str] = None
    reason_detail: Optional[str] = None
    error_code: Optional[str] = Field(default=None, description="Phase1Error 枚举值")
    cached: bool = Field(default=False, description="是否命中幂等缓存")


class DictionaryResponse(BaseModel):
    source: str = Field(..., description="字典来源：local_census / live_fallback")
    cache_path: Optional[str] = None
    ts: Optional[int] = None
    busiData: Any = None
    count: Optional[int] = None


class BusinessScopeItem(BaseModel):
    """单条经营范围条目（对应 queryIndustryFeatAndDes 返回的一行）。"""
    hyPecul: str = Field(..., description="匹配的关键词")
    hyCode: Optional[str] = Field(default=None, description="行业码，如 A0190")
    saveHyCode: Optional[str] = Field(default=None, description="保存用行业码")
    hyTypeName: Optional[str] = Field(default=None, description="行业类型名称，如 '其他农业'")
    includesTitle: Optional[str] = Field(default=None, description="包含项标题")
    includes: Optional[str] = Field(default=None, description="★ 经营范围主描述（可直接作为执照上的经营范围文本）")
    unIncludes: Optional[str] = Field(default=None, description="不包含项说明")
    explains: Optional[str] = Field(default=None, description="补充解释")
    busiType: Optional[str] = Field(default=None, description="适用业务类型")
    entType: Optional[str] = Field(default=None, description="适用企业类型")
    isCustomHy: Optional[str] = None
    raw: Dict[str, Any] = Field(default_factory=dict)


class BusinessScopeResponse(BaseModel):
    entType: str
    busiType: str
    keyword: str
    items: List[BusinessScopeItem] = Field(default_factory=list)
    source: str = "local_census"
