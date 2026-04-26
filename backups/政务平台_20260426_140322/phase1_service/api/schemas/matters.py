"""Pydantic schemas for /api/matters/*."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MatterItem(BaseModel):
    """办件列表单项。"""
    id: Optional[str] = None
    entName: Optional[str] = None
    nameId: Optional[str] = None
    entType: Optional[str] = None
    busiType: Optional[str] = None
    matterTypeCode: Optional[str] = None
    matterTypeName: Optional[str] = None
    matterStateCode: Optional[str] = None
    matterStateName: Optional[str] = None
    listMatterStateCode: Optional[str] = None
    listMatterStateLangCode: Optional[str] = None
    flowType: Optional[str] = None
    ywlbSign: Optional[str] = None
    legalName: Optional[str] = None
    marUniscId: Optional[str] = None

    class Config:
        extra = "allow"  # 其他未声明字段保留


class MattersListResponse(BaseModel):
    """`GET /api/matters/list` 响应。"""
    success: bool
    total: int = 0
    items: List[MatterItem] = Field(default_factory=list)
    reason: Optional[str] = None
    reason_detail: Optional[str] = None


class MatterDeleteResponse(BaseModel):
    """`POST /api/matters/delete` 响应。"""
    success: bool
    deleted: int = 0
    failed: int = 0
    details: List[Dict[str, Any]] = Field(default_factory=list)
    reason: Optional[str] = None
    reason_detail: Optional[str] = None


class MatterDetailResponse(BaseModel):
    """`GET /api/matters/detail` 响应：同时返回办件基本信息 + establish 位置信息。"""
    success: bool
    busi_id: Optional[str] = None
    entName: Optional[str] = None
    nameId: Optional[str] = None
    busiType: Optional[str] = None
    entType: Optional[str] = None
    status: Optional[str] = None
    currCompUrl: Optional[str] = None  # 来自 establish/loadCurrentLocationInfo
    establish_status: Optional[str] = None  # 来自 establish 的 flowData.status
    raw_matter: Optional[Dict[str, Any]] = None  # 完整办件信息
    reason: Optional[str] = None
    reason_detail: Optional[str] = None
