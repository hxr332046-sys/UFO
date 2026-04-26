from __future__ import annotations

from pathlib import Path

from orchestrator.adapters import Phase2Adapter
from orchestrator.core import Hook, InterventionSignal, Pipeline, PipelineContext, StepResult, StepSpec
from orchestrator.hooks import StateExtractorHook
from phase1_protocol_driver import DriverContext, step_namecheck_repeat


class _RetryOnceHook(Hook):
    def on_step_end(self, index: int, step: StepSpec, result: StepResult,
                    ctx: PipelineContext) -> None:
        if ctx.state.get("_retried_once"):
            return
        ctx.state["_retried_once"] = True
        raise InterventionSignal(kind="manual_retry", diagnostics={}, options=["retry"], message="retry once")

    def on_intervention(self, signal: InterventionSignal, ctx: PipelineContext) -> str:
        if signal.kind == "manual_retry":
            return "retry"
        return "abort"


def _make_ctx(tmp_path: Path, case: dict | None = None) -> PipelineContext:
    case_path = tmp_path / "guard-case.json"
    case_path.write_text("{}", encoding="utf-8")
    return PipelineContext(case=dict(case or {"entType_default": "4540"}), case_path=case_path, client=None)


def test_pipeline_blocks_step_without_feedback(tmp_path: Path):
    ctx = _make_ctx(tmp_path)
    pipe = Pipeline(
        "guard_no_feedback",
        steps=[
            StepSpec(
                name="blind_step",
                fn=lambda client, state: StepResult(name="blind_step", ok=True, code="00000"),
                delay_after_s=0,
            )
        ],
    )

    result = pipe.run(ctx)

    assert result.success is False
    assert result.steps[0]["code"] == "STEP_NO_FEEDBACK"


def test_pipeline_blocks_excessive_same_step_execution(tmp_path: Path):
    ctx = _make_ctx(tmp_path)
    pipe = Pipeline(
        "guard_execution_limit",
        steps=[
            StepSpec(
                name="retry_guard_step",
                fn=lambda client, state: StepResult(name="retry_guard_step", ok=True, code="00000", extracted={"seen": True}),
                delay_after_s=0,
                max_executions=1,
            )
        ],
        hooks=[_RetryOnceHook()],
    )

    result = pipe.run(ctx)

    assert result.success is False
    assert result.steps[0]["code"] == "STEP_EXECUTION_GUARD"
    assert result.steps[0]["extracted"]["attempted_count"] == 2


def test_phase2_tail_step_requires_known_position_feedback(minimal_case: dict, tmp_path: Path):
    case = dict(minimal_case)
    ctx = _make_ctx(tmp_path, case)
    adapter = Phase2Adapter(case, "P1-001", "NAME-001")
    step24 = next(step for step in adapter.make_steps("4540") if step.name.startswith("[24]"))

    result = step24.fn(None, ctx)

    assert result.ok is False
    assert result.code == "STEP_POSITION_GUARD"
    assert result.extracted["allowed_current_components"] == ["PreElectronicDoc"]


def test_phase2_tail_step_blocks_position_mismatch(minimal_case: dict, tmp_path: Path):
    case = dict(minimal_case)
    ctx = _make_ctx(tmp_path, case)
    ctx.state["current_comp_url"] = "YbbSelect"
    adapter = Phase2Adapter(case, "P1-001", "NAME-001")
    step24 = next(step for step in adapter.make_steps("4540") if step.name.startswith("[24]"))

    result = step24.fn(None, ctx)

    assert result.ok is False
    assert result.code == "STEP_POSITION_GUARD"
    assert result.extracted["observed_current_comp_url"] == "YbbSelect"
    assert result.extracted["allowed_current_components"] == ["PreElectronicDoc"]


def test_phase2_resume_realigns_ybbselect_to_actionable_save_step(minimal_case: dict):
    adapter = Phase2Adapter(dict(minimal_case), "P1-001", "NAME-001")

    start_from = adapter.recommend_start_from("YbbSelect", fallback_index=23, ent_type="4540")

    assert start_from == 22


def test_phase2_resume_realigns_namesuccess_to_establish_entry_step(minimal_case: dict):
    adapter = Phase2Adapter(dict(minimal_case), "P1-001", "NAME-001")

    start_from = adapter.recommend_start_from("NameSuccess", fallback_index=8, ent_type="4540")

    assert start_from == 9


