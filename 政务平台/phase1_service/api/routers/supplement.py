"""POST /api/phase1/supplement — 名称登记 Step2 信息补充 + Step3 提交。

前置条件：busiId（来自 POST /register 成功返回）
流程：
  1) NameSupplement/operationBusinessDataInfo — 保存信息补充
  2) /name/submit — 提交名称登记申请
  3) NameSuccess/loadBusinessDataInfo — 验证申报完成（status=51）
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "system"))

from ..core.auth_manager import (
    validate_authorization,
    set_runtime_auth,
    get_current_auth,
)
from ..core.supplement_driver import (
    SupplementInput,
    build_supplement_body,
    build_submit_body,
    build_success_load_body,
    API_NS_OP,
    API_SUBMIT,
    API_SUCCESS_LOAD,
)

router = APIRouter(prefix="/api/phase1", tags=["supplement"])


# ── 请求 schema ──
class BusiAreaItem(BaseModel):
    """经营范围条目（从 GET /scope 返回的 items 中挑选）。"""
    id: str = Field(..., description="条目 ID，如 I3006")
    name: str = Field(..., description="经营范围名称，如 软件开发")
    stateCo: str = Field(default="1", description="状态码：3=主营, 1=一般")
    pid: Optional[str] = None
    minIndusTypeCode: Optional[str] = None
    midIndusTypeCode: Optional[str] = None
    isMainIndustry: str = Field(default="0", description="1=主营")
    category: Optional[str] = None
    indusTypeCode: Optional[str] = None
    indusTypeName: Optional[str] = None


class AgentInfo(BaseModel):
    """经办人信息。"""
    name: str = Field(..., description="经办人姓名")
    cert_type: str = Field(default="10", description="证件类型：10=身份证")
    cert_no: str = Field(..., description="证件号码（明文，API 内部自动 RSA 加密）")
    mobile: str = Field(..., description="手机号码（明文，API 内部自动 RSA 加密）")


class SupplementRequest(BaseModel):
    busi_id: str = Field(..., description="Phase1 register 返回的 busiId")
    ent_name: str = Field(..., description="完整企业名称（Phase1 返回的 full_name）")

    # 企业类型
    ent_type: str = Field(default="4540")
    busi_type: str = Field(default="01")

    # 区划
    dist_code: str = Field(default="450921")
    dist_codes: List[str] = Field(default=["450000", "450900", "450921"])
    address: str = Field(default="广西壮族自治区玉林市容县")

    # 行业
    industry_code: str = Field(..., description="行业代码")
    industry_name: str = Field(..., description="行业名称")

    # 经营范围
    busi_area_items: List[BusiAreaItem] = Field(default_factory=list, description="经营范围条目列表")
    busi_area_code: str = Field(default="", description="经营范围代码，如 I3006|F1129")
    busi_area_name: str = Field(default="", description="经营范围名称，如 软件开发;食品销售")
    gen_busi_area: str = Field(default="", description="生成的经营范围文本")

    # 登记机关
    org_id: str = Field(default="", description="登记机关 ID")
    org_name: str = Field(default="", description="登记机关名称，如 容西市监所")

    # 注册资本
    register_capital: str = Field(default="5", description="注册资本（万元）")

    # 经办人
    agent: AgentInfo

    # 可选
    authorization: Optional[str] = None
    auto_submit: bool = Field(default=True, description="保存后是否自动提交")


class SupplementStepReport(BaseModel):
    name: str
    ok: bool
    code: str
    msg: Optional[str] = None
    duration_ms: int = 0


class SupplementResponse(BaseModel):
    success: bool
    busi_id: str
    status: Optional[str] = Field(None, description="最终状态：10=草稿 20=已提交 51=审核中")
    name_id: Optional[str] = Field(None, description="名称 ID（提交后分配）")
    steps: List[SupplementStepReport] = Field(default_factory=list)
    latency_ms: int = 0
    reason: Optional[str] = None


def _call_api(path: str, body: dict) -> dict:
    from icpsp_api_client import ICPSPClient
    client = ICPSPClient()
    return client.post_json(path, body)


@router.post("/supplement", response_model=SupplementResponse)
async def supplement(req: SupplementRequest) -> SupplementResponse:
    started = time.time()
    steps: List[SupplementStepReport] = []

    # Auth
    if req.authorization:
        if not validate_authorization(req.authorization):
            raise HTTPException(status_code=400, detail="Authorization 必须是 32 位十六进制")
        set_runtime_auth(req.authorization)
    elif not get_current_auth():
        raise HTTPException(status_code=401, detail="未提供 Authorization")

    # 构造输入
    inp = SupplementInput(
        busi_id=req.busi_id,
        ent_type=req.ent_type,
        busi_type=req.busi_type,
        dist_code=req.dist_code,
        dist_codes=req.dist_codes,
        address=req.address,
        industry_code=req.industry_code,
        industry_name=req.industry_name,
        busi_area_items=[item.model_dump() for item in req.busi_area_items],
        busi_area_code=req.busi_area_code,
        busi_area_name=req.busi_area_name,
        gen_busi_area=req.gen_busi_area,
        org_id=req.org_id,
        org_name=req.org_name,
        register_capital=req.register_capital,
        agent_name=req.agent.name,
        agent_cert_type=req.agent.cert_type,
        agent_cert_no=req.agent.cert_no,
        agent_mobile=req.agent.mobile,
        ent_name=req.ent_name,
    )

    # Step 1: NameSupplement save
    t0 = time.time()
    try:
        body = build_supplement_body(inp)
        resp = await asyncio.get_event_loop().run_in_executor(
            None, _call_api, API_NS_OP, body
        )
        code = str(resp.get("code") or "")
        ok = code == "00000"
        data = resp.get("data") or {}
        msg = str(data.get("msg") or resp.get("msg") or "")
        steps.append(SupplementStepReport(
            name="NameSupplement/save", ok=ok, code=code, msg=msg,
            duration_ms=int((time.time() - t0) * 1000)
        ))
        if not ok:
            return SupplementResponse(
                success=False, busi_id=req.busi_id, steps=steps,
                latency_ms=int((time.time() - started) * 1000),
                reason=f"NameSupplement save failed: code={code} msg={msg}",
            )
    except Exception as e:
        steps.append(SupplementStepReport(
            name="NameSupplement/save", ok=False, code="EXCEPTION", msg=str(e),
            duration_ms=int((time.time() - t0) * 1000)
        ))
        return SupplementResponse(
            success=False, busi_id=req.busi_id, steps=steps,
            latency_ms=int((time.time() - started) * 1000),
            reason=f"NameSupplement exception: {e!r}",
        )

    await asyncio.sleep(0.9)

    # Step 2: Submit (optional)
    status = "10"
    name_id = None
    if req.auto_submit:
        t0 = time.time()
        try:
            body = build_submit_body(inp)
            resp = await asyncio.get_event_loop().run_in_executor(
                None, _call_api, API_SUBMIT, body
            )
            code = str(resp.get("code") or "")
            ok = code == "00000"
            data = resp.get("data") or {}
            bd = data.get("busiData") or {}
            flow_resp = bd.get("flowData") or {}
            status = str(flow_resp.get("status") or "10")
            msg = str(data.get("msg") or resp.get("msg") or "")
            steps.append(SupplementStepReport(
                name="submit", ok=ok, code=code, msg=msg,
                duration_ms=int((time.time() - t0) * 1000)
            ))
            if not ok:
                return SupplementResponse(
                    success=False, busi_id=req.busi_id, status=status, steps=steps,
                    latency_ms=int((time.time() - started) * 1000),
                    reason=f"submit failed: code={code} msg={msg}",
                )
        except Exception as e:
            steps.append(SupplementStepReport(
                name="submit", ok=False, code="EXCEPTION", msg=str(e),
                duration_ms=int((time.time() - t0) * 1000)
            ))
            return SupplementResponse(
                success=False, busi_id=req.busi_id, steps=steps,
                latency_ms=int((time.time() - started) * 1000),
                reason=f"submit exception: {e!r}",
            )

        await asyncio.sleep(0.9)

        # Step 3: NameSuccess load (验证)
        t0 = time.time()
        try:
            body = build_success_load_body(inp)
            resp = await asyncio.get_event_loop().run_in_executor(
                None, _call_api, API_SUCCESS_LOAD, body
            )
            code = str(resp.get("code") or "")
            ok = code == "00000"
            data = resp.get("data") or {}
            bd = data.get("busiData") or {}
            flow_resp = bd.get("flowData") or {}
            status = str(flow_resp.get("status") or status)
            name_id = flow_resp.get("nameId")
            msg = str(data.get("msg") or "")
            steps.append(SupplementStepReport(
                name="NameSuccess/load", ok=ok, code=code, msg=msg,
                duration_ms=int((time.time() - t0) * 1000)
            ))
        except Exception as e:
            steps.append(SupplementStepReport(
                name="NameSuccess/load", ok=False, code="EXCEPTION", msg=str(e),
                duration_ms=int((time.time() - t0) * 1000)
            ))

    return SupplementResponse(
        success=True,
        busi_id=req.busi_id,
        status=status,
        name_id=name_id,
        steps=steps,
        latency_ms=int((time.time() - started) * 1000),
    )
