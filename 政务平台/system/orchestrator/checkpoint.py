"""
断点持久化 — 每步成功后存档，下次可从断点恢复

存储格式:
{
    "pipeline": "phase1_name_check",
    "completed_step": 5,
    "resume_index": 6,
    "context_state": { "busi_id": "xxx", "name_id": "yyy", ... },
    "last_step": { ... },
    "failure": { ... },
    "timestamp": "2026-04-24 21:30:00"
}
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .core import Hook, PipelineContext, PipelineResult, StepResult, StepSpec


_TRANSIENT_RUNTIME_STATE_KEYS = frozenset({
    "pipeline_name",
    "step_execution_counts",
    "last_attempted_step_index",
    "last_attempted_step_name",
    "last_attempted_step_count",
})


class Checkpoint:
    """断点数据的读写。"""

    def __init__(self, checkpoint_dir: Path):
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _legacy_path(self, pipeline_name: str) -> Path:
        return self.checkpoint_dir / f"checkpoint_{pipeline_name}.json"

    def _case_key(self, *, case_path: Optional[Path] = None,
                  case: Optional[Dict[str, Any]] = None) -> str:
        case_id = ""
        if isinstance(case, dict):
            case_id = str(case.get("case_id") or "").strip()

        raw_path = str(case_path.resolve()) if case_path else ""
        base = "||".join([raw_path, case_id]).strip("|") or raw_path or case_id or "default"
        digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:10]
        stem = case_path.stem if case_path else (case_id or "case")
        safe_stem = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in stem) or "case"
        return f"{safe_stem}_{digest}"

    def _path(self, pipeline_name: str, *, case_path: Optional[Path] = None,
              case: Optional[Dict[str, Any]] = None) -> Path:
        if case_path is None and case is None:
            return self._legacy_path(pipeline_name)
        case_key = self._case_key(case_path=case_path, case=case)
        return self.checkpoint_dir / f"checkpoint_{pipeline_name}__{case_key}.json"

    def path_for(self, pipeline_name: str, *, case_path: Optional[Path] = None,
                 case: Optional[Dict[str, Any]] = None) -> Path:
        return self._path(pipeline_name, case_path=case_path, case=case)

    def _build_payload(self, pipeline_name: str, step_index: int,
                       ctx: PipelineContext, *, status: str,
                       resume_index: Optional[int] = None,
                       failure: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        case = ctx.case if isinstance(ctx.case, dict) else {}
        last_result = ctx._step_results[-1] if ctx._step_results else None
        case_key = self._case_key(case_path=ctx.case_path, case=case)
        default_resume = 0 if status == "completed" else max(step_index + 1, 0)

        return {
            "schema": "orchestrator.checkpoint.v2",
            "pipeline": pipeline_name,
            "status": status,
            "case_key": case_key,
            "case_path": str(ctx.case_path),
            "case_id": case.get("case_id"),
            "case_name": case.get("phase1_check_name") or case.get("company_name_full"),
            "ent_type": case.get("entType_default"),
            "completed_step": step_index,
            "resume_index": default_resume if resume_index is None else max(int(resume_index), 0),
            "context_state": dict(ctx.state),
            "last_step": last_result.to_dict() if last_result else None,
            "failure": failure,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def save(self, pipeline_name: str, step_index: int,
             ctx: PipelineContext, *, status: str = "running",
             resume_index: Optional[int] = None,
             failure: Optional[Dict[str, Any]] = None) -> Path:
        """保存断点。"""
        data = self._build_payload(
            pipeline_name,
            step_index,
            ctx,
            status=status,
            resume_index=resume_index,
            failure=failure,
        )
        path = self._path(pipeline_name, case_path=ctx.case_path, case=ctx.case)
        text = json.dumps(data, ensure_ascii=False, indent=2)
        path.write_text(text, encoding="utf-8")
        self._legacy_path(pipeline_name).write_text(text, encoding="utf-8")
        return path

    def load(self, pipeline_name: str, *, case_path: Optional[Path] = None,
             case: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """加载断点。如果不存在返回 None。"""
        paths = []
        if case_path is not None or case is not None:
            paths.append(self._path(pipeline_name, case_path=case_path, case=case))
        else:
            paths.append(self._legacy_path(pipeline_name))

        for path in paths:
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            return data
        return None

    def clear(self, pipeline_name: str, *, case_path: Optional[Path] = None,
              case: Optional[Dict[str, Any]] = None) -> None:
        """清除断点。"""
        paths = [self._legacy_path(pipeline_name)]
        if case_path is not None or case is not None:
            paths.insert(0, self._path(pipeline_name, case_path=case_path, case=case))
        for path in paths:
            if path.exists():
                path.unlink()

    def get_resume_index(self, pipeline_name: str, *, case_path: Optional[Path] = None,
                         case: Optional[Dict[str, Any]] = None) -> int:
        """返回应该从哪一步恢复（completed_step + 1）。没有断点返回 0。"""
        cp = self.load(pipeline_name, case_path=case_path, case=case)
        if cp is None:
            return 0
        if cp.get("status") == "completed":
            return 0
        if cp.get("resume_index") is not None:
            return int(cp.get("resume_index") or 0)
        return cp.get("completed_step", -1) + 1

    def restore_context(self, pipeline_name: str, ctx: PipelineContext) -> bool:
        """将断点中的 state 恢复到 context。返回是否成功。"""
        cp = self.load(pipeline_name, case_path=ctx.case_path, case=ctx.case)
        if cp is None:
            return False
        saved_state = dict(cp.get("context_state", {}) or {})
        for key in _TRANSIENT_RUNTIME_STATE_KEYS:
            saved_state.pop(key, None)
        ctx.state.update(saved_state)
        return True


class CheckpointHook(Hook):
    """每步成功后自动保存断点。Pipeline 成功完成后清除断点。"""
    priority = 80

    def __init__(self, checkpoint: Checkpoint, pipeline_name: str = ""):
        self.checkpoint = checkpoint
        self.pipeline_name = pipeline_name

    def on_pipeline_start(self, ctx: PipelineContext, steps: List[StepSpec]) -> None:
        # 如果有断点，提示用户
        cp = self.checkpoint.load(self.pipeline_name, case_path=ctx.case_path, case=ctx.case)
        if cp:
            step_idx = cp.get("resume_index", 0)
            ts = cp.get("timestamp", "?")
            status = cp.get("status", "running")
            print(f"  💾 发现状态: {status} next={int(step_idx) + 1 if step_idx else 1} @ {ts}")

    def on_checkpoint(self, index: int, step: StepSpec, ctx: PipelineContext) -> None:
        if not step.optional or ctx._step_results[-1].ok:
            self.checkpoint.save(
                self.pipeline_name,
                index,
                ctx,
                status="running",
                resume_index=index + 1,
            )

    def on_pipeline_end(self, ctx: PipelineContext, result: PipelineResult) -> None:
        if result.success:
            self.checkpoint.save(
                self.pipeline_name,
                int(ctx.state.get("last_ok_step_index", result.stopped_at_step)),
                ctx,
                status="completed",
                resume_index=0,
            )
            print("  💾 已保存完成状态")
        else:
            failed_result = ctx._step_results[-1] if ctx._step_results else None
            failure = {
                "exit_reason": result.exit_reason,
                "exit_detail": result.exit_detail,
                "failed_step_index": result.stopped_at_step,
                "failed_step_name": failed_result.name if failed_result else None,
                "failed_step_code": failed_result.code if failed_result else None,
                "failed_step_result_type": failed_result.result_type if failed_result else None,
                "failed_step_message": failed_result.message if failed_result else None,
                "diagnosis": (failed_result.diagnostics if failed_result else None) or ctx.state.get("last_diagnosis"),
            }
            self.checkpoint.save(
                self.pipeline_name,
                int(ctx.state.get("last_ok_step_index", -1)),
                ctx,
                status="failed",
                resume_index=max(result.stopped_at_step, 0),
                failure=failure,
            )
            print("  💾 已保存失败现场，可继续续跑")