def test_phase2_resume_realigns_presubmitsuccess_to_terminal_load(minimal_case: dict):
    adapter = Phase2Adapter(dict(minimal_case), "P1-001", "NAME-001")

    start_from = adapter.recommend_start_from("PreSubmitSuccess", fallback_index=22, ent_type="4540")

    assert start_from == 24


def test_phase2_business_licence_way_has_expected_progress(minimal_case: dict):
    adapter = Phase2Adapter(dict(minimal_case), "P1-001", "NAME-001")

    step22 = next(step for step in adapter.make_steps("4540") if step.name.startswith("[22]"))

    assert step22.expected_progress["mode"] == "must_leave_component"
    assert step22.expected_progress["from_component"] == "BusinessLicenceWay"
    assert "YbbSelect" in step22.expected_progress["expected_components"]


def test_phase2_must_leave_component_uses_position_probe(monkeypatch, minimal_case: dict, tmp_path: Path):
    import phase2_protocol_driver

    adapter = Phase2Adapter(dict(minimal_case), "P1-001", "NAME-001")

    def fake_save(_client, _p2_ctx):
        return {
            "code": "00000",
            "data": {
                "resultType": "0",
                "busiData": {
                    "flowData": {
                        "busiId": "EST-001",
                        "nameId": "NAME-001",
                        "currCompUrl": "BusinessLicenceWay",
                        "status": "10",
                        "busiType": "02",
                    }
                },
            },
        }

    def fake_probe(_client, _p2_ctx):
        return {
            "code": "00000",
            "data": {
                "resultType": "0",
                "busiData": {
                    "flowData": {
                        "busiId": "EST-001",
                        "nameId": "NAME-001",
                        "currCompUrl": "YbbSelect",
                        "status": "10",
                        "busiType": "02",
                    }
                },
            },
        }

    monkeypatch.setattr(phase2_protocol_driver, "step12_establish_location", fake_probe)
    wrapped = adapter._wrap(
        fake_save,
        "establish/BusinessLicenceWay/operationBusinessDataInfo [save]",
        22,
        {
            "mode": "must_leave_component",
            "from_component": "BusinessLicenceWay",
            "expected_components": ["YbbSelect"],
        },
        {},
    )
    ctx = _make_ctx(tmp_path, minimal_case)

    result = wrapped(None, ctx)

    assert result.ok is True
    assert result.extracted["server_curr_comp_url"] == "YbbSelect"
    assert result.extracted["position_probe_code"] == "00000"


def test_phase2_native_next_load_step_can_skip_post_mutation_probe(monkeypatch, minimal_case: dict, tmp_path: Path):
    import phase2_protocol_driver

    adapter = Phase2Adapter(dict(minimal_case), "P1-001", "NAME-001")

    def fake_native_step(_client, _p2_ctx):
        return {
            "code": "00000",
            "_protocol_extracted": {"ybb_transition_mode": "save_then_load"},
            "data": {
                "resultType": "0",
                "busiData": {
                    "flowData": {
                        "busiId": "EST-001",
                        "nameId": "NAME-001",
                        "currCompUrl": "PreElectronicDoc",
                        "status": "10",
                        "busiType": "02",
                    }
                },
            },
        }

    def boom_probe(_client, _p2_ctx):
        raise AssertionError("position probe should be skipped for native next-load steps")

    monkeypatch.setattr(phase2_protocol_driver, "step12_establish_location", boom_probe)
    wrapped = adapter._wrap(
        fake_native_step,
        "establish/YbbSelect/operationBusinessDataInfo [save]",
        23,
        {
            "mode": "must_leave_component",
            "from_component": "YbbSelect",
            "expected_components": ["PreElectronicDoc", "PreSubmitSuccess"],
            "probe_after_mutation": False,
        },
        {},
    )
    ctx = _make_ctx(tmp_path, minimal_case)

    result = wrapped(None, ctx)

    assert result.ok is True
    assert result.extracted["server_curr_comp_url"] == "PreElectronicDoc"
    assert result.extracted["ybb_transition_mode"] == "save_then_load"


