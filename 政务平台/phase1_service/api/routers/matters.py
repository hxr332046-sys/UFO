"""`/api/matters/*` — "我的办件"列表与详情。

复用 `icpsp_api_client.ICPSPClient`（自动带 Authorization + cookies）。

数据源：`GET /icpsp-api/v4/pc/manager/mattermanager/matters/search`
  Query: searchText / pageNum / pageSize / matterTypeCode / matterStateCode / timeRange / useType

- useType=0 表示"我的办件"（个人视角）
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "system"))

from icpsp_api_client import ICPSPClient  # noqa: E402

from phase1_service.api.schemas.matters import (  # noqa: E402
    MatterItem,
    MattersListResponse,
    MatterDeleteResponse,
    MatterDetailResponse,
)

router = APIRouter(prefix="/api/matters", tags=["matters"])

MATTERS_SEARCH = "/icpsp-api/v4/pc/manager/mattermanager/matters/search"
MATTERS_OPERATE = "/icpsp-api/v4/pc/manager/mattermanager/matters/operate"


def _search_matters(
    client: ICPSPClient,
    *,
    search_text: str = "",
    page_num: int = 1,
    page_size: int = 10,
    matter_type_code: str = "",
    matter_state_code: str = "",
    use_type: str = "0",
) -> Dict[str, Any]:
    params = {
        "searchText": search_text,
        "pageNum": page_num,
        "pageSize": page_size,
        "matterTypeCode": matter_type_code,
        "matterStateCode": matter_state_code,
        "timeRange": "",
        "useType": use_type,
        "t": int(time.time() * 1000),
    }
    return client.get_json(MATTERS_SEARCH, params=params)


@router.get("/list", response_model=MattersListResponse)
async def list_matters(
    search: str = Query(default="", description="按关键字过滤（企业名/法人等）"),
    page: int = Query(default=1, ge=1, le=50),
    size: int = Query(default=10, ge=1, le=50),
    state: str = Query(default="", description="状态过滤（matterStateCode）"),
) -> MattersListResponse:
    """列出当前用户的办件。"""
    client = ICPSPClient()
    try:
        resp = _search_matters(
            client,
            search_text=search,
            page_num=page,
            page_size=size,
            matter_state_code=state,
        )
    except Exception as e:
        return MattersListResponse(
            success=False,
            reason="http_error",
            reason_detail=f"{type(e).__name__}: {str(e)[:200]}",
        )

    code = resp.get("code")
    if code != "00000":
        return MattersListResponse(
            success=False,
            reason=f"code_{code}",
            reason_detail=str(resp.get("msg") or "")[:200],
        )

    data = resp.get("data") or {}
    busi_data = data.get("busiData") or []
    if not isinstance(busi_data, list):
        busi_data = []

    items = [MatterItem(**it) for it in busi_data if isinstance(it, dict)]
    return MattersListResponse(
        success=True,
        total=len(items),
        items=items,
    )


def _delete_one(client: ICPSPClient, busi_id: str) -> Dict[str, Any]:
    """删除单条办件: before → operate。返回 {busi_id, success, msg}。"""
    result: Dict[str, Any] = {"busi_id": busi_id, "success": False, "msg": ""}
    try:
        r1 = client.post_json(MATTERS_OPERATE, {
            "busiId": busi_id, "btnCode": "103", "dealFlag": "before",
        })
        if r1.get("code") != "00000":
            result["msg"] = f"before failed: {r1.get('code')} {r1.get('msg', '')}"
            return result
    except Exception as e:
        result["msg"] = f"before error: {e}"
        return result

    try:
        r2 = client.post_json(MATTERS_OPERATE, {
            "busiId": busi_id, "btnCode": "103", "dealFlag": "operate",
        })
        code2 = r2.get("code")
        data2 = r2.get("data") or {}
        rt = data2.get("resultType")
        msg2 = data2.get("msg") or r2.get("msg", "")
        result["msg"] = msg2
        if code2 == "00000" and str(rt) == "0":
            result["success"] = True
        else:
            result["msg"] = f"operate: code={code2} rt={rt} {msg2}"
    except Exception as e:
        result["msg"] = f"operate error: {e}"
    return result


@router.post("/delete", response_model=MatterDeleteResponse)
async def delete_matter(
    busi_id: str = Query(default="", description="单个 busiId（与 search 二选一）"),
    search: str = Query(default="", description="按企业名搜索并批量删除"),
    confirm: str = Query(default="", description="安全确认：必须等于 busi_id 或 'DELETE'"),
) -> MatterDeleteResponse:
    """删除办件。支持单个 busi_id 或 search 批量删除。\n\n    安全机制：confirm 必须等于 busi_id（单个）或 'DELETE'（批量）。"""
    client = ICPSPClient()

    if busi_id and confirm == busi_id:
        r = _delete_one(client, busi_id)
        return MatterDeleteResponse(
            success=r["success"],
            deleted=1 if r["success"] else 0,
            failed=0 if r["success"] else 1,
            details=[r],
        )

    if search and confirm == "DELETE":
        try:
            resp = _search_matters(client, search_text=search, page_size=50)
        except Exception as e:
            return MatterDeleteResponse(
                success=False, reason="search_error",
                reason_detail=f"{type(e).__name__}: {str(e)[:200]}",
            )
        if resp.get("code") != "00000":
            return MatterDeleteResponse(
                success=False, reason=f"search_code_{resp.get('code')}",
                reason_detail=str(resp.get("msg") or "")[:200],
            )
        items = (resp.get("data") or {}).get("busiData") or []
        targets = [
            str(it.get("id"))
            for it in items
            if isinstance(it, dict) and search in (it.get("entName") or "")
        ]
        if not targets:
            return MatterDeleteResponse(success=True, deleted=0, reason="no_match")

        details = []
        deleted = 0
        for bid in targets:
            r = _delete_one(client, bid)
            details.append(r)
            if r["success"]:
                deleted += 1
        return MatterDeleteResponse(
            success=deleted > 0,
            deleted=deleted,
            failed=len(targets) - deleted,
            details=details,
        )

    return MatterDeleteResponse(
        success=False, reason="confirm_mismatch",
        reason_detail="confirm 必须等于 busi_id（单个）或 'DELETE'（批量搜索删除）",
    )


@router.get("/detail", response_model=MatterDetailResponse)
async def matter_detail(
    busi_id: str = Query(..., description="办件 busiId"),
    name_id: Optional[str] = Query(default=None, description="可选：nameId（如果调用方已知）"),
) -> MatterDetailResponse:
    """单个办件详情 + establish 当前位置。"""
    client = ICPSPClient()

    # 1. 从 list 找 basic info（列表是唯一来源，因为没找到单独的 detail GET API）
    try:
        list_resp = _search_matters(client, page_size=50)
    except Exception as e:
        return MatterDetailResponse(
            success=False,
            busi_id=busi_id,
            reason="http_error",
            reason_detail=f"{type(e).__name__}: {str(e)[:200]}",
        )

    list_code = list_resp.get("code")
    if list_code != "00000":
        return MatterDetailResponse(
            success=False,
            busi_id=busi_id,
            reason=f"list_code_{list_code}",
            reason_detail=str(list_resp.get("msg") or "")[:200],
        )

    raw_matter: Optional[Dict[str, Any]] = None
    for it in (list_resp.get("data") or {}).get("busiData") or []:
        if isinstance(it, dict) and str(it.get("id")) == str(busi_id):
            raw_matter = it
            break

    if not raw_matter:
        return MatterDetailResponse(
            success=False,
            busi_id=busi_id,
            reason="not_found",
            reason_detail=f"busi_id={busi_id} 不在当前用户的办件列表中",
        )

    ent_type = str(raw_matter.get("entType") or "4540")
    busi_type_full = str(raw_matter.get("busiType") or "01_4")
    nid = name_id or raw_matter.get("nameId")

    # 2. 调 establish/loadCurrentLocationInfo 查当前组件位置
    curr_comp: Optional[str] = None
    est_status: Optional[str] = None
    try:
        body = {
            "flowData": {
                "busiId": busi_id,
                "entType": ent_type,
                "busiType": busi_type_full,
                "ywlbSign": "4",
                "busiMode": None,
                "nameId": nid,
                "marPrId": None,
                "secondId": None,
                "vipChannel": None,
            },
            "linkData": {"continueFlag": "continueFlag", "token": ""},
        }
        est_resp = client.post_json(
            "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
            body,
            extra_headers={"Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html"},
        )
        if est_resp.get("code") == "00000":
            bd = (est_resp.get("data") or {}).get("busiData") or {}
            fd = bd.get("flowData") or {}
            curr_comp = fd.get("currCompUrl")
            est_status = fd.get("status")
    except Exception:
        pass  # establish 查询失败不影响基础信息

    return MatterDetailResponse(
        success=True,
        busi_id=busi_id,
        entName=raw_matter.get("entName"),
        nameId=nid,
        busiType=raw_matter.get("busiType"),
        entType=ent_type,
        status=raw_matter.get("matterStateCode") or raw_matter.get("listMatterStateCode"),
        currCompUrl=curr_comp,
        establish_status=est_status,
        raw_matter=raw_matter,
    )
