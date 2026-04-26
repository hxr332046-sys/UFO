from __future__ import annotations

from orchestrator.core import StepResult
from orchestrator.hooks import SmartDiagnosisHook, default_hooks
from orchestrator.intelligence import build_diagnosis


def test_phase2_ybb_select_step_maps_to_business_page():
    result = StepResult(
        name="establish/YbbSelect/operationBusinessDataInfo [save]",
        ok=False,
        code="00000",
        result_type="1",
        message="请选择业务流程模式！",
    )

    diagnosis = build_diagnosis(
        pipeline_name="phase2_establish",
        step_index=22,
        step_name="[23] establish/YbbSelect/operationBusinessDataInfo [save]",
        step_tag="p2_step23",
        optional=False,
        result=result,
        ctx_state={},
        case={"entType_default": "4540"},
    )

    assert diagnosis["business_stage_key"] == "stage2_info_filling"
    assert diagnosis["page_key"] == "ybb_select"
    assert diagnosis["page_name"] == "云帮办流程模式选择"
    assert diagnosis["category"] == "business_validation_failed"
    assert diagnosis["recovery_action"] == "fix_payload_then_resume"


def test_d0018_is_business_status_changed_and_probe_progress():
    result = StepResult(
        name="establish/PreElectronicDoc/operationBusinessDataInfo [save]",
        ok=False,
        code="D0018",
        result_type="",
        message="业务状态已发生变化",
    )

    diagnosis = build_diagnosis(
        pipeline_name="phase2_establish",
        step_index=23,
        step_name="[24] establish/PreElectronicDoc/operationBusinessDataInfo [save]",
        step_tag="p2_step24",
        optional=False,
        result=result,
        ctx_state={"current_comp_url": "PreElectronicDoc", "current_status": "10"},
        case={"entType_default": "4540"},
    )

    assert diagnosis["page_key"] == "pre_electronic_doc"
    assert diagnosis["category"] == "business_status_changed"
    assert diagnosis["severity"] == "recoverable"
    assert diagnosis["recovery_action"] == "probe_progress_then_resume"
    assert diagnosis["retryable"] is False


def test_step_position_guard_has_probe_current_position_advice():
    result = StepResult(
        name="establish/PreElectronicDoc/operationBusinessDataInfo [save]",
        ok=False,
        code="STEP_POSITION_GUARD",
        message="被本地编排护栏拦截",
        extracted={
            "observed_current_comp_url": "YbbSelect",
            "allowed_current_components": ["PreElectronicDoc"],
        },
    )

    diagnosis = build_diagnosis(
        pipeline_name="phase2_establish",
        step_index=23,
        step_name="[24] establish/PreElectronicDoc/operationBusinessDataInfo [save]",
        step_tag="p2_step24",
        optional=False,
        result=result,
        ctx_state={"current_comp_url": "YbbSelect", "current_status": "10"},
        case={"entType_default": "4540"},
    )

    assert diagnosis["category"] == "step_position_guard"
    assert diagnosis["recovery_action"] == "probe_current_position_then_resume"
    assert diagnosis["observed_current_comp_url"] == "YbbSelect"
    assert diagnosis["allowed_current_components"] == ["PreElectronicDoc"]


def test_name_id_expired_code_requests_phase1_refresh():
    result = StepResult(
        name="establish/YbbSelect/operationBusinessDataInfo [save]",
        ok=False,
        code="GS52010400B0017",
        message="",
    )

    diagnosis = build_diagnosis(
        pipeline_name="phase2_establish",
        step_index=22,
        step_name="[23] establish/YbbSelect/operationBusinessDataInfo [save]",
        step_tag="p2_step23",
        optional=False,
        result=result,
        ctx_state={"current_comp_url": "YbbSelect", "current_status": "10"},
        case={"entType_default": "4540"},
    )

    assert diagnosis["category"] == "name_id_expired"
    assert diagnosis["recovery_action"] == "refresh_name_id_then_resume"
    assert "重跑 Phase 1" in diagnosis["suggested_action"]


def test_name_check_stop_requests_rename_or_release():
    result = StepResult(
        name="NameCheckInfo/nameCheckRepeat",
        ok=False,
        code="NAME_CHECK_STOP",
        result_type="0",
        message="名称库查重返回 stop，当前名称不能继续提交",
        extracted={
            "checkState_reported": 2,
            "langStateCode": "register.msg.namecheck.state.stop",
        },
    )

    diagnosis = build_diagnosis(
        pipeline_name="phase1_name_check",
        step_index=5,
        step_name="NameCheckInfo/nameCheckRepeat",
        step_tag="p1_query",
        optional=False,
        result=result,
        ctx_state={},
        case={"entType_default": "4540"},
    )

    assert diagnosis["page_key"] == "name_repeat_check"
    assert diagnosis["category"] == "name_check_stop"
    assert diagnosis["recovery_action"] == "rename_then_restart_phase1"
    assert "更换字号" in diagnosis["suggested_action"]


def test_step_result_dict_includes_diagnostics():
    result = StepResult(name="x", ok=False, code="D0022")
    result.diagnostics = {"category": "privilege_or_contract_mismatch"}

    data = result.to_dict()

    assert data["diagnostics"]["category"] == "privilege_or_contract_mismatch"


def test_default_hooks_include_smart_diagnosis_hook():
    hooks = default_hooks()

    assert any(isinstance(h, SmartDiagnosisHook) for h in hooks)
