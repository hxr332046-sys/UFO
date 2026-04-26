from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import run_smart_register
from run_smart_register import SmartRegisterRunner



def _make_runner(tmp_path: Path, case: dict | None = None) -> SmartRegisterRunner:
    payload = dict(case or {
        "case_id": "CASE-001",
        "entType_default": "4540",
        "name_mark": "测试",
        "phase1_check_name": "测试（广西容县）软件开发中心（个人独资）",
    })
    case_path = tmp_path / "runner-case.json"
    case_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    runner = SmartRegisterRunner(case_path)
    runner.case = dict(payload)
    return runner



def test_extract_phase2_recovery_guard_reads_name_expired_failure(tmp_path: Path):
    runner = _make_runner(tmp_path)

    guard = runner._extract_phase2_recovery_guard({
        "context_state": {
            "name_id": "NAME-OLD-001",
            "phase1_busi_id": "BUSI-001",
            "current_comp_url": "YbbSelect",
            "current_status": "10",
        },
        "failure": {
            "failed_step_code": "GS52010400B0017",
            "failed_step_name": "[23] establish/YbbSelect/operationBusinessDataInfo [save]",
            "failed_step_index": 22,
            "diagnosis": {
                "page_name": "云帮办流程模式选择",
                "meaning": "名称保留期限超期，旧 nameId 已失效",
                "suggested_action": "先刷新有效 nameId",
                "recovery_action": "refresh_name_id_then_resume",
            },
        },
    })

    assert guard["failed_code"] == "GS52010400B0017"
    assert guard["recovery_action"] == "refresh_name_id_then_resume"
    assert guard["saved_name_id"] == "NAME-OLD-001"
    assert guard["current_comp_url"] == "YbbSelect"



def test_force_phase1_refresh_clears_direct_resume_state(tmp_path: Path):
    runner = _make_runner(tmp_path)
    runner.resume_candidate = {"busi_id": "BUSI-001", "name_id": "NAME-OLD-001"}
    runner.resume_source = "active_matter"
    runner.phase1_busi_id = "BUSI-001"
    runner.phase1_name_id = "NAME-OLD-001"
    runner.establish_busi_id = "BUSI-001"
    runner.phase2_start_from = 23

    runner._force_phase1_refresh_for_guard({
        "failed_code": "GS52010400B0017",
        "recovery_action": "refresh_name_id_then_resume",
        "saved_name_id": "NAME-OLD-001",
    })

    assert runner.resume_candidate is None
    assert runner.resume_source == "phase1_name_refresh_required"
    assert runner.phase1_busi_id is None
    assert runner.phase1_name_id is None
    assert runner.establish_busi_id is None
    assert runner.phase2_start_from == 0



def test_block_unresolved_name_refresh_prevents_same_phase2_retry(tmp_path: Path):
    runner = _make_runner(tmp_path)
    runner.phase1_busi_id = "BUSI-001"
    runner.phase1_name_id = "NAME-OLD-001"
    runner.phase2_recovery_guard = {
        "failed_code": "GS52010400B0017",
        "failed_step_name": "[23] establish/YbbSelect/operationBusinessDataInfo [save]",
        "failed_step_index": 22,
        "recovery_action": "refresh_name_id_then_resume",
        "page_name": "云帮办流程模式选择",
        "current_comp_url": "YbbSelect",
        "current_status": "10",
        "saved_name_id": "NAME-OLD-001",
    }

    blocked = runner._block_unresolved_phase2_recovery()

    assert blocked is True
    assert runner.final_status == "phase2_recovery_guard"
    assert runner.last_diagnosis["category"] == "name_id_expired"
    assert runner.last_diagnosis["recovery_action"] == "refresh_name_id_then_resume"
    assert "新的 nameId" in runner.last_diagnosis["suggested_action"]