def test_step23_ybbselect_d0010_followup_is_not_treated_as_confirmed_advancement(minimal_case: dict):
    import phase2_protocol_driver

    class FakeClient:
        def post_json(self, url, body, extra_headers=None):
            if url.endswith("/component/YbbSelect/loadBusinessDataInfo"):
                return {
                    "code": "00000",
                    "data": {
                        "resultType": "0",
                        "busiData": {
                            "flowData": {
                                "busiId": "EST-001",
                                "entType": "4540",
                                "busiType": "02",
                                "ywlbSign": "4",
                                "nameId": "NAME-001",
                                "currCompUrl": "YbbSelect",
                                "status": "10",
                            },
                            "linkData": {
                                "token": "",
                                "continueFlag": None,
                                "compUrl": "YbbSelect",
                                "compUrlPaths": ["YbbSelect"],
                                "busiCompComb": {"id": "COMB-001"},
                                "compCombArr": ["YbbSelect", "PreElectronicDoc"],
                                "opeType": "load",
                                "busiCompUrlPaths": "%5B%5D",
                            },
                            "signInfo": "1425944578",
                            "itemId": "",
                            "isOptional": "1",
                            "preAuditSign": None,
                            "isSelectYbb": "0",
                        },
                    },
                }
            if url.endswith("/component/YbbSelect/operationBusinessDataInfo"):
                return {
                    "code": "00000",
                    "data": {
                        "resultType": "0",
                        "msg": "操作成功",
                        "busiData": {
                            "flowData": {
                                "busiId": "EST-001",
                                "entType": "4540",
                                "busiType": "02",
                                "ywlbSign": "4",
                                "nameId": "NAME-001",
                                "currCompUrl": "YbbSelect",
                                "status": "10",
                            },
                            "linkData": {
                                "token": "",
                                "continueFlag": None,
                                "compUrl": "YbbSelect",
                                "compUrlPaths": ["YbbSelect"],
                                "busiCompComb": {"id": "COMB-001"},
                                "compCombArr": ["YbbSelect", "PreElectronicDoc"],
                                "opeType": "save",
                                "busiCompUrlPaths": "%5B%5D",
                            },
                            "signInfo": "1425944578",
                        },
                    },
                }
            if url.endswith("/component/PreElectronicDoc/loadBusinessDataInfo"):
                return {
                    "code": "D0010",
                    "msg": "当前表单无需填写",
                    "data": {
                        "msg": "当前表单无需填写",
                    },
                }
            raise AssertionError(url)

    ctx = phase2_protocol_driver.Phase2Context.from_case(dict(minimal_case), "P1-001")
    ctx.name_id = "NAME-001"
    ctx.snapshot["establish_busiId"] = "EST-001"

    resp = phase2_protocol_driver.step23_ybb_select_save(FakeClient(), ctx)

    assert resp["code"] == "00000"
    assert resp["_protocol_extracted"]["ybb_followup_code"] == "D0010"
    assert resp["_protocol_extracted"]["ybb_followup_accessible"] is False
    assert resp["data"]["busiData"]["flowData"]["currCompUrl"] == "YbbSelect"
    assert ctx.snapshot["last_save_flowData"]["currCompUrl"] == "YbbSelect"


