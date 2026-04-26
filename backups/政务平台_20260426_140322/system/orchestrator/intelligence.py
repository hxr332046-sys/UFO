from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


_STAGE1 = {
    "key": "stage1_name_info",
    "name": "第一阶段：名称信息（核名）",
}
_STAGE2 = {
    "key": "stage2_info_filling",
    "name": "第二阶段：信息填报",
}

_P1_PAGES = [
    ("checkEstablishName", "name_precheck", "名称预检 / 查重"),
    ("loadCurrentLocationInfo", "name_location", "名称流程定位"),
    ("NameCheckInfo/loadBusinessDataInfo", "name_form_load", "名称表单加载"),
    ("bannedLexiconCalibration", "banned_lexicon", "禁限用词校验"),
    ("operationBusinessDataInfo#1", "name_first_save", "名称首次保存"),
    ("nameCheckRepeat", "name_repeat_check", "名称库查重"),
    ("operationBusinessDataInfo#2", "name_second_save", "名称二次确认保存"),
    ("operationBusinessDataInfo#3", "name_third_save", "名称补充确认保存"),
]

_P2_4540_PAGES = {
    1: ("name_location", "名称流程定位", _STAGE1),
    2: ("name_supplement", "名称补充信息", _STAGE1),
    3: ("name_shareholder", "投资人 / 股东摘要", _STAGE1),
    4: ("name_shareholder", "投资人 / 股东摘要", _STAGE1),
    5: ("name_shareholder", "投资人 / 股东摘要保存", _STAGE1),
    6: ("name_shareholder", "投资人 / 股东摘要重读", _STAGE1),
    7: ("name_supplement", "名称补充信息保存", _STAGE1),
    8: ("name_submit", "名称提交", _STAGE1),
    9: ("name_success", "名称成功页", _STAGE1),
    10: ("matter_entry", "办件入口预处理", _STAGE2),
    11: ("matter_entry", "进入设立办件", _STAGE2),
    12: ("establish_location", "设立流程定位", _STAGE2),
    13: ("ybb_probe", "云帮办入口探测", _STAGE2),
    14: ("basic_info", "基本信息", _STAGE2),
    15: ("basic_info", "基本信息保存", _STAGE2),
    16: ("member_post", "成员架构", _STAGE2),
    17: ("member_info", "成员池列表", _STAGE2),
    18: ("member_info", "成员信息", _STAGE2),
    19: ("complement_info", "补充信息", _STAGE2),
    20: ("tax_invoice", "税务信息填报", _STAGE2),
    21: ("sl_upload_material", "材料补充", _STAGE2),
    22: ("business_licence_way", "营业执照领取", _STAGE2),
    23: ("ybb_select", "云帮办流程模式选择", _STAGE2),
    24: ("pre_electronic_doc", "预电子文档 / 信息确认", _STAGE2),
    25: ("pre_submit_success", "云提交成功页", _STAGE2),
}

_P2_1151_OVERRIDES = {
    16: ("member_post", "成员架构", _STAGE2),
    17: ("member_info", "成员池列表", _STAGE2),
    18: ("member_info", "成员信息", _STAGE2),
    19: ("complement_info", "补充信息 / 受益所有人", _STAGE2),
    20: ("rules", "章程", _STAGE2),
    21: ("medical_insured", "医保信息", _STAGE2),
    22: ("tax_invoice", "税务信息填报", _STAGE2),
    23: ("yjs_reg_prepack", "仅销售预包装食品备案", _STAGE2),
    24: ("sl_upload_material", "材料补充", _STAGE2),
    25: ("business_licence_way", "营业执照领取", _STAGE2),
    26: ("ybb_select", "云帮办流程模式选择", _STAGE2),
    27: ("pre_electronic_doc", "预电子文档 / 信息确认", _STAGE2),
    28: ("pre_submit_success", "云提交成功页", _STAGE2),
}

