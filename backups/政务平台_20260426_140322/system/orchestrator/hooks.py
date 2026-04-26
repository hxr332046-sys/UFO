"""
内置 Hook 实现 — 日志 · 限流保护 · 交互纠错 · 状态提取

每个 Hook 只关心一个关注点（Single Responsibility）。
组合使用时按 priority 排序执行。
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .core import (
    Hook,
    InterventionSignal,
    PipelineContext,
    PipelineResult,
    StepResult,
    StepSpec,
)
from .intelligence import build_diagnosis, compact_problem

# ═══════════════════════════════════════════════
# 颜色工具
# ═══════════════════════════════════════════════
_COLORS = {"r": "31", "g": "32", "y": "33", "b": "34", "m": "35", "c": "36", "w": "37"}


def _c(text: str, color: str = "w") -> str:
    code = _COLORS.get(color, "37")
    return f"\033[{code}m{text}\033[0m"


# ═══════════════════════════════════════════════
# 1. LoggingHook — 统一彩色日志
# ═══════════════════════════════════════════════

class LoggingHook(Hook):
    """每步开始/结束时打印彩色日志，Pipeline 开始/结束打印框线。"""
    priority = 10

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def on_pipeline_start(self, ctx: PipelineContext, steps: List[StepSpec]) -> None:
        total = len(steps)
        print()
        print(_c(f"╔═══ Pipeline 启动: {total} 步 ═══╗", "m"))

    def on_step_start(self, index: int, step: StepSpec, ctx: PipelineContext) -> None:
        total = len(ctx._step_results) + (len(ctx._step_results) == 0 and 1 or 1)
        tag = f" [{step.tag}]" if step.tag else ""
        opt = " (optional)" if step.optional else ""
        print(f"\n  [{index + 1}] {step.name}{tag}{opt}")

    def on_step_end(self, index: int, step: StepSpec, result: StepResult,
                    ctx: PipelineContext) -> None:
        if result.ok:
            if result.code == "SKIP":
                print(_c(f"      SKIP  ({result.duration_s:.1f}s)", "y"))
            else:
                rt = result.result_type
                print(_c(f"      ✅ OK  code={result.code} rt={rt}  ({result.duration_s:.1f}s)", "g"))
        elif step.optional:
            print(_c(f"      ⚠ SKIP  code={result.code}  ({result.duration_s:.1f}s)", "y"))
        else:
            print(_c(f"      ❌ FAIL  code={result.code} rt={result.result_type}  ({result.duration_s:.1f}s)", "r"))
            if result.message:
                print(_c(f"         msg: {result.message[:150]}", "r"))

        # extracted 打印
        if result.extracted:
            keep = {k: v for k, v in result.extracted.items()
                    if not k.startswith("_") and k != "nameCheckDTO_captured"}
            if keep:
                print(f"      extracted: {json.dumps(keep, ensure_ascii=False)[:200]}")

        # verbose: raw response preview
        if self.verbose and result.raw_response:
            preview = json.dumps(result.raw_response, ensure_ascii=False)[:300]
            print(f"      raw: {preview}")

    def on_step_error(self, index: int, step: StepSpec, error: Exception,
                      ctx: PipelineContext) -> Optional[StepResult]:
        print(_c(f"      💥 EXCEPTION: {error}", "r"))
        return None

    def on_pipeline_end(self, ctx: PipelineContext, result: PipelineResult) -> None:
        print()
        if result.success:
            print(_c(f"╚═══ Pipeline 完成 ✅  {result.total_time_s}s ═══╝", "g"))
        else:
            reason = result.exit_reason or "unknown"
            print(_c(f"╚═══ Pipeline 停止 ❌  reason={reason}  {result.total_time_s}s ═══╝", "r"))


# ═══════════════════════════════════════════════
# 2. SmartDiagnosisHook — 阶段 / 页面 / 错误 / 建议动作
# ═══════════════════════════════════════════════

class SmartDiagnosisHook(Hook):
    """为每一步生成智能诊断，失败时输出阶段、页面、原因与建议。"""
    priority = 35

    def on_step_end(self, index: int, step: StepSpec, result: StepResult,
                    ctx: PipelineContext) -> None:
        pipeline_name = str(ctx.state.get("pipeline_name") or "")
        diagnosis = build_diagnosis(
            pipeline_name=pipeline_name,
            step_index=index,
            step_name=step.name,
            step_tag=step.tag,
            optional=step.optional,
            result=result,
            ctx_state=ctx.state,
            case=ctx.case,
        )
        result.diagnostics = diagnosis
        ctx.state["last_diagnosis"] = diagnosis
        if not result.ok:
            ctx.state["last_problem"] = compact_problem(diagnosis)
            problems = ctx.state.setdefault("problems", [])
            if isinstance(problems, list):
                problems.append(compact_problem(diagnosis))
            self._print_problem(diagnosis)

    def on_pipeline_end(self, ctx: PipelineContext, result: PipelineResult) -> None:
        diagnosis = ctx.state.get("last_diagnosis")
        if diagnosis:
            result.context_state["last_diagnosis"] = diagnosis
        problem = ctx.state.get("last_problem")
        if problem:
            result.context_state["last_problem"] = problem

    def _print_problem(self, diagnosis: Dict[str, Any]) -> None:
        print(_c("      🧠 智能诊断", "m"))
        print(_c(f"         阶段: {diagnosis.get('business_stage_name')}", "m"))
        print(_c(f"         页面: {diagnosis.get('page_name')}", "m"))
        print(_c(f"         类型: {diagnosis.get('category')} / {diagnosis.get('severity')}", "m"))
        print(_c(f"         含义: {diagnosis.get('meaning')}", "m"))
        print(_c(f"         建议: {diagnosis.get('suggested_action')}", "m"))


# ═══════════════════════════════════════════════
# 3. ThrottleHook — 限流检测 + Session 过期检测
# ═══════════════════════════════════════════════

RATE_LIMIT_CODE = "D0029"
SESSION_GATE_CODE = "GS52010103E0302"


class ThrottleHook(Hook):
    """检测限流和 Session 过期，触发 InterventionSignal 或直接标记退出。"""
    priority = 40

    def on_step_end(self, index: int, step: StepSpec, result: StepResult,
                    ctx: PipelineContext) -> None:
        if result.code == RATE_LIMIT_CODE:
            print(_c("      🛑 服务端限流 (D0029) — 立即停止，请等 5-10 分钟", "r"))
            raise InterventionSignal(
                kind="rate_limit",
                diagnostics={"code": result.code, "message": result.message},
                options=["abort"],
                message="服务端限流，需要冷却",
            )

        if result.code == SESSION_GATE_CODE:
            print(_c("      🔑 Session 过期 — 需要重新登录", "r"))
            raise InterventionSignal(
                kind="session_expired",
                diagnostics={"code": result.code},
                options=["abort"],
                message="Session 过期，请重新扫码",
            )


# ═══════════════════════════════════════════════
# 4. StateExtractorHook — 从响应中提取关键状态
# ═══════════════════════════════════════════════

class StateExtractorHook(Hook):
    """从 StepResult 中提取 busiId / nameId / status 等关键状态到 Context。"""
    priority = 30

    def on_step_end(self, index: int, step: StepSpec, result: StepResult,
                    ctx: PipelineContext) -> None:
        ext = result.extracted or {}
        has_probed_server_comp = isinstance(ext.get("server_curr_comp_url"), str) and bool(str(ext.get("server_curr_comp_url") or "").strip())
        has_probed_server_status = ext.get("server_status") not in (None, "")
        ctx.state["last_step_index"] = index
        ctx.state["last_step_name"] = step.name
        ctx.state["last_step_ok"] = bool(result.ok)
        ctx.state["last_response_code"] = result.code
        ctx.state["last_response_result_type"] = result.result_type
        if result.message:
            ctx.state["last_response_message"] = result.message[:200]

        # busiId 提取
        for key in ("busiId", "busiId_from_second_save", "busiId_from_third_save"):
            bid = ext.get(key)
            if isinstance(bid, str) and bid.strip():
                if "phase1" in step.tag or "name" in step.name.lower():
                    ctx.phase1_busi_id = bid.strip()
                else:
                    ctx.establish_busi_id = bid.strip()

        # nameId
        nid = ext.get("nameId")
        if isinstance(nid, str) and nid.strip():
            ctx.name_id = nid.strip()

        server_comp = ext.get("server_curr_comp_url")
        if isinstance(server_comp, str) and server_comp.strip():
            ctx.state["server_curr_comp_url"] = server_comp.strip()
            ctx.state["current_comp_url"] = server_comp.strip()

        server_status = ext.get("server_status")
        if server_status not in (None, ""):
            ctx.state["server_status"] = server_status
            ctx.state["current_status"] = server_status

        if result.ok:
            ctx.state["last_ok_step_index"] = index
            ctx.state["last_ok_step_name"] = step.name
            ctx.state["last_ok_code"] = result.code
            ctx.state["last_ok_result_type"] = result.result_type

        # flowData 提取（如果 raw_response 可用）
        if result.raw_response and isinstance(result.raw_response, dict):
            data = result.raw_response.get("data") or {}
            bd = data.get("busiData") or {}
            fd = bd.get("flowData") or {}
            if fd.get("busiId") and not ctx.establish_busi_id:
                ctx.establish_busi_id = str(fd["busiId"])
            if fd.get("currCompUrl") and not has_probed_server_comp:
                ctx.state["current_comp_url"] = fd.get("currCompUrl")
            if fd.get("status") and not has_probed_server_status:
                ctx.state["current_status"] = fd.get("status")
            if fd.get("busiType"):
                ctx.state["current_busi_type"] = fd.get("busiType")
            if fd.get("entType"):
                ctx.state["current_ent_type"] = fd.get("entType")
            if fd.get("status") == "90":
                ctx.state["reached_status_90"] = True
            if fd.get("currCompUrl") == "PreSubmitSuccess":
                ctx.state["reached_pre_submit"] = True
            if isinstance(bd, dict):
                bcc = bd.get("busiCompComb") or {}
                if isinstance(bcc, dict):
                    ctx.state["current_busi_comp_comb"] = {
                        "id": bcc.get("id"),
                        "compUrl": bcc.get("compUrl"),
                    }


# ═══════════════════════════════════════════════
# 5. NameCorrectionHook — 核名交互纠错
# ═══════════════════════════════════════════════

class NameCorrectionHook(Hook):
    """当核名步骤返回 resultType=2 且无 busiId 时，触发交互干预。

    展示禁限词详情、近似名列表，提供改名/强制/退出选项。
    """
    priority = 50

    def on_step_end(self, index: int, step: StepSpec, result: StepResult,
                    ctx: PipelineContext) -> None:
        # 只在核名第二次保存(#2)触发；第一次保存(#1) rt=2 是正常流程（近似名确认）
        if "operationBusinessDataInfo" not in step.name:
            return
        if "#1" in step.name:
            return  # 第一次保存 rt=2 = 正常，继续到 nameCheckRepeat
        if result.result_type != "2":
            return
        if result.extracted.get("busiId_from_second_save") or result.extracted.get("busiId_from_third_save"):
            return

        # 构建诊断数据
        diagnostics = {
            "step_name": step.name,
            "result_type": result.result_type,
            "message": result.message,
            "extracted": result.extracted,
        }

        # 尝试从上下文中收集更多诊断信息
        for prev in ctx._step_results:
            if "bannedLexicon" in prev.name:
                diagnostics["banned_tip"] = prev.extracted.get("tipStr", "")
            if "nameCheckRepeat" in prev.name:
                diagnostics["hit_count"] = prev.extracted.get("hit_count", 0)
                diagnostics["checkState"] = prev.extracted.get("checkState_reported", "")

        raise InterventionSignal(
            kind="name_correction",
            diagnostics=diagnostics,
            options=["rename", "force", "abort"],
            message="核名返回 resultType=2，需要用户决定",
        )

    def on_intervention(self, signal: InterventionSignal,
                        ctx: PipelineContext) -> str:
        if signal.kind != "name_correction":
            return "abort"

        self._display_diagnosis(signal.diagnostics, ctx)
        return self._prompt_user(ctx)

    def _display_diagnosis(self, diag: Dict[str, Any], ctx: PipelineContext) -> None:
        """展示完整诊断信息。"""
        print()
        print(_c("╔═══════════════════════════════════════════════╗", "y"))
        print(_c("║           ⚠ 核名需要您的决定 ⚠                ║", "y"))
        print(_c("╚═══════════════════════════════════════════════╝", "y"))

        name = ctx.case.get("phase1_check_name", "?")
        mark = ctx.case.get("name_mark", "?")
        print()
        print(_c(f"  当前名称: {name}", "w"))
        print(_c(f"  字号    : {mark}", "w"))

        banned = diag.get("banned_tip", "")
        if banned:
            print()
            print(_c(f"  ┌─ 禁限用词警告 ──────────────────────┐", "r"))
            print(_c(f"  │ {banned[:100]}", "r"))
            print(_c(f"  └──────────────────────────────────────┘", "r"))

        hit_count = diag.get("hit_count", 0)
        if hit_count:
            print(_c(f"  近似企业数: {hit_count}", "y"))

        print()
        print(_c(f"  resultType=2, message: {diag.get('message', '')[:100]}", "y"))

    def _prompt_user(self, ctx: PipelineContext) -> str:
        """交互提示。"""
        print()
        print(_c("  ═══ 请选择操作 ═══", "m"))
        print(_c("  [1] 更换字号（输入新字号，重头核名）", "g"))
        print(_c("  [2] 强制继续（continueFlag）", "y"))
        print(_c("  [3] 退出", "r"))
        print()

        while True:
            try:
                choice = input(_c("  选项 (1/2/3): ", "m")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return "abort"

            if choice == "1":
                new_mark = input(_c("  新字号: ", "g")).strip()
                if len(new_mark) < 2:
                    print(_c("  字号至少2字", "r"))
                    continue
                self._update_name(ctx, new_mark)
                return "restart_pipeline"
            elif choice == "2":
                confirm = input(_c("  确认强制继续? (y/N): ", "y")).strip().lower()
                if confirm in ("y", "yes"):
                    return "skip"
                continue
            elif choice == "3":
                return "abort"

    def _update_name(self, ctx: PipelineContext, new_mark: str) -> None:
        """更新 case 名称（内存+磁盘）。"""
        name_pre = ctx.case.get("phase1_name_pre", "广西容县")
        organize = ctx.case.get("phase1_organize", "中心（个人独资）")
        ind_special = ctx.case.get("phase1_industry_special", "软件开发")
        new_full = f"{new_mark}（{name_pre}）{ind_special}{organize}"

        print(_c(f"  名称更新: {ctx.case.get('name_mark')} → {new_mark}", "g"))
        print(_c(f"  全称: {new_full}", "g"))

        ctx.case["name_mark"] = new_mark
        ctx.case["phase1_check_name"] = new_full
        ctx.case["company_name_full"] = new_full

        try:
            ctx.case_path.write_text(
                json.dumps(ctx.case, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            print(_c(f"  ⚠ 文件写入失败: {e}", "y"))


# ═══════════════════════════════════════════════
# 6. ResultWriterHook — 结果 JSON 持久化
# ═══════════════════════════════════════════════

class ResultWriterHook(Hook):
    """Pipeline 结束后将结果写入 JSON 文件。"""
    priority = 90

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def on_pipeline_end(self, ctx: PipelineContext, result: PipelineResult) -> None:
        out = {
            "schema": "orchestrator.v1",
            "pipeline": result.pipeline_name,
            "success": result.success,
            "exit_reason": result.exit_reason,
            "exit_detail": result.exit_detail,
            "stopped_at_step": result.stopped_at_step,
            "total_steps": result.total_steps,
            "total_time_s": result.total_time_s,
            "context_state": result.context_state,
            "steps": result.steps,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{result.pipeline_name}_latest.json"
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  📄 结果已保存: {path}")


# ═══════════════════════════════════════════════
# 预置 Hook 组合
# ═══════════════════════════════════════════════

def default_hooks(verbose: bool = False, output_dir: Optional[Path] = None) -> List[Hook]:
    """返回推荐的 Hook 组合。"""
    hooks: List[Hook] = [
        LoggingHook(verbose=verbose),
        SmartDiagnosisHook(),
        ThrottleHook(),
        StateExtractorHook(),
    ]
    if output_dir:
        hooks.append(ResultWriterHook(output_dir))
    return hooks


def full_hooks(verbose: bool = False, output_dir: Optional[Path] = None) -> List[Hook]:
    """包含核名纠错的完整 Hook 组合。"""
    hooks = default_hooks(verbose=verbose, output_dir=output_dir)
    hooks.append(NameCorrectionHook())
    return hooks