def test_phase2_recovery_resolved_requires_new_name_id_or_login(tmp_path: Path):
    runner = _make_runner(tmp_path)

    name_guard = {
        "failed_code": "GS52010400B0017",
        "recovery_action": "refresh_name_id_then_resume",
        "saved_name_id": "NAME-OLD-001",
    }
    runner.phase1_name_id = "NAME-OLD-001"
    assert runner._phase2_recovery_resolved(name_guard) is False
    runner.phase1_name_id = "NAME-NEW-002"
    assert runner._phase2_recovery_resolved(name_guard) is True

    session_guard = {
        "failed_code": "GS52010103E0302",
        "recovery_action": "refresh_session_then_resume",
    }
    runner.do_login = False
    assert runner._phase2_recovery_resolved(session_guard) is False
    runner.do_login = True
    assert runner._phase2_recovery_resolved(session_guard) is True

    contract_guard = {
        "failed_code": "STEP_NOT_ADVANCED",
        "recovery_action": "inspect_progress_contract_then_resume",
    }
    assert runner._phase2_recovery_resolved(contract_guard) is True
    contract_guard["saved_progress_contract_version"] = run_smart_register.PHASE2_PROGRESS_CONTRACT_VERSION
    assert runner._phase2_recovery_resolved(contract_guard) is False
    contract_guard["progress_contract_reviewed"] = True
    assert runner._phase2_recovery_resolved(contract_guard) is True


def test_block_unresolved_step_not_advanced_prevents_same_step_retry(tmp_path: Path):
    runner = _make_runner(tmp_path)
    runner.phase2_recovery_guard = {
        "failed_code": "STEP_NOT_ADVANCED",
        "failed_step_name": "[23] establish/YbbSelect/operationBusinessDataInfo [save]",
        "failed_step_index": 22,
        "recovery_action": "inspect_progress_contract_then_resume",
        "saved_progress_contract_version": run_smart_register.PHASE2_PROGRESS_CONTRACT_VERSION,
        "page_name": "云帮办流程模式选择",
        "current_comp_url": "YbbSelect",
        "current_status": "10",
    }

    blocked = runner._block_unresolved_phase2_recovery()

    assert blocked is True
    assert runner.final_status == "phase2_recovery_guard"
    assert runner.last_diagnosis["category"] == "step_not_advanced"
    assert runner.last_diagnosis["recovery_action"] == "inspect_progress_contract_then_resume"
    assert "协议合同检查" in runner.last_diagnosis["suggested_action"]


def test_legacy_step_not_advanced_guard_allows_retry_after_contract_upgrade(tmp_path: Path):
    runner = _make_runner(tmp_path)
    runner.phase2_recovery_guard = {
        "failed_code": "STEP_NOT_ADVANCED",
        "failed_step_name": "[23] establish/YbbSelect/operationBusinessDataInfo [save]",
        "failed_step_index": 22,
        "recovery_action": "inspect_progress_contract_then_resume",
        "saved_progress_contract_version": 0,
        "page_name": "云帮办流程模式选择",
        "current_comp_url": "YbbSelect",
        "current_status": "10",
    }

    blocked = runner._block_unresolved_phase2_recovery()

    assert blocked is False


def test_ignore_stale_phase2_checkpoint_after_name_refresh(tmp_path: Path):
    runner = _make_runner(tmp_path)
    runner.phase2_recovery_guard = {
        "failed_code": "GS52010400B0017",
        "recovery_action": "refresh_name_id_then_resume",
        "saved_name_id": "NAME-OLD-001",
    }

    runner.phase1_name_id = "NAME-OLD-001"
    assert runner._should_ignore_phase2_checkpoint() is False

    runner.phase1_name_id = "NAME-NEW-002"
    assert runner._should_ignore_phase2_checkpoint() is True


def test_phase2_resume_candidate_must_be_establish_and_have_name_id(tmp_path: Path):
    runner = _make_runner(tmp_path)

    assert runner._is_establish_resume_candidate({"busiType": "02_4", "nameId": "NAME-001"}) is True
    assert runner._is_establish_resume_candidate({"busiType": "02", "name_id": "NAME-002"}) is True
    assert runner._is_establish_resume_candidate({"busiType": "01", "nameId": "NAME-001"}) is False
    assert runner._is_establish_resume_candidate({"busiType": "02_4", "nameId": None}) is False


def test_pick_resume_candidate_ignores_non_establish_active_matters(tmp_path: Path):
    runner = _make_runner(tmp_path)

    chosen = runner._pick_resume_candidate([
        {
            "name": runner.case["phase1_check_name"],
            "busi_id": "BUSI-OLD-001",
            "busiType": "01",
            "nameId": None,
            "entType": "4540",
        }
    ])

    assert chosen is None