def test_step24_pre_electronic_doc_success_followup_reaches_pre_submit_success(minimal_case: dict):
    import phase2_protocol_driver

    class FakeClient:
        def post_json(self, url, body, extra_headers=None):
            if url.endswith("/component/PreElectronicDoc/loadBusinessDataInfo"):
                return {
                    "code": "D0010",
                    "msg": "当前表单无需填写",
                    "data": {
                        "msg": "当前表单无需填写",
                    },
                }
            if url.endswith("/component/PreElectronicDoc/operationBusinessDataInfo"):
                return {
                    "code": "00000",
                    "data": {
                        "resultType": "0",
                        "msg": "操作成功",
                        "busiData": {
                            "flowData": {
                                "busiId": "EST-001",
                                "entType": "4540",
                                "busiType": "02",
                                "ywlbSign": "4",
                                "nameId": "NAME-001",
                                "currCompUrl": "PreElectronicDoc",
                                "status": "10",
                            },
                            "linkData": {
                                "token": "",
                                "continueFlag": None,
                                "compUrl": "PreElectronicDoc",
                                "compUrlPaths": ["PreElectronicDoc"],
                                "opeType": "save",
                                "busiCompUrlPaths": "%5B%5D",
                            },
                            "signInfo": "1425944578",
                        },
                    },
                }
            if url.endswith("/component/PreSubmitSuccess/loadBusinessDataInfo"):
                return {
                    "code": "00000",
                    "data": {
                        "resultType": "0",
                        "msg": "操作成功",
                        "busiData": {
                            "flowData": {
                                "busiId": "EST-001",
                                "entType": "4540",
                                "busiType": "02",
                                "ywlbSign": "4",
                                "nameId": "NAME-001",
                                "currCompUrl": "PreSubmitSuccess",
                                "status": "90",
                            },
                            "linkData": {
                                "token": "",
                                "compUrl": "PreSubmitSuccess",
                                "compUrlPaths": ["PreSubmitSuccess"],
                                "opeType": "load",
                            },
                            "signInfo": "1425944578",
                        },
                    },
                }
            raise AssertionError(url)

    ctx = phase2_protocol_driver.Phase2Context.from_case(dict(minimal_case), "P1-001")
    ctx.name_id = "NAME-001"
    ctx.snapshot["establish_busiId"] = "EST-001"
    ctx.snapshot["last_save_flowData"] = {
        "busiId": "EST-001",
        "entType": "4540",
        "busiType": "02",
        "ywlbSign": "4",
        "nameId": "NAME-001",
        "currCompUrl": "PreElectronicDoc",
        "status": "10",
    }
    ctx.snapshot["last_save_linkData"] = {
        "token": "",
        "continueFlag": None,
        "compUrl": "PreElectronicDoc",
        "compUrlPaths": ["PreElectronicDoc"],
        "opeType": "load",
        "busiCompUrlPaths": "%5B%5D",
    }
    ctx.snapshot["last_sign_info"] = "1425944578"

    resp = phase2_protocol_driver.step24_pre_electronic_doc_advance(FakeClient(), ctx)

    assert resp["code"] == "00000"
    assert resp["_protocol_extracted"]["pre_doc_action_semantics"] == "pre_submit_ybb"
    assert resp["_protocol_extracted"]["pre_doc_followup_component"] == "PreSubmitSuccess"
    assert resp["_protocol_extracted"]["pre_doc_followup_status"] == "90"
    assert resp["data"]["busiData"]["flowData"]["currCompUrl"] == "PreSubmitSuccess"
    assert ctx.snapshot["last_save_flowData"]["currCompUrl"] == "PreSubmitSuccess"


def test_step24_pre_electronic_doc_d0018_is_treated_as_already_progressed_when_followup_load_succeeds(minimal_case: dict):
    import phase2_protocol_driver

    class FakeClient:
        def post_json(self, url, body, extra_headers=None):
            if url.endswith("/component/PreElectronicDoc/loadBusinessDataInfo"):
                return {
                    "code": "D0010",
                    "msg": "当前表单无需填写",
                    "data": {
                        "msg": "当前表单无需填写",
                    },
                }
            if url.endswith("/component/PreElectronicDoc/operationBusinessDataInfo"):
                return {
                    "code": "D0018",
                    "msg": "业务状态已发生变化",
                    "data": {
                        "msg": "业务状态已发生变化",
                    },
                }
            if url.endswith("/component/PreSubmitSuccess/loadBusinessDataInfo"):
                return {
                    "code": "00000",
                    "data": {
                        "resultType": "0",
                        "msg": "操作成功",
                        "busiData": {
                            "flowData": {
                                "busiId": "EST-001",
                                "entType": "4540",
                                "busiType": "02",
                                "ywlbSign": "4",
                                "nameId": "NAME-001",
                                "currCompUrl": "PreSubmitSuccess",
                                "status": "90",
                            },
                            "linkData": {
                                "token": "",
                                "compUrl": "PreSubmitSuccess",
                                "compUrlPaths": ["PreSubmitSuccess"],
                                "opeType": "load",
                            },
                            "signInfo": "1425944578",
                        },
                    },
                }
            raise AssertionError(url)

    ctx = phase2_protocol_driver.Phase2Context.from_case(dict(minimal_case), "P1-001")
    ctx.name_id = "NAME-001"
    ctx.snapshot["establish_busiId"] = "EST-001"
    ctx.snapshot["last_save_flowData"] = {
        "busiId": "EST-001",
        "entType": "4540",
        "busiType": "02",
        "ywlbSign": "4",
        "nameId": "NAME-001",
        "currCompUrl": "PreElectronicDoc",
        "status": "10",
    }
    ctx.snapshot["last_save_linkData"] = {
        "token": "",
        "continueFlag": None,
        "compUrl": "PreElectronicDoc",
        "compUrlPaths": ["PreElectronicDoc"],
        "opeType": "load",
        "busiCompUrlPaths": "%5B%5D",
    }
    ctx.snapshot["last_sign_info"] = "1425944578"

    resp = phase2_protocol_driver.step24_pre_electronic_doc_advance(FakeClient(), ctx)

    assert resp["code"] == "00000"
    assert resp["_protocol_extracted"]["pre_doc_submit_code"] == "D0018"
    assert resp["_protocol_extracted"]["pre_doc_followup_accessible"] is True
    assert resp["data"]["busiData"]["flowData"]["currCompUrl"] == "PreSubmitSuccess"
    assert ctx.snapshot["last_save_flowData"]["status"] == "90"