_CODE_POLICIES = {
    "D0029": {
        "category": "rate_limited",
        "severity": "blocker",
        "meaning": "服务端操作频繁 / 限流",
        "suggested_action": "停止当前链路，等待冷却后续跑；不要并发或死循环重试。",
        "recovery_action": "cooldown_then_resume",
        "retryable": True,
        "requires_human": False,
    },
    "D0022": {
        "category": "privilege_or_contract_mismatch",
        "severity": "blocker",
        "meaning": "越权访问或协议字段合同不匹配",
        "suggested_action": "检查是否先 load 当前组件、动态 signInfo、linkData、busiCompUrlPaths、flowData 与 body 字段是否来自真实样本。",
        "recovery_action": "inspect_payload_and_preload",
        "retryable": False,
        "requires_human": False,
    },
    "D0018": {
        "category": "business_status_changed",
        "severity": "recoverable",
        "meaning": "业务状态已变化，当前步骤可能已完成或服务端已推进到后续组件",
        "suggested_action": "立即查询 establish/loadCurrentLocationInfo；若当前位置已到后续页面，则按当前位置续跑，不要重复提交当前 save。",
        "recovery_action": "probe_progress_then_resume",
        "retryable": False,
        "requires_human": False,
    },
    "D0019": {
        "category": "business_context_mismatch",
        "severity": "recoverable",
        "meaning": "业务上下文或当前位置不匹配",
        "suggested_action": "先执行 establish/loadCurrentLocationInfo 热身并恢复上下文，再从服务端当前位置续跑。",
        "recovery_action": "warmup_then_resume",
        "retryable": True,
        "requires_human": False,
    },
    "STEP_NOT_ADVANCED": {
        "category": "step_not_advanced",
        "severity": "recoverable",
        "meaning": "接口返回成功，但服务端状态没有推进到期望页面或状态",
        "suggested_action": "不要直接进入下一协议步骤；先以服务端当前位置为准，检查该组件是否缺少 continueFlag、按钮语义或自动推进合同。",
        "recovery_action": "inspect_progress_contract_then_resume",
        "retryable": False,
        "requires_human": False,
    },
    "STEP_POSITION_GUARD": {
        "category": "step_position_guard",
        "severity": "recoverable",
        "meaning": "本地编排护栏发现当前位置反馈缺失或与目标步骤不匹配，因此主动阻止了请求发送",
        "suggested_action": "先读取当前位置反馈，再按服务端真实所在组件续跑；不要盲目直打后续页面。",
        "recovery_action": "probe_current_position_then_resume",
        "retryable": False,
        "requires_human": False,
    },
    "STEP_NO_FEEDBACK": {
        "category": "missing_feedback",
        "severity": "blocker",
        "meaning": "步骤没有返回足够的结构化反馈，编排器拒绝在无感知状态下继续推进",
        "suggested_action": "补齐该步骤的响应感知、状态提取或回执解析，再继续编排。",
        "recovery_action": "instrument_feedback_then_resume",
        "retryable": False,
        "requires_human": False,
    },
    "STEP_EXECUTION_GUARD": {
        "category": "execution_guard_triggered",
        "severity": "blocker",
        "meaning": "单次运行内同一步触发次数过高，已被护栏阻断以避免死循环和高频请求",
        "suggested_action": "停止继续攻击同一点，复核状态与策略后再人工决定是否续跑。",
        "recovery_action": "cooldown_and_review_before_resume",
        "retryable": False,
        "requires_human": False,
    },
    "NAME_CHECK_STOP": {
        "category": "name_check_stop",
        "severity": "blocker",
        "meaning": "名称库查重明确返回 stop，当前名称不能继续同名提交",
        "suggested_action": "不要继续同名二次保存或 name/submit；先更换字号后从 Phase 1 重跑，或先人工释放原名称再试。",
        "recovery_action": "rename_then_restart_phase1",
        "retryable": False,
        "requires_human": False,
    },
    "D0021": {
        "category": "optional_component_unavailable",
        "severity": "warning",
        "meaning": "可选组件不可用或当前用户无该可选入口权限",
        "suggested_action": "如果该 step 标记 optional，可跳过；否则查询当前位置确认是否应进入下一页面。",
        "recovery_action": "skip_if_optional",
        "retryable": False,
        "requires_human": False,
    },
    "A0002": {
        "category": "server_exception_or_payload_error",
        "severity": "blocker",
        "meaning": "服务端异常，常见根因是请求体字段、类型、大小写、加密或路径不符合真实前端合同",
        "suggested_action": "对比 mitm 成功样本，重点查字段数量、null/空串/布尔类型、RSA/AES、cerno/cerNo 大小写和 linkData。",
        "recovery_action": "diff_against_captured_body",
        "retryable": False,
        "requires_human": False,
    },
    "A0005": {
        "category": "session_expired",
        "severity": "blocker",
        "meaning": "登录态或 Authorization 失效",
        "suggested_action": "刷新 token 或重新扫码登录，然后从断点续跑。",
        "recovery_action": "refresh_session_then_resume",
        "retryable": True,
        "requires_human": True,
    },
    "GS52010103E0302": {
        "category": "session_expired",
        "severity": "blocker",
        "meaning": "统一认证会话失效或未认证",
        "suggested_action": "刷新 token 或重新扫码登录，然后从断点续跑。",
        "recovery_action": "refresh_session_then_resume",
        "retryable": True,
        "requires_human": True,
    },
    "GS52010400B0017": {
        "category": "name_id_expired",
        "severity": "blocker",
        "meaning": "名称保留期限超期，旧 nameId 已失效",
        "suggested_action": "不要继续打当前 Phase 2 save；先刷新有效 nameId，通常需要重跑 Phase 1 名称链后再进入设立续跑。",
        "recovery_action": "refresh_name_id_then_resume",
        "retryable": False,
        "requires_human": False,
    },
    "EXCEPTION": {
        "category": "local_exception",
        "severity": "blocker",
        "meaning": "本地执行异常",
        "suggested_action": "查看 traceback 和最近一次上下文，修复脚本或环境后续跑。",
        "recovery_action": "inspect_local_exception",
        "retryable": False,
        "requires_human": False,
    },
    "ERROR": {
        "category": "local_or_optional_error",
        "severity": "warning",
        "meaning": "本地错误或可选步骤失败",
        "suggested_action": "如果是 optional 可跳过；否则查看异常详情。",
        "recovery_action": "inspect_or_skip_optional",
        "retryable": False,
        "requires_human": False,
    },
}


