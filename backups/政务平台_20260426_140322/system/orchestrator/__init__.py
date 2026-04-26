"""
流程编排器框架 — 统一步骤协议 · Hook 插件 · 断点续跑

用法:
    from orchestrator import Pipeline, StepSpec, PipelineContext, Hook, StepResult
    from orchestrator.hooks import LoggingHook, ThrottleHook, CheckpointHook
"""

from .core import (
    StepResult,
    StepSpec,
    PipelineContext,
    PipelineResult,
    Hook,
    InterventionSignal,
    Pipeline,
)
from .checkpoint import Checkpoint

__all__ = [
    "StepResult",
    "StepSpec",
    "PipelineContext",
    "PipelineResult",
    "Hook",
    "InterventionSignal",
    "Pipeline",
    "Checkpoint",
]
