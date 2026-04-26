"""GET /api/phase1/dict/* — 从本地普查数据读字典。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from phase1_service.api.schemas.response import DictionaryResponse

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "phase1_service/data"
DICT_DIR = DATA_DIR / "dictionaries"

router = APIRouter(prefix="/api/phase1/dict", tags=["dict"])


def _read_dict(relative: str) -> Optional[Dict[str, Any]]:
    p = DICT_DIR / relative
    if not p.exists():
        return None
    try:
        wrapper = json.loads(p.read_text(encoding="utf-8"))
        data = wrapper.get("data") or wrapper
        bd = (data.get("data") or {}).get("busiData") if isinstance(data.get("data"), dict) else data.get("busiData")
        if bd is None and isinstance(data, dict):
            # wrapper.data.busiData
            inner = data.get("busiData")
            if inner is None:
                inner = data.get("data", {}).get("busiData") if isinstance(data.get("data"), dict) else None
            bd = inner
        meta = wrapper.get("meta") or {}
        count = len(bd) if isinstance(bd, list) else None
        return {
            "cache_path": str(p.relative_to(ROOT)),
            "ts": meta.get("ts"),
            "busiData": bd,
            "count": count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"字典解析失败: {e!r}")


@router.get("/ent-types", response_model=DictionaryResponse)
async def ent_types(level: int = Query(default=1, ge=1, le=2)) -> DictionaryResponse:
    r = _read_dict(f"ent_types_type{level}.json")
    if r is None:
        raise HTTPException(status_code=404, detail=f"ent_types_type{level}.json 不存在，请先跑 Tier A 普查")
    return DictionaryResponse(source="local_census", **r)


@router.get("/industries/{entType}", response_model=DictionaryResponse)
async def industries(entType: str, busiType: str = Query(default="01")) -> DictionaryResponse:
    r = _read_dict(f"industries/entType_{entType}_busi_{busiType}.json")
    if r is None:
        raise HTTPException(status_code=404, detail=f"industries/entType_{entType}_busi_{busiType}.json 不存在，请先跑 Tier B")
    return DictionaryResponse(source="local_census", **r)


@router.get("/organizes/{entType}", response_model=DictionaryResponse)
async def organizes(entType: str, busiType: str = Query(default="01")) -> DictionaryResponse:
    r = _read_dict(f"organizes/entType_{entType}_busi_{busiType}.json")
    if r is None:
        raise HTTPException(status_code=404, detail=f"organizes/entType_{entType}_busi_{busiType}.json 不存在")
    return DictionaryResponse(source="local_census", **r)


@router.get("/regions")
async def regions() -> DictionaryResponse:
    r = _read_dict("regions/root.json")
    if r is None:
        raise HTTPException(status_code=404, detail="regions/root.json 不存在")
    return DictionaryResponse(source="local_census", **r)


@router.get("/name-prefixes/{distCode}/{entType}")
async def name_prefixes(distCode: str, entType: str) -> DictionaryResponse:
    r = _read_dict(f"name_prefixes/dist_{distCode}_entType_{entType}.json")
    if r is None:
        raise HTTPException(status_code=404, detail=f"name_prefixes dist={distCode} entType={entType} 不存在")
    return DictionaryResponse(source="local_census", **r)
