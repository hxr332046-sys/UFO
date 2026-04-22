"""GET /api/phase1/scope — 经营范围查询（从本地 Tier D 普查数据）。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from phase1_service.api.schemas.response import (
    BusinessScopeItem,
    BusinessScopeResponse,
)

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "phase1_service/data"
SCOPE_DIR = DATA_DIR / "dictionaries/business_scopes"

router = APIRouter(prefix="/api/phase1/scope", tags=["business_scope"])


def _kw_hash(kw: str) -> str:
    return hashlib.md5(kw.encode("utf-8")).hexdigest()[:8]


def _parse_items_from_busidata(bd: Any, kw: str) -> List[BusinessScopeItem]:
    """按 queryIndustryFeatAndDes 的真实字段结构（2026-04-22 实测）解析：
    每条是 {hyCode, saveHyCode, hyPecul, hyTypeName, explains, includesTitle,
           includes, unIncludes, busiType, entType, isCustomHy}
    """
    items: List[BusinessScopeItem] = []
    if isinstance(bd, list):
        for row in bd:
            if not isinstance(row, dict):
                continue
            items.append(BusinessScopeItem(
                hyPecul=row.get("hyPecul") or kw,
                hyCode=row.get("hyCode"),
                saveHyCode=row.get("saveHyCode"),
                hyTypeName=row.get("hyTypeName"),
                includesTitle=row.get("includesTitle"),
                includes=row.get("includes"),
                unIncludes=row.get("unIncludes"),
                explains=row.get("explains"),
                busiType=row.get("busiType"),
                entType=row.get("entType"),
                isCustomHy=str(row.get("isCustomHy")) if row.get("isCustomHy") is not None else None,
                raw=row,
            ))
    elif isinstance(bd, dict):
        # 退化处理：嵌套 dict 里可能存 list
        for v in bd.values():
            if isinstance(v, list):
                items.extend(_parse_items_from_busidata(v, kw))
    return items


@router.get("", response_model=BusinessScopeResponse)
async def scope(
    entType: str = Query(..., description="企业类型，如 4540"),
    busiType: str = Query(default="01", description="业务类型，01/02"),
    keyword: str = Query(..., description="行业特征关键词，如 软件开发 / 食品"),
) -> BusinessScopeResponse:
    kw = keyword.strip()
    if not kw:
        raise HTTPException(status_code=400, detail="keyword 不能为空")

    subdir = SCOPE_DIR / f"entType_{entType}_busi_{busiType}"
    if not subdir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"经营范围普查数据缺失（{subdir.relative_to(ROOT)}），请先跑 Tier D 普查",
        )

    # 精确 hash 匹配
    hkey = _kw_hash(kw)
    exact = None
    for f in subdir.glob(f"{hkey}_*.json"):
        exact = f
        break

    files: List[Path] = []
    if exact and exact.exists():
        files = [exact]
    else:
        # 回退：在文件名里按关键词模糊匹配
        for f in subdir.iterdir():
            if f.is_file() and kw in f.name:
                files.append(f)

    if not files:
        raise HTTPException(
            status_code=404,
            detail=f"未找到 entType={entType} busiType={busiType} keyword='{kw}' 的普查数据",
        )

    all_items: List[BusinessScopeItem] = []
    for f in files:
        try:
            wrapper = json.loads(f.read_text(encoding="utf-8"))
            resp = wrapper.get("data") or {}
            bd = (resp.get("data") or {}).get("busiData") if isinstance(resp.get("data"), dict) else resp.get("busiData")
            if bd is None:
                # Support direct response
                bd = resp.get("busiData")
            if bd is None and isinstance(resp, dict) and "busiData" in (resp.get("data") or {}):
                bd = resp["data"]["busiData"]
            all_items.extend(_parse_items_from_busidata(bd, kw))
        except Exception:
            continue

    return BusinessScopeResponse(entType=entType, busiType=busiType, keyword=kw, items=all_items)