def protocol_step_number(step_name: str, tag: str = "") -> Optional[int]:
    tag_match = re.search(r"p2_step(\d+)", tag or "")
    if tag_match:
        return int(tag_match.group(1))
    name_match = re.match(r"\[(\d+)\]", step_name or "")
    if name_match:
        return int(name_match.group(1))
    return None


def page_context(pipeline_name: str, step_name: str, tag: str, ctx_state: Dict[str, Any], case: Dict[str, Any]) -> Dict[str, Any]:
    protocol_step = protocol_step_number(step_name, tag)
    ent_type = str(case.get("entType_default") or ctx_state.get("current_ent_type") or "4540")

    if protocol_step is not None:
        mapping = dict(_P2_4540_PAGES)
        if ent_type == "1151":
            mapping.update(_P2_1151_OVERRIDES)
        page_key, page_name, stage = mapping.get(protocol_step, ("unknown", "未知页面", _STAGE2 if protocol_step >= 10 else _STAGE1))
        return {
            "business_stage_key": stage["key"],
            "business_stage_name": stage["name"],
            "page_key": page_key,
            "page_name": page_name,
            "protocol_step": protocol_step,
            "ent_type": ent_type,
        }

    for needle, page_key, page_name in _P1_PAGES:
        if needle in step_name:
            return {
                "business_stage_key": _STAGE1["key"],
                "business_stage_name": _STAGE1["name"],
                "page_key": page_key,
                "page_name": page_name,
                "protocol_step": None,
                "ent_type": ent_type,
            }

    return {
        "business_stage_key": _STAGE1["key"] if "phase1" in pipeline_name else "unknown",
        "business_stage_name": _STAGE1["name"] if "phase1" in pipeline_name else "未知阶段",
        "page_key": "unknown",
        "page_name": "未知页面",
        "protocol_step": None,
        "ent_type": ent_type,
    }