def test_check_duplicate_does_not_block_non_establish_active_matter(tmp_path: Path):
    runner = _make_runner(tmp_path)

    class FakeClient:
        def get_json(self, path, params=None):
            assert path.endswith("/mattermanager/matters/search")
            return {
                "code": "00000",
                "data": {
                    "busiData": [
                        {
                            "entName": runner.case["phase1_check_name"],
                            "id": "BUSI-NAME-001",
                            "matterStateCode": "10",
                            "busiType": "01",
                            "nameId": None,
                            "entType": "4540",
                        }
                    ]
                },
            }

    runner.client = FakeClient()

    assert runner.check_duplicate() is True
    assert runner.resume_candidate is None


def test_run_name_completion_reuses_phase2_steps_1_to_9(monkeypatch, tmp_path: Path):
    runner = _make_runner(tmp_path)
    runner.phase1_busi_id = "BUSI-NAME-001"
    runner.client = object()

    class FakeAdapter:
        def __init__(self, case, busi_id, name_id=None):
            assert busi_id == "BUSI-NAME-001"
            assert name_id is None
            self.p2_ctx = SimpleNamespace(name_id="NAME-FROM-ADAPTER")

        def make_steps(self, ent_type=None):
            return ["step"] * 25

    class FakePipeline:
        def __init__(self, name, steps, hooks):
            assert name == "phase1_name_completion"
            assert len(steps) == 25

        def run(self, ctx, start_from=0, stop_after=None):
            assert start_from == 0
            assert stop_after == 9
            ctx.name_id = "NAME-FROM-CTX"
            ctx.state["phase2_driver_name_id"] = "NAME-FROM-STATE"
            return SimpleNamespace(success=True, exit_reason=None, exit_detail=None)

    monkeypatch.setattr(run_smart_register, "Phase2Adapter", FakeAdapter)
    monkeypatch.setattr(run_smart_register, "Pipeline", FakePipeline)

    assert runner.run_name_completion() is True
    assert runner.phase1_name_id == "NAME-FROM-CTX"
    assert runner.phase2_start_from == 9


def test_phase2_resume_realign_prefers_server_component_over_stale_local_state(monkeypatch, tmp_path: Path):
    runner = _make_runner(tmp_path)
    runner.phase1_busi_id = "BUSI-001"
    runner.phase1_name_id = "NAME-001"
    runner.client = object()

    class FakeAdapter:
        def __init__(self, case, busi_id, name_id=None):
            self.p2_ctx = SimpleNamespace(name_id=name_id, busi_id="EST-001", ent_type="4540", busi_type="02")

        def make_steps(self, ent_type=None):
            return ["step"] * 25

        def restore_from_pipeline_ctx(self, ctx):
            return None

        def probe_current_location(self, client, ctx):
            ctx.state["server_curr_comp_url"] = "YbbSelect"
            ctx.state["current_comp_url"] = "YbbSelect"
            ctx.state["server_status"] = "10"
            ctx.state["current_status"] = "10"
            return {"server_curr_comp_url": "YbbSelect", "server_status": "10"}

        def recommend_start_from(self, observed_component, fallback_index=0, ent_type=None):
            assert observed_component == "YbbSelect"
            return 22

    class FakeCheckpoint:
        def __init__(self, _path):
            pass

        def load(self, pipeline_name, case_path=None, case=None):
            return {
                "status": "failed",
                "failure": {"failed_step_code": "STEP_POSITION_GUARD"},
            }

        def get_resume_index(self, pipeline_name, case_path=None, case=None):
            return 22

        def restore_context(self, pipeline_name, ctx):
            ctx.state["current_comp_url"] = "BusinessLicenceWay"
            ctx.state["current_status"] = "10"
            return True

    class FakeCheckpointHook:
        def __init__(self, checkpoint, pipeline_name=""):
            self.checkpoint = checkpoint
            self.pipeline_name = pipeline_name

    class FakePipeline:
        def __init__(self, name, steps, hooks):
            assert name == "phase2_establish"

        def run(self, ctx, start_from=0, stop_after=None):
            assert start_from == 22
            return SimpleNamespace(
                success=False,
                exit_reason="done",
                exit_detail=None,
                stopped_at_step=22,
            )

    monkeypatch.setattr(run_smart_register, "Phase2Adapter", FakeAdapter)
    monkeypatch.setattr(run_smart_register, "Checkpoint", FakeCheckpoint)
    monkeypatch.setattr(run_smart_register, "CheckpointHook", FakeCheckpointHook)
    monkeypatch.setattr(run_smart_register, "Pipeline", FakePipeline)

    assert runner.run_phase2() is False


