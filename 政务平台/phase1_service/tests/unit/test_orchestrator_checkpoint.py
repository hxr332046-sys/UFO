from __future__ import annotations

import json
from pathlib import Path

from orchestrator.adapters import Phase2Adapter
from orchestrator.checkpoint import Checkpoint
from orchestrator.core import PipelineContext, StepResult


def _make_ctx(tmp_path: Path, case_name: str, case_id: str = "case-1") -> PipelineContext:
    case_path = tmp_path / f"{case_name}.json"
    case_path.write_text("{}", encoding="utf-8")
    ctx = PipelineContext(
        case={
            "case_id": case_id,
            "phase1_check_name": case_name,
            "company_name_full": case_name,
            "entType_default": "1151",
            "person": {
                "name": "黄永裕",
                "mobile": "18977514335",
                "id_no": "450921198812051251",
            },
        },
        case_path=case_path,
        client=None,
    )
    return ctx


def test_checkpoint_is_case_aware(tmp_path: Path):
    cp = Checkpoint(tmp_path)
    ctx_a = _make_ctx(tmp_path, "A公司", "case-a")
    ctx_b = _make_ctx(tmp_path, "B公司", "case-b")

    ctx_a.state["phase1_busi_id"] = "A-001"
    ctx_a._step_results.append(StepResult(name="step-a", ok=True, code="00000"))
    cp.save("phase2_establish", 3, ctx_a, status="running", resume_index=4)

    ctx_b.state["phase1_busi_id"] = "B-001"
    ctx_b._step_results.append(StepResult(name="step-b", ok=True, code="00000"))
    cp.save("phase2_establish", 7, ctx_b, status="failed", resume_index=7)

    loaded_a = cp.load("phase2_establish", case_path=ctx_a.case_path, case=ctx_a.case)
    loaded_b = cp.load("phase2_establish", case_path=ctx_b.case_path, case=ctx_b.case)

    assert loaded_a is not None
    assert loaded_b is not None
    assert loaded_a["case_id"] == "case-a"
    assert loaded_b["case_id"] == "case-b"
    assert loaded_a["context_state"]["phase1_busi_id"] == "A-001"
    assert loaded_b["context_state"]["phase1_busi_id"] == "B-001"
    assert cp.path_for("phase2_establish", case_path=ctx_a.case_path, case=ctx_a.case) != cp.path_for(
        "phase2_establish", case_path=ctx_b.case_path, case=ctx_b.case
    )


def test_checkpoint_resume_index_ignores_completed(tmp_path: Path):
    cp = Checkpoint(tmp_path)
    ctx = _make_ctx(tmp_path, "完成公司")
    ctx._step_results.append(StepResult(name="done", ok=True, code="00000"))

    cp.save("phase2_establish", 9, ctx, status="completed", resume_index=0)

    assert cp.get_resume_index("phase2_establish", case_path=ctx.case_path, case=ctx.case) == 0


def test_phase2_adapter_restore_from_pipeline_ctx(minimal_case: dict, tmp_path: Path):
    case = dict(minimal_case)
    case["entType_default"] = "1151"
    case["case_id"] = "restore-case"
    case_path = tmp_path / "restore-case.json"
    case_path.write_text("{}", encoding="utf-8")

    ctx = PipelineContext(case=case, case_path=case_path, client=None)
    ctx.phase1_busi_id = "P1-001"
    ctx.establish_busi_id = "EST-009"
    ctx.name_id = "NAME-007"
    ctx.state["phase2_driver_name_id"] = "NAME-007"
    ctx.state["phase2_driver_busi_id"] = "EST-009"
    ctx.state["phase2_driver_ent_type"] = "1151"
    ctx.state["phase2_driver_busi_type"] = "02_4"
    ctx.state["phase2_driver_snapshot"] = {
        "establish_busiId": "EST-009",
        "last_sign_info": "-2013029225",
        "last_save_flowData": {"currCompUrl": "ComplementInfo"},
    }

    adapter = Phase2Adapter(case, "P1-001", "NAME-001")
    adapter.restore_from_pipeline_ctx(ctx)

    assert adapter.p2_ctx.busi_id == "EST-009"
    assert adapter.p2_ctx.name_id == "NAME-007"
    assert adapter.p2_ctx.ent_type == "1151"
    assert adapter.p2_ctx.busi_type == "02_4"
    assert adapter.p2_ctx.snapshot["establish_busiId"] == "EST-009"
    assert adapter.p2_ctx.snapshot["last_sign_info"] == "-2013029225"


def test_checkpoint_restore_drops_transient_runtime_state(tmp_path: Path):
    cp = Checkpoint(tmp_path)
    ctx_save = _make_ctx(tmp_path, "运行态公司", "runtime-case")
    ctx_save.state.update({
        "phase1_busi_id": "BUSI-001",
        "step_execution_counts": {"22:[23] foo": 2},
        "last_attempted_step_index": 22,
        "last_attempted_step_name": "[23] foo",
        "last_attempted_step_count": 2,
        "current_comp_url": "YbbSelect",
    })
    ctx_save._step_results.append(StepResult(name="foo", ok=False, code="STEP_EXECUTION_GUARD"))
    cp.save("phase2_establish", 22, ctx_save, status="failed", resume_index=22)

    ctx_restore = _make_ctx(tmp_path, "运行态公司", "runtime-case")

    assert cp.restore_context("phase2_establish", ctx_restore) is True
    assert ctx_restore.state["phase1_busi_id"] == "BUSI-001"
    assert ctx_restore.state["current_comp_url"] == "YbbSelect"
    assert "step_execution_counts" not in ctx_restore.state
    assert "last_attempted_step_index" not in ctx_restore.state
    assert "last_attempted_step_name" not in ctx_restore.state
    assert "last_attempted_step_count" not in ctx_restore.state


def test_case_aware_checkpoint_load_ignores_legacy_fallback(tmp_path: Path):
    cp = Checkpoint(tmp_path)
    ctx = _make_ctx(tmp_path, "兴裕为", "xingyuwei-case")

    legacy_payload = {
        "schema": "orchestrator.checkpoint.v2",
        "pipeline": "phase2_establish",
        "status": "failed",
        "case_path": str(ctx.case_path),
        "case_id": ctx.case["case_id"],
        "context_state": {"phase1_busi_id": "LEGACY-001"},
        "resume_index": 22,
    }
    (tmp_path / "checkpoint_phase2_establish.json").write_text(
        json.dumps(legacy_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    loaded = cp.load("phase2_establish", case_path=ctx.case_path, case=ctx.case)

    assert loaded is None