def classify_result(code: str, result_type: str, ok: bool, optional: bool, message: str = "") -> Dict[str, Any]:
    code = str(code or "")
    result_type = str(result_type or "")
    if ok:
        category = "success"
        if result_type == "2":
            category = "success_with_warning"
        return {
            "category": category,
            "severity": "info" if category == "success" else "warning",
            "meaning": "步骤执行成功" if category == "success" else "步骤成功但包含服务端警告",
            "suggested_action": "继续下一步。",
            "recovery_action": "continue",
            "retryable": False,
            "requires_human": False,
        }

    if code in _CODE_POLICIES:
        policy = dict(_CODE_POLICIES[code])
        if optional and policy.get("severity") == "blocker":
            policy["severity"] = "warning"
            policy["suggested_action"] = "该步骤为 optional，记录后可继续；如果后续失败，再回头确认当前位置。"
            policy["recovery_action"] = "continue_optional"
        return policy

    if code == "00000" and result_type == "1":
        return {
            "category": "business_validation_failed",
            "severity": "blocker",
            "meaning": "服务端业务校验未通过，组件没有保存成功",
            "suggested_action": "读取 msg 定位缺失字段；对照该页面 load busiData 和真实成功请求体补齐字段。",
            "recovery_action": "fix_payload_then_resume",
            "retryable": False,
            "requires_human": False,
        }

    if result_type == "-1":
        return {
            "category": "fatal_result_type",
            "severity": "blocker",
            "meaning": "服务端返回致命 resultType=-1",
            "suggested_action": "停止当前链路，查看完整响应与服务端消息后再处理。",
            "recovery_action": "inspect_response",
            "retryable": False,
            "requires_human": False,
        }

    if not code:
        return {
            "category": "empty_code",
            "severity": "blocker",
            "meaning": "响应中没有标准 code，可能是请求异常或响应格式异常",
            "suggested_action": "查看 raw_response、HTTP 状态和本地异常。",
            "recovery_action": "inspect_transport",
            "retryable": True,
            "requires_human": False,
        }

    return {
        "category": "upstream_rejected",
        "severity": "blocker" if not optional else "warning",
        "meaning": f"服务端返回未归类错误码 {code}",
        "suggested_action": "查看 msg/raw_response，并将该错误码补充进 ErrorPolicy。",
        "recovery_action": "inspect_unknown_code",
        "retryable": False,
        "requires_human": False,
    }


def build_diagnosis(
    *,
    pipeline_name: str,
    step_index: int,
    step_name: str,
    step_tag: str,
    optional: bool,
    result: Any,
    ctx_state: Dict[str, Any],
    case: Dict[str, Any],
) -> Dict[str, Any]:
    page = page_context(pipeline_name, step_name, step_tag, ctx_state, case)
    extracted = dict(getattr(result, "extracted", {}) or {})
    code = str(getattr(result, "code", "") or "")
    result_type = str(getattr(result, "result_type", "") or "")
    message = str(getattr(result, "message", "") or "")
    ok = bool(getattr(result, "ok", False))
    policy = classify_result(code, result_type, ok, optional, message)
    return {
        "schema": "smart_diagnosis.v1",
        "pipeline": pipeline_name,
        "step_index": step_index,
        "step_number": step_index + 1,
        "step_name": step_name,
        "step_tag": step_tag,
        "optional": bool(optional),
        "ok": ok,
        "code": code,
        "result_type": result_type,
        "message": message[:300],
        "business_stage_key": page["business_stage_key"],
        "business_stage_name": page["business_stage_name"],
        "page_key": page["page_key"],
        "page_name": page["page_name"],
        "protocol_step": page["protocol_step"],
        "ent_type": page["ent_type"],
        "current_comp_url": ctx_state.get("current_comp_url"),
        "current_status": ctx_state.get("current_status"),
        "server_curr_comp_url": extracted.get("server_curr_comp_url"),
        "server_status": extracted.get("server_status"),
        "expected_components": extracted.get("expected_components"),
        "expected_statuses": extracted.get("expected_statuses"),
        "observed_current_comp_url": extracted.get("observed_current_comp_url"),
        "allowed_current_components": extracted.get("allowed_current_components"),
        "upstream_code": extracted.get("upstream_code"),
        "attempted_count": extracted.get("attempted_count"),
        "max_executions": extracted.get("max_executions"),
        "last_ok_step_index": ctx_state.get("last_ok_step_index"),
        "last_ok_step_name": ctx_state.get("last_ok_step_name"),
        "category": policy["category"],
        "severity": policy["severity"],
        "meaning": policy["meaning"],
        "suggested_action": policy["suggested_action"],
        "recovery_action": policy["recovery_action"],
        "retryable": bool(policy["retryable"]),
        "requires_human": bool(policy["requires_human"]),
    }


def compact_problem(diagnosis: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "business_stage_name",
        "page_name",
        "protocol_step",
        "step_name",
        "code",
        "result_type",
        "message",
        "category",
        "severity",
        "meaning",
        "suggested_action",
        "recovery_action",
        "current_comp_url",
        "current_status",
        "server_curr_comp_url",
        "server_status",
        "expected_components",
        "expected_statuses",
        "observed_current_comp_url",
        "allowed_current_components",
        "upstream_code",
        "attempted_count",
        "max_executions",
    ]
    return {k: diagnosis.get(k) for k in keys if diagnosis.get(k) is not None}