def test_step12_establish_location_does_not_reuse_phase1_busi_id_without_establish_context(minimal_case: dict):
    import phase2_protocol_driver

    captured = {}

    class FakeClient:
        def post_json(self, url, body, extra_headers=None):
            captured["url"] = url
            captured["body"] = body
            return {
                "code": "00000",
                "data": {
                    "resultType": "0",
                    "busiData": {
                        "flowData": {
                            "busiId": None,
                            "entType": "4540",
                            "busiType": "02",
                            "nameId": "NAME-NEW-001",
                            "status": "10",
                        }
                    },
                },
            }

    ctx = phase2_protocol_driver.Phase2Context.from_case(dict(minimal_case), "P1-001")
    ctx.phase1_busi_id = "P1-001"
    ctx.busi_id = "P1-001"
    ctx.name_id = "NAME-NEW-001"

    resp = phase2_protocol_driver.step12_establish_location(FakeClient(), ctx)

    assert resp["code"] == "00000"
    assert captured["url"].endswith("/register/establish/loadCurrentLocationInfo")
    assert captured["body"]["flowData"]["busiId"] is None
    assert captured["body"]["flowData"]["busiType"] == "02_4"
    assert captured["body"]["flowData"]["nameId"] == "NAME-NEW-001"


def test_phase1_namecheck_repeat_stop_state_fails_fast():
    case = {
        "entType_default": "4540",
        "phase1_dist_codes": ["450000", "450900", "450921"],
        "region_text": "广西容县",
        "name_mark": "兴裕为",
        "phase1_name_pre": "广西容县",
        "phase1_organize": "中心（个人独资）",
        "phase1_industry_code": "6513",
        "phase1_industry_name": "应用软件开发",
        "phase1_industry_special": "软件开发",
        "phase1_check_name": "兴裕为（广西容县）软件开发中心（个人独资）",
    }
    driver_ctx = DriverContext.from_case(case)

    class _Client:
        def post_json(self, _url, _body):
            return {
                "code": "00000",
                "data": {
                    "resultType": "0",
                    "busiData": {
                        "checkState": 2,
                        "langStateCode": "register.msg.namecheck.state.stop",
                        "checkResult": [
                            {"entName": "兴裕为软件开发中心（个人独资）"},
                        ],
                    },
                },
            }

    result, raw = step_namecheck_repeat(_Client(), driver_ctx)

    assert result.ok is False
    assert result.code == "NAME_CHECK_STOP"
    assert result.extracted["name_check_stop"] is True
    assert result.extracted["checkState_reported"] == 2
    assert "更换字号后重跑" in result.reason
    assert raw is not None


def test_state_extractor_prefers_probed_server_position_over_raw_response(tmp_path: Path):
    ctx = _make_ctx(tmp_path, {"entType_default": "4540"})
    result = StepResult(
        name="[22] establish/BusinessLicenceWay/operationBusinessDataInfo [save]",
        ok=True,
        code="00000",
        extracted={
            "server_curr_comp_url": "YbbSelect",
            "server_status": "10",
            "busiId": "EST-001",
            "nameId": "NAME-001",
        },
        raw_response={
            "data": {
                "busiData": {
                    "flowData": {
                        "busiId": "EST-001",
                        "nameId": "NAME-001",
                        "currCompUrl": "BusinessLicenceWay",
                        "status": "10",
                        "busiType": "02",
                        "entType": "4540",
                    }
                }
            }
        },
    )

    StateExtractorHook().on_step_end(21, StepSpec(name=result.name, fn=lambda *_: result), result, ctx)

    assert ctx.state["server_curr_comp_url"] == "YbbSelect"
    assert ctx.state["current_comp_url"] == "YbbSelect"
