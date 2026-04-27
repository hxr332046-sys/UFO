"""
适配层 — 把现有 Phase 1/2 驱动器的步骤函数接入 Pipeline 框架

设计:
  - Phase1Adapter: 持有 DriverContext，把 8 个步骤函数包装为 StepSpec
  - Phase2Adapter: 持有 Phase2Context，把 25/28 个步骤函数包装为 StepSpec
  - 内部驱动器上下文对外不可见，Pipeline 只看到 StepSpec + StepResult
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

from .core import StepResult, StepSpec, PipelineContext


def _phase2_component_from_name(step_name: str) -> str:
    parts = [p.strip() for p in str(step_name or "").split("/") if p.strip()]
    if not parts:
        return ""
    if parts[0] in ("establish", "name", "matters") and len(parts) > 1:
        candidate = parts[1]
    else:
        candidate = parts[0]
    candidate = candidate.split()[0]
    if candidate in ("loadCurrentLocationInfo", "loadBusinessDataInfo", "loadBusinessInfoList", "submit", "operate"):
        return ""
    return candidate


def _phase2_expected_progress(step_num: int, ent_type: str, component: str) -> Dict[str, Any]:
    common_tail = {
        22: {
            "mode": "must_leave_component",
            "from_component": "BusinessLicenceWay",
            "expected_components": ["YbbSelect", "PreElectronicDoc", "PreSubmitSuccess"],
            "probe_after_mutation": False,
        },
        23: {
            "mode": "must_leave_component",
            "from_component": "YbbSelect",
            "expected_components": ["PreElectronicDoc", "PreSubmitSuccess"],
            "probe_after_mutation": False,
        },
        24: {
            "mode": "must_reach_component_status",
            "expected_components": ["PreSubmitSuccess"],
            "expected_statuses": ["90"],
            "probe_after_mutation": False,
        },
        25: {
            "mode": "must_reach_component_status",
            "expected_components": ["PreSubmitSuccess"],
            "expected_statuses": ["90"],
        },
        26: {
            "mode": "submit_final",
            "expected_components": ["PreSubmitSuccess"],
            "expected_statuses": ["90"],
        },
    }
    company_tail = {
        25: {
            "mode": "must_leave_component",
            "from_component": "BusinessLicenceWay",
            "expected_components": ["YbbSelect", "PreElectronicDoc", "PreSubmitSuccess"],
            "probe_after_mutation": False,
        },
        26: {
            "mode": "must_leave_component",
            "from_component": "YbbSelect",
            "expected_components": ["PreElectronicDoc", "PreSubmitSuccess"],
            "probe_after_mutation": False,
        },
        27: {
            "mode": "must_reach_component_status",
            "expected_components": ["PreSubmitSuccess"],
            "expected_statuses": ["90"],
            "probe_after_mutation": False,
        },
        28: {
            "mode": "must_reach_component_status",
            "expected_components": ["PreSubmitSuccess"],
            "expected_statuses": ["90"],
        },
        29: {
            "mode": "submit_final",
            "expected_components": ["PreSubmitSuccess"],
            "expected_statuses": ["90"],
        },
    }
    rules = company_tail if ent_type == "1151" else common_tail
    progress = dict(rules.get(step_num) or {})
    if progress and component and not progress.get("from_component"):
        progress["from_component"] = component
    return progress


def _phase2_expected_entry(step_num: int, ent_type: str) -> Dict[str, Any]:
    common_tail = {
        23: {"allowed_current_components": ["YbbSelect", "BusinessLicenceWay"], "require_known_position": True},
        24: {"allowed_current_components": ["PreElectronicDoc", "YbbSelect"], "require_known_position": True},
        25: {"allowed_current_components": ["PreSubmitSuccess", "YbbSelect", "PreElectronicDoc"], "require_known_position": True},
        26: {"allowed_current_components": ["PreSubmitSuccess"], "require_known_position": True},
    }
    company_tail = {
        26: {"allowed_current_components": ["YbbSelect", "BusinessLicenceWay"], "require_known_position": True},
        27: {"allowed_current_components": ["PreElectronicDoc", "YbbSelect"], "require_known_position": True},
        28: {"allowed_current_components": ["PreSubmitSuccess", "YbbSelect", "PreElectronicDoc"], "require_known_position": True},
        29: {"allowed_current_components": ["PreSubmitSuccess"], "require_known_position": True},
    }
    rules = company_tail if ent_type == "1151" else common_tail
    return dict(rules.get(step_num) or {})


def _phase2_server_state(resp: Dict[str, Any]) -> Dict[str, Any]:
    data = resp.get("data") or {} if isinstance(resp, dict) else {}
    bd = data.get("busiData") or {} if isinstance(data, dict) else {}
    fd = bd.get("flowData") or {} if isinstance(bd, dict) else {}
    pvo = bd.get("processVo") or {} if isinstance(bd, dict) else {}
    busi_comp = bd.get("busiComp") or {} if isinstance(bd, dict) else {}
    # ★ flowData.currCompUrl 是权威位置；processVo.currentComp 只是 SPA 模板
    # 当 currCompUrl=None 时说明还没进入任何组件，不应 fallback 到 processVo
    raw_comp = fd.get("currCompUrl")
    if raw_comp:
        comp_url = str(raw_comp)
    else:
        comp_url = ""
    return {
        "server_curr_comp_url": comp_url,
        "server_status": str(fd.get("status") or ""),
        "server_busi_type": str(fd.get("busiType") or ""),
        "server_name_id": str(fd.get("nameId") or ""),
        "server_busi_id": str(fd.get("busiId") or ""),
    }


def _phase2_probe_current_location(client: Any, p2_ctx: Any) -> Dict[str, Any]:
    try:
        from phase2_protocol_driver import step12_establish_location
        resp = step12_establish_location(client, p2_ctx)
        state = _phase2_server_state(resp)
        data = resp.get("data") or {} if isinstance(resp, dict) else {}
        state["position_probe_code"] = str(resp.get("code") or "") if isinstance(resp, dict) else ""
        state["position_probe_result_type"] = str(data.get("resultType") or "") if isinstance(data, dict) else ""
        return state
    except Exception as exc:
        return {"position_probe_error": f"{type(exc).__name__}: {str(exc)[:160]}"}


def _phase2_resume_anchor_index(raw_specs: List[Any], observed_component: str) -> Optional[int]:
    component = str(observed_component or "").strip()
    if not component:
        return None
    if component == "NameSuccess":
        for idx, (_step_num, name, _fn, _optional) in enumerate(raw_specs):
            if "matters/operate [108,before]" in name:
                return idx
    first_match: Optional[int] = None
    preferred_match: Optional[int] = None
    for idx, (_step_num, name, _fn, _optional) in enumerate(raw_specs):
        current_component = _phase2_component_from_name(name)
        if current_component != component:
            continue
        if first_match is None:
            first_match = idx
        if any(token in name for token in ("operationBusinessDataInfo", "submit", "upload", "[终点]")):
            preferred_match = idx
    return preferred_match if preferred_match is not None else first_match


def _validate_phase2_progress(progress: Dict[str, Any], server_state: Dict[str, Any], *,
                              step_name: str, upstream_code: str, upstream_result_type: str) -> Optional[Dict[str, Any]]:
    if not progress:
        return None
    mode = str(progress.get("mode") or "")
    current_comp = str(server_state.get("server_curr_comp_url") or "")
    current_status = str(server_state.get("server_status") or "")
    from_component = str(progress.get("from_component") or "")
    expected_components = [str(x) for x in (progress.get("expected_components") or []) if x]
    expected_statuses = [str(x) for x in (progress.get("expected_statuses") or []) if x]

    if mode == "must_leave_component":
        if current_comp and from_component and current_comp == from_component:
            target = " / ".join(expected_components) or "后续组件"
            return {
                "code": "STEP_NOT_ADVANCED",
                "message": f"{step_name} 上游返回 {upstream_code}/rt={upstream_result_type or '-'}，但服务端仍停留在 {current_comp}，未推进到 {target}。",
            }
        return None

    if mode == "must_reach_component_status":
        if current_comp and expected_components and current_comp not in expected_components:
            return {
                "code": "STEP_NOT_ADVANCED",
                "message": f"{step_name} 上游返回 {upstream_code}/rt={upstream_result_type or '-'}，但服务端当前位置为 {current_comp}，未到达 {' / '.join(expected_components)}。",
            }
        if current_status and expected_statuses and current_status not in expected_statuses:
            return {
                "code": "STEP_NOT_ADVANCED",
                "message": f"{step_name} 上游返回 {upstream_code}/rt={upstream_result_type or '-'}，但服务端 status={current_status}，未达到 {' / '.join(expected_statuses)}。",
            }
    return None


def _phase2_preflight_result(step_name: str, entry_guard: Dict[str, Any],
                             pipeline_ctx: PipelineContext) -> Optional[StepResult]:
    if not entry_guard:
        return None
    allowed_components = [str(x) for x in (entry_guard.get("allowed_current_components") or []) if x]
    require_known_position = bool(entry_guard.get("require_known_position"))
    observed_component = str(
        pipeline_ctx.state.get("current_comp_url")
        or pipeline_ctx.state.get("server_curr_comp_url")
        or ""
    )
    if not observed_component:
        if not require_known_position:
            return None
        return StepResult(
            name=step_name,
            ok=False,
            code="STEP_POSITION_GUARD",
            message=f"{step_name} 被本地编排护栏拦截：当前没有可用的位置反馈，不能在无感知状态下继续请求。",
            extracted={
                "allowed_current_components": allowed_components,
                "last_response_code": pipeline_ctx.state.get("last_response_code"),
                "last_step_name": pipeline_ctx.state.get("last_step_name"),
            },
        )
    if allowed_components and observed_component not in allowed_components:
        return StepResult(
            name=step_name,
            ok=False,
            code="STEP_POSITION_GUARD",
            message=f"{step_name} 被本地编排护栏拦截：当前感知位置为 {observed_component}，不应直接执行该步骤。",
            extracted={
                "observed_current_comp_url": observed_component,
                "allowed_current_components": allowed_components,
                "last_response_code": pipeline_ctx.state.get("last_response_code"),
                "last_step_name": pipeline_ctx.state.get("last_step_name"),
            },
        )
    return None


# ════════════════════════════════════════════════
# Phase 1 适配器
# ════════════════════════════════════════════════

class Phase1Adapter:
    """把 phase1_protocol_driver 的 8 个步骤函数适配为 Pipeline StepSpec。

    内部持有 DriverContext，所有步骤共享同一个上下文。
    Pipeline 看到的是标准 StepSpec，完全不知道 DriverContext 的存在。

    Usage:
        adapter = Phase1Adapter(case_dict)
        steps = adapter.make_steps()
        pipe = Pipeline("phase1", steps=steps, hooks=hooks)
        result = pipe.run(ctx)
        # 核名成功后取 busiId:
        busi_id = adapter.driver_ctx.busi_id
    """

    def __init__(self, case: Dict[str, Any]):
        from phase1_protocol_driver import DriverContext
        self.driver_ctx = DriverContext.from_case(case)

    def rebuild(self, new_case: Dict[str, Any]):
        """改名后重建 DriverContext（不丢弃 adapter 实例）。"""
        from phase1_protocol_driver import DriverContext
        self.driver_ctx = DriverContext.from_case(new_case)

    def _wrap(self, fn: Callable) -> Callable:
        """将 Phase 1 步骤函数 (client, DriverCtx) -> (P1StepResult, resp)
        包装为 Pipeline 能调用的 (client, PipelineCtx) -> StepResult。
        """
        driver_ctx = self.driver_ctx

        def adapted(client: Any, pipeline_ctx: PipelineContext) -> StepResult:
            p1_result, resp = fn(client, driver_ctx)
            # 转换为框架的 StepResult
            sr = StepResult(
                name=getattr(p1_result, "name", ""),
                ok=p1_result.ok,
                code=str(getattr(p1_result, "code", "")),
                result_type=str(getattr(p1_result, "result_type", "")),
                message=str(getattr(p1_result, "reason", "")),
                extracted=dict(getattr(p1_result, "extracted", {}) or {}),
                raw_response=resp if isinstance(resp, dict) else None,
                sent_body_keys=list(getattr(p1_result, "sent_body_keys", []) or []),
            )
            # 同步关键状态到 PipelineContext
            bid = sr.extracted.get("busiId_from_second_save") or sr.extracted.get("busiId_from_third_save")
            if bid:
                pipeline_ctx.phase1_busi_id = str(bid)
            nid = sr.extracted.get("nameId")
            if nid:
                pipeline_ctx.name_id = str(nid)
            # 同步 banned 信息（供 NameCorrectionHook 使用）
            if driver_ctx.banned_tip_keywords:
                pipeline_ctx.state["banned_tip_keywords"] = driver_ctx.banned_tip_keywords
            if driver_ctx.banned_infos_json:
                pipeline_ctx.state["banned_infos_json"] = driver_ctx.banned_infos_json
            return sr

        return adapted

    def make_steps(self) -> List[StepSpec]:
        """生成 Phase 1 的 8 个 StepSpec。"""
        from phase1_protocol_driver import (
            step_check_establish_name,
            step_load_current_location,
            step_namecheck_load,
            step_banned_lexicon,
            step_nc_op_first_save,
            step_namecheck_repeat,
            step_nc_op_second_save,
            step_nc_op_third_save,
        )

        return [
            StepSpec(name="checkEstablishName",                       fn=self._wrap(step_check_establish_name),  optional=True,  tag="p1_guide", delay_after_s=0.9),
            StepSpec(name="loadCurrentLocationInfo",                   fn=self._wrap(step_load_current_location), optional=True,  tag="p1_guide", delay_after_s=0.9),
            StepSpec(name="NameCheckInfo/loadBusinessDataInfo",        fn=self._wrap(step_namecheck_load),        optional=True,  tag="p1_guide", delay_after_s=0.9),
            StepSpec(name="bannedLexiconCalibration",                  fn=self._wrap(step_banned_lexicon),        optional=True,  tag="p1_query", delay_after_s=0.9),
            StepSpec(name="NameCheckInfo/operationBusinessDataInfo#1", fn=self._wrap(step_nc_op_first_save),      optional=False, tag="p1_core",  delay_after_s=1.5),
            StepSpec(name="NameCheckInfo/nameCheckRepeat",             fn=self._wrap(step_namecheck_repeat),      optional=False, tag="p1_query", delay_after_s=0.9),
            StepSpec(name="NameCheckInfo/operationBusinessDataInfo#2", fn=self._wrap(step_nc_op_second_save),     optional=False, tag="p1_core",  delay_after_s=1.5),
            StepSpec(name="NameCheckInfo/operationBusinessDataInfo#3", fn=self._wrap(step_nc_op_third_save),      optional=True,  tag="p1_core",  delay_after_s=0.9),
        ]


# ════════════════════════════════════════════════
# Phase 2 适配器
# ════════════════════════════════════════════════

class Phase2Adapter:
    """把 phase2_protocol_driver 的 25/28 个步骤函数适配为 Pipeline StepSpec。

    内部持有 Phase2Context，所有步骤共享同一个上下文。

    Usage:
        adapter = Phase2Adapter(case_dict, busi_id="xxx", name_id="yyy")
        steps = adapter.make_steps()
        pipe = Pipeline("phase2", steps=steps, hooks=hooks)
        result = pipe.run(ctx)
    """

    def __init__(self, case: Dict[str, Any], busi_id: str,
                 name_id: Optional[str] = None,
                 establish_busi_id: Optional[str] = None,
                 user_id: str = ""):
        from phase2_protocol_driver import Phase2Context
        self.p2_ctx = Phase2Context.from_case(case, busi_id)
        if name_id:
            self.p2_ctx.name_id = name_id
        if establish_busi_id:
            self.p2_ctx.snapshot["establish_busiId"] = establish_busi_id
        if user_id:
            self.p2_ctx.user_id = user_id

    def restore_from_pipeline_ctx(self, pipeline_ctx: PipelineContext) -> None:
        """把 checkpoint 恢复到 PipelineContext 的状态同步回内部 Phase2Context。"""
        state = pipeline_ctx.state or {}
        if state.get("phase2_driver_name_id"):
            self.p2_ctx.name_id = str(state.get("phase2_driver_name_id"))
        elif pipeline_ctx.name_id:
            self.p2_ctx.name_id = str(pipeline_ctx.name_id)

        restored_busi_id = (
            state.get("phase2_driver_busi_id")
            or state.get("establish_busi_id")
            or state.get("phase1_busi_id")
        )
        if restored_busi_id:
            self.p2_ctx.busi_id = str(restored_busi_id)

        snapshot = state.get("phase2_driver_snapshot") or {}
        if isinstance(snapshot, dict):
            self.p2_ctx.snapshot = dict(snapshot)

        if state.get("phase2_driver_ent_type"):
            self.p2_ctx.ent_type = str(state.get("phase2_driver_ent_type"))
        if state.get("phase2_driver_busi_type"):
            self.p2_ctx.busi_type = str(state.get("phase2_driver_busi_type"))

    def recommend_start_from(self, observed_component: str, *,
                              fallback_index: int = 0,
                              ent_type: Optional[str] = None) -> int:
        """根据当前位置组件，给出更符合服务端状态的恢复起点（0-indexed）。"""
        from phase2_protocol_driver import get_steps_spec

        raw_specs = get_steps_spec(ent_type or self.p2_ctx.ent_type)
        anchor_index = _phase2_resume_anchor_index(raw_specs, observed_component)
        if anchor_index is None:
            return fallback_index
        return int(anchor_index)

    def probe_current_location(self, client: Any, pipeline_ctx: PipelineContext) -> Dict[str, Any]:
        state = _phase2_probe_current_location(client, self.p2_ctx)
        if state.get("server_curr_comp_url"):
            pipeline_ctx.state["current_comp_url"] = state.get("server_curr_comp_url")
        if state.get("server_status"):
            pipeline_ctx.state["current_status"] = state.get("server_status")
        if state.get("server_busi_id") and state.get("server_busi_type") == "02":
            pipeline_ctx.establish_busi_id = str(state.get("server_busi_id"))
        pipeline_ctx.state.update({k: v for k, v in state.items() if v})
        pipeline_ctx.state["phase2_driver_snapshot"] = dict(self.p2_ctx.snapshot or {})
        return state

    def _wrap(self, fn: Callable, step_name: str, step_num: int,
              progress: Optional[Dict[str, Any]] = None,
              entry_guard: Optional[Dict[str, Any]] = None) -> Callable:
        """将 Phase 2 步骤函数 (client, Phase2Ctx) -> Dict
        包装为 Pipeline 能调用的 (client, PipelineCtx) -> StepResult。
        """
        p2_ctx = self.p2_ctx
        progress = dict(progress or {})
        entry_guard = dict(entry_guard or {})

        def adapted(client: Any, pipeline_ctx: PipelineContext) -> StepResult:
            preflight = _phase2_preflight_result(step_name, entry_guard, pipeline_ctx)
            if preflight is not None:
                return preflight
            resp = fn(client, p2_ctx)
            pipeline_ctx.state["phase2_driver_snapshot"] = dict(p2_ctx.snapshot or {})
            pipeline_ctx.state["phase2_driver_busi_id"] = p2_ctx.busi_id
            pipeline_ctx.state["phase2_driver_ent_type"] = p2_ctx.ent_type
            pipeline_ctx.state["phase2_driver_busi_type"] = p2_ctx.busi_type
            if p2_ctx.name_id:
                pipeline_ctx.state["phase2_driver_name_id"] = p2_ctx.name_id
                if not pipeline_ctx.name_id:
                    pipeline_ctx.name_id = str(p2_ctx.name_id)
            # Phase 2 返回 raw dict，解析出标准字段
            code, rt, msg = "", "", ""
            extracted: Dict[str, Any] = {}
            if isinstance(resp, dict):
                code = str(resp.get("code", ""))
                protocol_extracted = resp.get("_protocol_extracted") or {}
                if isinstance(protocol_extracted, dict):
                    extracted.update(protocol_extracted)
                data = resp.get("data") or {}
                if isinstance(data, dict):
                    rt = str(data.get("resultType", ""))
                    msg = str(data.get("msg", "") or resp.get("message", ""))
                    bd = data.get("busiData") or {}
                    fd = bd.get("flowData") or {} if isinstance(bd, dict) else {}
                    if isinstance(fd, dict):
                        extracted.update({
                            "busiId": fd.get("busiId"),
                            "nameId": fd.get("nameId"),
                            "server_curr_comp_url": fd.get("currCompUrl"),
                            "server_status": fd.get("status"),
                            "server_busi_type": fd.get("busiType"),
                        })
                    # 同步关键状态
                    if isinstance(fd, dict):
                        # ★ 只在 busiType=02（设立）时捕获 establish_busi_id
                        #    避免把 busiType=01（核名）的 busiId 误设为 establish_busi_id
                        if (fd.get("busiId") and not pipeline_ctx.establish_busi_id
                                and fd.get("busiType") == "02"):
                            pipeline_ctx.establish_busi_id = str(fd["busiId"])
                        if fd.get("status") == "90":
                            pipeline_ctx.state["reached_status_90"] = True
                        if fd.get("currCompUrl") == "PreSubmitSuccess":
                            pipeline_ctx.state["reached_pre_submit"] = True
                else:
                    msg = str(resp.get("message", ""))

            # ★ ok 判定：code=00000 且 rt≠1 才算真正成功
            #   rt=0/空: 保存成功，组件已推进
            #   rt=1:   参数校验失败，组件未保存 → 不应为 ok
            #   rt=2:   警告（如名称近似），步骤内部可能已处理 → 允许 ok
            #   rt=-1:  致命错误（由 is_fatal 单独处理）
            #   D0018:  业务状态已变化，服务端已推进 → 视为成功
            #   D0010:  当前表单无需填写（终点组件可达但无需操作）→ 视为成功
            step_ok = (code == "00000" and rt != "1") or code in ("D0018", "D0010")

            if step_ok and progress:
                server_state = _phase2_server_state(resp)
                if progress.get("mode") == "must_leave_component":
                    if progress.get("probe_after_mutation", True):
                        probe_state = _phase2_probe_current_location(client, p2_ctx)
                        extracted.update({k: v for k, v in probe_state.items() if v})
                        if not probe_state.get("position_probe_error"):
                            server_state.update({k: v for k, v in probe_state.items() if v})
                    else:
                        # ★ probe_after_mutation=False: save 响应的 currCompUrl 是当前组件，
                        # 无法判断是否推进。跳过 progress validation，信任 save 成功。
                        extracted.update(server_state)
                        if progress.get("expected_components"):
                            extracted["expected_components"] = list(progress.get("expected_components") or [])
                        # 跳过 _validate_phase2_progress
                        return StepResult(
                            name=step_name,
                            ok=True,
                            code=code,
                            result_type=rt,
                            message=msg[:200],
                            extracted=extracted,
                            raw_response=resp,
                        )
                extracted.update(server_state)
                if progress.get("expected_components"):
                    extracted["expected_components"] = list(progress.get("expected_components") or [])
                if progress.get("expected_statuses"):
                    extracted["expected_statuses"] = list(progress.get("expected_statuses") or [])
                # ★ D0010/D0018 时服务端不返回 flowData，progress validation 必然失败
                # 这些 code 本身就表示步骤已完成，跳过 validation
                if code in ("D0010", "D0018"):
                    extracted["progress_validation_skipped"] = True
                    extracted["progress_validation_skip_reason"] = f"code={code}"
                else:
                    progress_problem = _validate_phase2_progress(
                        progress,
                        server_state,
                        step_name=step_name,
                        upstream_code=code,
                        upstream_result_type=rt,
                    )
                    if progress_problem:
                        step_ok = False
                        code = str(progress_problem.get("code") or "STEP_NOT_ADVANCED")
                        msg = str(progress_problem.get("message") or msg)
                        extracted["upstream_code"] = resp.get("code")
                        extracted["upstream_result_type"] = rt
                        extracted["expected_progress_mode"] = progress.get("mode")
                        extracted["expected_from_component"] = progress.get("from_component")

            return StepResult(
                name=step_name,
                ok=step_ok,
                code=code,
                result_type=rt,
                message=msg[:200],
                extracted=extracted,
                raw_response=resp,
            )

        return adapted

    def make_steps(self, ent_type: Optional[str] = None) -> List[StepSpec]:
        """生成 Phase 2 的 StepSpec 列表。

        根据 ent_type 自动选择 4540 (25步) 或 1151 (28步)。
        """
        from phase2_protocol_driver import get_steps_spec

        raw_specs = get_steps_spec(ent_type or self.p2_ctx.ent_type)
        steps: List[StepSpec] = []

        for step_num, name, fn, optional in raw_specs:
            component = _phase2_component_from_name(name)
            progress = _phase2_expected_progress(step_num, ent_type or self.p2_ctx.ent_type, component)
            entry_guard = _phase2_expected_entry(step_num, ent_type or self.p2_ctx.ent_type)
            # save/submit/operate 步骤用更长延时（类人节奏）
            if any(kw in name for kw in ("operationBusinessDataInfo", "submit", "operate", "upload")):
                delay = 4.5
            else:
                delay = 1.8

            steps.append(StepSpec(
                name=f"[{step_num}] {name}",
                fn=self._wrap(fn, name, step_num, progress, entry_guard),
                optional=optional,
                tag=f"p2_step{step_num}",
                component=component,
                expected_progress=progress,
                delay_after_s=delay,
            ))

        return steps


# ════════════════════════════════════════════════
# 工厂函数
# ════════════════════════════════════════════════

def build_phase1_steps(case: Dict[str, Any]) -> tuple:
    """便捷工厂：返回 (steps, adapter)。"""
    adapter = Phase1Adapter(case)
    return adapter.make_steps(), adapter


def build_phase2_steps(case: Dict[str, Any], busi_id: str,
                       name_id: Optional[str] = None,
                       ent_type: Optional[str] = None) -> tuple:
    """便捷工厂：返回 (steps, adapter)。"""
    adapter = Phase2Adapter(case, busi_id, name_id)
    return adapter.make_steps(ent_type), adapter