def test_phase2_resume_probes_authoritative_location_before_alignment(monkeypatch, tmp_path: Path):
    runner = _make_runner(tmp_path)
    runner.phase1_busi_id = "BUSI-001"
    runner.phase1_name_id = "NAME-001"
    runner.client = object()
    calls = {"probe": 0}

    class FakeAdapter:
        def __init__(self, case, busi_id, name_id=None):
            self.p2_ctx = SimpleNamespace(name_id=name_id, busi_id="EST-001", ent_type="4540", busi_type="02")

        def make_steps(self, ent_type=None):
            return ["step"] * 25

        def restore_from_pipeline_ctx(self, ctx):
            return None

        def probe_current_location(self, client, ctx):
            calls["probe"] += 1
            ctx.state["server_curr_comp_url"] = "YbbSelect"
            ctx.state["current_comp_url"] = "YbbSelect"
            ctx.state["server_status"] = "10"
            ctx.state["current_status"] = "10"
            return {"server_curr_comp_url": "YbbSelect", "server_status": "10"}

        def recommend_start_from(self, observed_component, fallback_index=0, ent_type=None):
            assert observed_component == "YbbSelect"
            return 22

    class FakeCheckpoint:
        def __init__(self, _path):
            pass

        def load(self, pipeline_name, case_path=None, case=None):
            return {"status": "failed"}

        def get_resume_index(self, pipeline_name, case_path=None, case=None):
            return 23

        def restore_context(self, pipeline_name, ctx):
            ctx.state["current_comp_url"] = "PreElectronicDoc"
            ctx.state["current_status"] = "10"
            return True

    class FakeCheckpointHook:
        def __init__(self, checkpoint, pipeline_name=""):
            self.checkpoint = checkpoint
            self.pipeline_name = pipeline_name

    class FakePipeline:
        def __init__(self, name, steps, hooks):
            assert name == "phase2_establish"

        def run(self, ctx, start_from=0, stop_after=None):
            assert start_from == 22
            return SimpleNamespace(
                success=False,
                exit_reason="done",
                exit_detail=None,
                stopped_at_step=22,
            )

    monkeypatch.setattr(run_smart_register, "Phase2Adapter", FakeAdapter)
    monkeypatch.setattr(run_smart_register, "Checkpoint", FakeCheckpoint)
    monkeypatch.setattr(run_smart_register, "CheckpointHook", FakeCheckpointHook)
    monkeypatch.setattr(run_smart_register, "Pipeline", FakePipeline)

    assert runner.run_phase2() is False
    assert calls["probe"] == 1


def test_write_run_record_refreshes_node_assets(monkeypatch, tmp_path: Path):
    runner = _make_runner(tmp_path)
    runner.final_status = "step_22_p2_step23"
    runner.phase1_busi_id = "BUSI-001"
    runner.phase1_name_id = "NAME-001"
    runner.establish_busi_id = "EST-001"
    runner.last_phase2_state = {"current_comp_url": "YbbSelect", "current_status": "10"}
    runner.last_diagnosis = {"page_name": "云帮办流程模式选择", "category": "step_not_advanced"}
    runner.log = [{"success": False, "code": "STEP_NOT_ADVANCED"}]

    records_dir = tmp_path / "records"
    assets_dir = tmp_path / "assets"
    captured = {}

    class FakeCheckpoint:
        def __init__(self, _path):
            pass

        def load(self, pipeline_name, case_path=None, case=None):
            return {"status": "failed", "context_state": {"phase2_driver_snapshot": {}}}

    def fake_export_latest_node_assets(records_dir, assets_dir):
        captured["records_dir"] = records_dir
        captured["assets_dir"] = assets_dir
        return {"manifest_path": str(Path(assets_dir) / "node_assets_latest.json"), "node_count": 1}

    monkeypatch.setattr(run_smart_register, "Checkpoint", FakeCheckpoint)
    monkeypatch.setattr(run_smart_register, "RECORDS_DIR", records_dir)
    monkeypatch.setattr(run_smart_register, "ASSETS_DIR", assets_dir)
    monkeypatch.setattr(run_smart_register, "export_latest_node_assets", fake_export_latest_node_assets)

    runner._write_run_record()

    assert (records_dir / "smart_register_latest.json").exists()
    assert captured["records_dir"] == records_dir
    assert captured["assets_dir"] == assets_dir
    assert runner.latest_node_assets["node_count"] == 1
