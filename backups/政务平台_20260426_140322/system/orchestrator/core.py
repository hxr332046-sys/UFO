"""
Pipeline 核心引擎 — 步骤执行 · Hook 分发 · 干预信号

设计原则:
  1. 确定性优先 — 步骤序列已知时直接执行，不引入 LLM 延迟
  2. Hook 可插拔 — 日志、限流、交互纠错、检查点全部是 Hook
  3. 干预信号 — 任何 Hook 可以抛 InterventionSignal 暂停流水线
  4. 上下文透传 — PipelineContext 跨步骤共享状态
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# ════════════════════════════════════════════════
# 数据类
# ════════════════════════════════════════════════

@dataclass
class StepResult:
    """一步执行的标准化结果。所有 Phase/驱动器必须返回此类型。"""
    name: str
    ok: bool
    code: str                                 # API 返回码 (00000 / A0002 / SKIP / ERROR)
    result_type: str = ""                     # resultType (0/1/2/-1)
    message: str = ""                         # 服务端消息或错误描述
    extracted: Dict[str, Any] = field(default_factory=dict)   # 从响应中提取的关键字段
    diagnostics: Dict[str, Any] = field(default_factory=dict) # 供 Hook 展示的诊断数据
    duration_s: float = 0.0
    raw_response: Optional[Dict[str, Any]] = None  # 完整响应（verbose 模式用）
    sent_body_keys: List[str] = field(default_factory=list)

    @property
    def is_warning(self) -> bool:
        """rt=2 的警告（如名称近似），步骤函数内部已处理。
        ★ rt=1（参数校验失败）现在由 adapter 直接标记 ok=False，不再算 warning。
        """
        return self.ok and self.result_type == "2"

    @property
    def is_fatal(self) -> bool:
        return self.result_type == "-1"

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "name": self.name,
            "ok": self.ok,
            "code": self.code,
            "resultType": self.result_type,
            "message": self.message[:200],
            "extracted": self.extracted,
            "duration_s": round(self.duration_s, 2),
            "sent_body_keys": self.sent_body_keys,
        }
        if self.diagnostics:
            data["diagnostics"] = self.diagnostics
        return data


@dataclass
class StepSpec:
    """步骤规格 — 描述一步该怎么执行。

    fn 签名: (client, context_state) -> StepResult
    或者:     (client, context_state) -> Tuple[StepResult, Optional[Dict]]
    """
    name: str
    fn: Callable[..., Any]
    optional: bool = False
    tag: str = ""                # 分组标签 (guide / query / core / save)
    component: str = ""          # 组件名（如 YbbSelect / PreElectronicDoc）
    expected_progress: Dict[str, Any] = field(default_factory=dict)  # 执行后期望达到的服务端状态
    requires_feedback: bool = True
    delay_after_s: float = 1.0   # 步间延时
    retry_on_codes: List[str] = field(default_factory=list)  # 可重试的错误码
    max_retries: int = 0
    max_executions: int = 2


@dataclass
class PipelineContext:
    """跨步骤共享的可变上下文。

    state 是一个自由字典，任何步骤/Hook 都可以读写。
    约定的 well-known keys 通过 property 暴露。
    """
    case: Dict[str, Any]
    case_path: Path
    client: Any                    # ICPSPClient 实例
    verbose: bool = False
    state: Dict[str, Any] = field(default_factory=dict)
    # 内部追踪
    _step_results: List[StepResult] = field(default_factory=list, repr=False)

    # ── well-known state properties ──
    @property
    def busi_id(self) -> Optional[str]:
        return self.state.get("busi_id")

    @busi_id.setter
    def busi_id(self, v: str):
        self.state["busi_id"] = v

    @property
    def name_id(self) -> Optional[str]:
        return self.state.get("name_id")

    @name_id.setter
    def name_id(self, v: str):
        self.state["name_id"] = v

    @property
    def phase1_busi_id(self) -> Optional[str]:
        return self.state.get("phase1_busi_id")

    @phase1_busi_id.setter
    def phase1_busi_id(self, v: str):
        self.state["phase1_busi_id"] = v

    @property
    def establish_busi_id(self) -> Optional[str]:
        return self.state.get("establish_busi_id")

    @establish_busi_id.setter
    def establish_busi_id(self, v: str):
        self.state["establish_busi_id"] = v

    def reload_case(self):
        """从磁盘重新加载 case 文件（改名后使用）。"""
        import json
        self.case = json.loads(self.case_path.read_text(encoding="utf-8"))


@dataclass
class PipelineResult:
    """Pipeline 执行的最终结果。"""
    pipeline_name: str
    success: bool
    exit_reason: Optional[str] = None
    exit_detail: Optional[str] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)
    context_state: Dict[str, Any] = field(default_factory=dict)
    total_time_s: float = 0.0
    stopped_at_step: int = 0
    total_steps: int = 0


# ════════════════════════════════════════════════
# 干预信号
# ════════════════════════════════════════════════

class InterventionSignal(Exception):
    """Hook 抛出此异常以暂停 Pipeline，请求人工干预。

    Pipeline 捕获后调用 on_intervention 回调链，
    根据返回的 action 决定 retry / skip / abort。
    """

    def __init__(self, kind: str, diagnostics: Dict[str, Any],
                 options: Optional[List[str]] = None, message: str = ""):
        self.kind = kind                 # "name_correction" / "confirm" / "manual"
        self.diagnostics = diagnostics
        self.options = options or ["retry", "skip", "abort"]
        self.message = message
        super().__init__(message or f"InterventionSignal({kind})")


# ════════════════════════════════════════════════
# Hook 基类
# ════════════════════════════════════════════════

class Hook:
    """可插拔的生命周期钩子。子类按需重写。

    所有方法默认为空操作（no-op），子类只需重写关心的方法。
    """
    priority: int = 100  # 数值越小越先执行

    def on_pipeline_start(self, ctx: PipelineContext, steps: List[StepSpec]) -> None:
        """Pipeline 开始前。"""

    def on_step_start(self, index: int, step: StepSpec, ctx: PipelineContext) -> None:
        """步骤开始前。"""

    def on_step_end(self, index: int, step: StepSpec, result: StepResult,
                    ctx: PipelineContext) -> None:
        """步骤成功完成后（ok=True 或 optional 跳过）。"""

    def on_step_error(self, index: int, step: StepSpec, error: Exception,
                      ctx: PipelineContext) -> Optional[StepResult]:
        """步骤抛异常时。返回 StepResult 可替代异常，返回 None 继续向上抛。"""

    def on_intervention(self, signal: InterventionSignal,
                        ctx: PipelineContext) -> str:
        """收到干预信号时。返回 action: 'retry' / 'skip' / 'abort' / 'rename:新字号'。"""
        return "abort"

    def on_pipeline_end(self, ctx: PipelineContext, result: PipelineResult) -> None:
        """Pipeline 结束后（无论成功失败）。"""

    def on_checkpoint(self, index: int, step: StepSpec, ctx: PipelineContext) -> None:
        """每步成功后触发，用于持久化断点。"""


def _result_has_feedback(result: StepResult) -> bool:
    if result.code == "SKIP":
        return True
    if isinstance(result.raw_response, dict) and bool(result.raw_response):
        return True
    if isinstance(result.extracted, dict) and bool(result.extracted):
        return True
    if str(result.result_type or "").strip():
        return True
    if str(result.message or "").strip():
        return True
    code = str(result.code or "").strip()
    return bool(code and code not in ("", "00000", "UNKNOWN_FORMAT"))


# ════════════════════════════════════════════════
# Pipeline 引擎
# ════════════════════════════════════════════════

class Pipeline:
    """核心流水线引擎。

    用法:
        pipe = Pipeline("phase1_name_check", steps=[...], hooks=[...])
        result = pipe.run(ctx)
        # 或断点恢复:
        result = pipe.run(ctx, start_from=5)
    """

    def __init__(self, name: str, steps: List[StepSpec], hooks: Optional[List[Hook]] = None):
        self.name = name
        self.steps = steps
        self.hooks = sorted(hooks or [], key=lambda h: h.priority)

    def run(self, ctx: PipelineContext, *,
            start_from: int = 0,
            stop_after: Optional[int] = None) -> PipelineResult:
        """执行流水线。

        Args:
            ctx: 共享上下文
            start_from: 从第几步开始（0-indexed），用于断点恢复
            stop_after: 执行到第几步后停止（1-indexed），None=全部执行
        """
        t_start = time.time()
        exit_reason: Optional[str] = None
        exit_detail: Optional[str] = None
        steps_out: List[Dict[str, Any]] = []
        last_index = start_from

        effective_end = len(self.steps) if stop_after is None else min(stop_after, len(self.steps))
        ctx.state["pipeline_name"] = self.name

        # ── pipeline start hooks ──
        for h in self.hooks:
            try:
                h.on_pipeline_start(ctx, self.steps)
            except Exception:
                pass

        for idx in range(start_from, effective_end):
            spec = self.steps[idx]
            last_index = idx

            # ── step start hooks ──
            for h in self.hooks:
                try:
                    h.on_step_start(idx, spec, ctx)
                except Exception:
                    pass

            result = self._execute_step(idx, spec, ctx)

            if result is None:
                # 异常未被 Hook 处理
                exit_reason = f"step_{idx}_unhandled_exception"
                break

            steps_out.append(result.to_dict())
            ctx._step_results.append(result)

            # ── step end hooks ──
            for h in self.hooks:
                try:
                    h.on_step_end(idx, spec, result, ctx)
                except InterventionSignal as sig:
                    # Hook 请求干预（如核名纠错）
                    action = self._handle_intervention(sig, ctx)
                    if action == "abort":
                        exit_reason = "user_abort"
                        exit_detail = sig.message
                        break
                    elif action == "retry":
                        # 重跑当前步骤
                        result2 = self._execute_step(idx, spec, ctx)
                        if result2 and result2.ok:
                            result = result2
                            steps_out[-1] = result2.to_dict()
                            ctx._step_results[-1] = result2
                        else:
                            if result2:
                                result = result2
                                steps_out[-1] = result2.to_dict()
                                ctx._step_results[-1] = result2
                            exit_reason = f"step_{idx}_retry_failed"
                            break
                    elif action.startswith("restart_pipeline"):
                        # 需要从头重跑（改名后）
                        exit_reason = "__restart__"
                        exit_detail = action
                        break
                    elif action == "skip":
                        pass  # 继续下一步
                except Exception:
                    pass

            steps_out[-1] = result.to_dict()

            if exit_reason:
                break

            # ── 判断是否应该停止 ──
            if not result.ok and not spec.optional:
                exit_reason = f"step_{idx}_{spec.tag or 'failed'}"
                exit_detail = f"{spec.name}: {result.code} {result.message[:200]}"
                break

            if result.is_fatal:
                exit_reason = f"step_{idx}_fatal"
                exit_detail = result.message
                break

            # ── checkpoint hooks ──
            for h in self.hooks:
                try:
                    h.on_checkpoint(idx, spec, ctx)
                except Exception:
                    pass

            # ── 步间延时 ──
            if idx < effective_end - 1 and spec.delay_after_s > 0:
                time.sleep(spec.delay_after_s)

        # ── pipeline end ──
        total_time = time.time() - t_start
        last_result = ctx._step_results[-1] if ctx._step_results else None
        success = (
            exit_reason is None
            and last_result is not None
            and last_result.ok
        )

        pipe_result = PipelineResult(
            pipeline_name=self.name,
            success=success,
            exit_reason=exit_reason,
            exit_detail=exit_detail,
            steps=steps_out,
            context_state=dict(ctx.state),
            total_time_s=round(total_time, 1),
            stopped_at_step=last_index,
            total_steps=len(self.steps),
        )

        for h in self.hooks:
            try:
                h.on_pipeline_end(ctx, pipe_result)
            except Exception:
                pass

        return pipe_result

    def _execute_step(self, idx: int, spec: StepSpec,
                      ctx: PipelineContext) -> Optional[StepResult]:
        """执行单步，处理异常和重试。"""
        attempts = 1 + spec.max_retries
        execution_counts = ctx.state.setdefault("step_execution_counts", {})
        step_key = f"{idx}:{spec.name}"

        for attempt in range(attempts):
            execution_count = int(execution_counts.get(step_key, 0)) + 1
            execution_counts[step_key] = execution_count
            ctx.state["last_attempted_step_index"] = idx
            ctx.state["last_attempted_step_name"] = spec.name
            ctx.state["last_attempted_step_count"] = execution_count
            if spec.max_executions > 0 and execution_count > spec.max_executions:
                return StepResult(
                    name=spec.name,
                    ok=False,
                    code="STEP_EXECUTION_GUARD",
                    message=f"{spec.name} 在单次运行中已执行 {execution_count} 次，超过上限 {spec.max_executions}，为避免死循环和高频攻击已拦截。",
                    extracted={
                        "attempted_count": execution_count,
                        "max_executions": spec.max_executions,
                    },
                )
            t0 = time.time()
            try:
                raw = spec.fn(ctx.client, ctx)
                dt = time.time() - t0

                # 适配不同返回格式
                result = self._normalize_result(raw, spec.name, dt)
                if spec.requires_feedback and not _result_has_feedback(result):
                    ext = dict(result.extracted or {})
                    ext["upstream_code"] = result.code
                    ext["upstream_result_type"] = result.result_type
                    return StepResult(
                        name=spec.name,
                        ok=False,
                        code="STEP_NO_FEEDBACK",
                        result_type=result.result_type,
                        message=f"{spec.name} 没有返回足够的结构化反馈，编排器不会在无感知状态下继续推进。",
                        extracted=ext,
                        duration_s=dt,
                        raw_response=result.raw_response,
                    )
                return result

            except InterventionSignal:
                raise  # 上层处理

            except Exception as e:
                dt = time.time() - t0
                # 给 Hook 机会处理
                for h in self.hooks:
                    try:
                        recovery = h.on_step_error(idx, spec, e, ctx)
                        if recovery is not None:
                            return recovery
                    except Exception:
                        pass

                # 最后一次尝试仍失败
                if attempt == attempts - 1:
                    if spec.optional:
                        return StepResult(
                            name=spec.name,
                            ok=False,
                            code="ERROR",
                            message=str(e)[:200],
                            duration_s=dt,
                        )
                    else:
                        return StepResult(
                            name=spec.name,
                            ok=False,
                            code="EXCEPTION",
                            message=str(e)[:200],
                            diagnostics={"traceback": traceback.format_exc()[-500:]},
                            duration_s=dt,
                        )

                # 重试前等待
                time.sleep(1.0)

        return None

    def _normalize_result(self, raw: Any, name: str, dt: float) -> StepResult:
        """将不同驱动器的返回值归一化为 StepResult。"""
        # 已经是 StepResult
        if isinstance(raw, StepResult):
            if raw.duration_s == 0:
                raw.duration_s = dt
            return raw

        # Phase 1 驱动器返回 (StepResult_like, response_dict) 元组
        if isinstance(raw, tuple) and len(raw) == 2:
            sr, resp = raw
            if hasattr(sr, "ok") and hasattr(sr, "code"):
                result = StepResult(
                    name=getattr(sr, "name", name),
                    ok=sr.ok,
                    code=sr.code,
                    result_type=getattr(sr, "result_type", ""),
                    message=getattr(sr, "reason", ""),
                    extracted=getattr(sr, "extracted", {}),
                    duration_s=dt,
                    raw_response=resp,
                    sent_body_keys=getattr(sr, "sent_body_keys", []),
                )
                return result

        # Phase 2 驱动器返回 dict (响应体)
        if isinstance(raw, dict):
            code = str(raw.get("code", ""))
            rt = str(raw.get("data", {}).get("resultType", "") if isinstance(raw.get("data"), dict) else "")
            msg = str(raw.get("message", ""))
            return StepResult(
                name=name,
                ok=(code == "00000"),
                code=code,
                result_type=rt,
                message=msg,
                duration_s=dt,
                raw_response=raw,
            )

        # 未知格式 — 尝试当成功
        return StepResult(
            name=name,
            ok=True,
            code="UNKNOWN_FORMAT",
            message=f"Unrecognized return type: {type(raw).__name__}",
            duration_s=dt,
        )

    def _handle_intervention(self, signal: InterventionSignal,
                             ctx: PipelineContext) -> str:
        """将干预信号广播给所有 Hook，返回最终 action。"""
        action = "abort"
        for h in self.hooks:
            try:
                a = h.on_intervention(signal, ctx)
                if a and a != "abort":
                    action = a
                    break
            except Exception:
                pass
        return action
