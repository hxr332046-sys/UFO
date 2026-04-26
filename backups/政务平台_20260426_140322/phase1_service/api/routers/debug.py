"""`/api/debug/*` — 开发辅助 API（mitm 样本查询 / 路径对照）。

仅在开发/联调时使用。

- `GET /api/debug/mitm/samples?api_pattern=X&opeType=Y&limit=5` 列出匹配的样本
- `GET /api/debug/mitm/latest?api_pattern=X` 最新一条样本（含 req + resp）
- `GET /api/debug/mitm/stats` mitm JSONL 概览（条数 / 成功 / 常见错误码）
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

ROOT = Path(__file__).resolve().parents[3]
MITM_JSONL = ROOT / "dashboard" / "data" / "records" / "mitm_ufo_flows.jsonl"

router = APIRouter(prefix="/api/debug", tags=["debug"])


def _iter_mitm_records(path: Path = MITM_JSONL):
    """生成器：逐行 yield mitm 记录。容忍 json 解析失败。"""
    if not path.exists():
        return
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                yield json.loads(line)
            except Exception:
                continue


def _extract_req_resp(rec: Dict[str, Any]) -> Dict[str, Any]:
    """解析一条记录，返回简化的视图。"""
    req = rec.get("req_body")
    resp = rec.get("resp_body")
    if isinstance(req, str):
        try:
            req = json.loads(req)
        except Exception:
            pass
    if isinstance(resp, str):
        try:
            resp = json.loads(resp)
        except Exception:
            pass
    if isinstance(resp, str):  # 双重编码
        try:
            resp = json.loads(resp)
        except Exception:
            pass
    code = None
    msg = None
    ope_type = None
    if isinstance(req, dict):
        ld = req.get("linkData")
        if isinstance(ld, dict):
            ope_type = ld.get("opeType")
    if isinstance(resp, dict):
        code = resp.get("code")
        msg = resp.get("msg")
    return {
        "ts": rec.get("ts"),
        "method": rec.get("method"),
        "url": rec.get("url"),
        "opeType": ope_type,
        "code": code,
        "msg": msg,
        "req_body": req,
        "resp_body": resp,
    }


@router.get("/mitm/samples")
async def list_samples(
    api_pattern: str = Query(..., description="URL 关键词，如 BasicInfo/operationBusinessDataInfo"),
    opeType: Optional[str] = Query(default=None, description="按 linkData.opeType 过滤，如 save/special"),
    code: Optional[str] = Query(default=None, description="按 resp code 过滤，如 00000"),
    limit: int = Query(default=5, ge=1, le=50),
) -> Dict[str, Any]:
    """列出匹配 api_pattern 的 mitm 记录（最新在前）。"""
    if not MITM_JSONL.exists():
        return {"success": False, "reason": "mitm_missing", "path": str(MITM_JSONL)}

    matches: List[Dict[str, Any]] = []
    pat = api_pattern.lower()
    for rec in _iter_mitm_records():
        url = str(rec.get("url") or "").lower()
        if pat not in url:
            continue
        view = _extract_req_resp(rec)
        if opeType and view.get("opeType") != opeType:
            continue
        if code and view.get("code") != code:
            continue
        matches.append(view)

    # 最新在前
    matches.sort(key=lambda v: v.get("ts") or 0, reverse=True)
    return {
        "success": True,
        "api_pattern": api_pattern,
        "opeType_filter": opeType,
        "code_filter": code,
        "total_matched": len(matches),
        "returned": min(limit, len(matches)),
        "items": matches[:limit],
    }


@router.get("/mitm/latest")
async def latest_sample(
    api_pattern: str = Query(..., description="URL 关键词"),
    opeType: Optional[str] = Query(default=None),
    only_success: bool = Query(default=True, description="仅返回 code=00000 的"),
) -> Dict[str, Any]:
    """返回最新一条匹配记录（完整 req + resp）。"""
    items = (await list_samples(api_pattern=api_pattern, opeType=opeType,
                                  code="00000" if only_success else None, limit=1)).get("items") or []
    if not items:
        return {
            "success": False,
            "reason": "no_match",
            "api_pattern": api_pattern,
        }
    return {
        "success": True,
        "api_pattern": api_pattern,
        "sample": items[0],
    }


@router.get("/mitm/stats")
async def mitm_stats() -> Dict[str, Any]:
    """统计 mitm JSONL 概览。"""
    if not MITM_JSONL.exists():
        return {"success": False, "reason": "mitm_missing", "path": str(MITM_JSONL)}

    total = 0
    methods: Dict[str, int] = {}
    codes: Dict[str, int] = {}
    top_apis: Dict[str, int] = {}
    size_mb = round(MITM_JSONL.stat().st_size / 1024 / 1024, 2)

    for rec in _iter_mitm_records():
        total += 1
        m = str(rec.get("method") or "")
        methods[m] = methods.get(m, 0) + 1
        url = str(rec.get("url") or "")
        # 提取 api 段
        if "/icpsp-api/" in url:
            tail = url.split("/icpsp-api/")[1].split("?")[0]
            # 拿最后两段
            parts = tail.split("/")
            api_tag = "/".join(parts[-2:]) if len(parts) >= 2 else tail
            top_apis[api_tag] = top_apis.get(api_tag, 0) + 1
        # 解 resp code
        resp = rec.get("resp_body")
        if isinstance(resp, str):
            try:
                resp = json.loads(resp)
            except Exception:
                resp = None
        if isinstance(resp, str):
            try:
                resp = json.loads(resp)
            except Exception:
                resp = None
        if isinstance(resp, dict):
            code = str(resp.get("code") or "")
            if code:
                codes[code] = codes.get(code, 0) + 1

    # 排序
    top_apis_sorted = sorted(top_apis.items(), key=lambda x: -x[1])[:15]
    codes_sorted = sorted(codes.items(), key=lambda x: -x[1])[:10]

    return {
        "success": True,
        "path": str(MITM_JSONL),
        "size_mb": size_mb,
        "total_records": total,
        "methods": methods,
        "top_codes": dict(codes_sorted),
        "top_apis": [{"api": a, "count": c} for a, c in top_apis_sorted],
    }
