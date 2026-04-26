"""
编排器使用示例 — 展示如何用 Pipeline 组装 Phase 1 核名流程

这个文件不是产品代码，是框架使用文档。
"""

from __future__ import annotations


def example_phase1_pipeline():
    """示例: 用框架组装 Phase 1 核名流水线。

    对比原来在 phase1_protocol_driver.py 里的硬编码步骤列表,
    框架版本把步骤定义、执行引擎、日志、限流保护、核名纠错全部解耦。

    Usage:
        from orchestrator import Pipeline, StepSpec, PipelineContext
        from orchestrator.hooks import full_hooks
        from orchestrator.checkpoint import Checkpoint, CheckpointHook

        # 1. 定义步骤（从现有驱动器导入函数）
        steps = [
            StepSpec(name="checkEstablishName",     fn=step_check_establish_name, optional=True,  tag="guide", delay_after_s=0.9),
            StepSpec(name="loadCurrentLocationInfo", fn=step_load_current_location, optional=True, tag="guide", delay_after_s=0.9),
            StepSpec(name="loadBusinessDataInfo",    fn=step_namecheck_load,       optional=True,  tag="guide", delay_after_s=0.9),
            StepSpec(name="bannedLexiconCalibration",fn=step_banned_lexicon,       optional=True,  tag="query", delay_after_s=0.9),
            StepSpec(name="operationBusinessDataInfo#first",  fn=step_nc_op_first_save,  optional=False, tag="core", delay_after_s=1.5),
            StepSpec(name="nameCheckRepeat",         fn=step_namecheck_repeat,     optional=False, tag="query", delay_after_s=0.9),
            StepSpec(name="operationBusinessDataInfo#second", fn=step_nc_op_second_save, optional=False, tag="core", delay_after_s=1.5),
            StepSpec(name="operationBusinessDataInfo#confirm",fn=step_nc_op_third_save,  optional=True,  tag="core", delay_after_s=0.9),
        ]

        # 2. 组装 Hook（可插拔）
        hooks = full_hooks(verbose=True, output_dir=Path("dashboard/data/records"))
        # 加入断点
        cp = Checkpoint(Path("dashboard/data/checkpoints"))
        hooks.append(CheckpointHook(cp, pipeline_name="phase1"))

        # 3. 创建 Pipeline
        pipe = Pipeline("phase1_name_check", steps=steps, hooks=hooks)

        # 4. 创建 Context
        ctx = PipelineContext(
            case=case_dict,
            case_path=Path("docs/case_xxx.json"),
            client=icpsp_client,
            verbose=True,
        )

        # 5. 执行（支持断点恢复）
        start = cp.get_resume_index("phase1")
        if start > 0:
            cp.restore_context("phase1", ctx)
            print(f"从断点 step={start} 恢复")
        result = pipe.run(ctx, start_from=start)

        # 6. 检查结果
        if result.success:
            print(f"核名成功! busiId={ctx.phase1_busi_id}")
        elif result.exit_reason == "__restart__":
            # 用户改名了，需要重跑 — 编排器外层循环处理
            pass
        else:
            print(f"失败: {result.exit_reason}")
    """
    pass


def example_full_register():
    """示例: Phase 1 + Phase 2 端到端流水线。

    编排器的核心价值: 把两个 Phase 的步骤拼成一个大流水线，
    统一的 Hook 系统处理所有横切关注点。

    Usage:
        # Phase 1 步骤
        phase1_steps = [...]  # 8 步

        # Phase 2 步骤
        phase2_steps = [...]  # 25 步

        # 合并成一条流水线
        all_steps = phase1_steps + phase2_steps

        pipe = Pipeline("full_register_4540", steps=all_steps, hooks=hooks)
        result = pipe.run(ctx)

        # 或者分成两个 Pipeline，由外层编排
        p1 = Pipeline("phase1", steps=phase1_steps, hooks=hooks)
        p2 = Pipeline("phase2", steps=phase2_steps, hooks=hooks)

        r1 = p1.run(ctx)
        if r1.success:
            r2 = p2.run(ctx)
    """
    pass


def example_custom_hook():
    """示例: 自定义 Hook — 钉钉/微信通知。

    Usage:
        class DingTalkHook(Hook):
            priority = 95

            def __init__(self, webhook_url: str):
                self.url = webhook_url

            def on_pipeline_end(self, ctx, result):
                name = ctx.case.get("phase1_check_name", "未知")
                if result.success:
                    msg = f"✅ {name} 注册到达云提交停点"
                else:
                    msg = f"❌ {name} 注册失败: {result.exit_reason}"
                requests.post(self.url, json={"msgtype": "text", "text": {"content": msg}})

        hooks = full_hooks() + [DingTalkHook("https://oapi.dingtalk.com/robot/send?...")]
        pipe = Pipeline("register", steps=steps, hooks=hooks)
    """
    pass


# ═══════════════════════════════════════════════
# 架构对比
# ═══════════════════════════════════════════════

ARCHITECTURE_COMPARISON = """
╔═══════════════════════════════════════════════════════════════════╗
║                    架构对比: 旧 vs 新                             ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  旧架构 (run_smart_register.py v1):                               ║
║  ┌──────────────────────┐                                         ║
║  │  Phase 1 黑盒调用     │ → exit_code → 判断                     ║
║  │  (phase1_run)         │                                        ║
║  └──────────────────────┘                                         ║
║  ┌──────────────────────┐                                         ║
║  │  Phase 2 内联循环     │ → 步骤+日志+错误处理 全部混在一起        ║
║  │  (for spec in steps)  │                                        ║
║  └──────────────────────┘                                         ║
║  问题: 日志/限流/纠错/断点 全部硬编码在主循环里                    ║
║                                                                   ║
║  ─────────────────────────────────────────────                    ║
║                                                                   ║
║  新架构 (orchestrator 框架):                                       ║
║  ┌─────────────────────────────────────────┐                      ║
║  │           Pipeline 引擎                  │                      ║
║  │  步骤执行 → Hook 分发 → 干预信号处理     │                      ║
║  └──────────────┬──────────────────────────┘                      ║
║                 │                                                  ║
║    ┌────────────┼────────────┐                                    ║
║    ▼            ▼            ▼                                    ║
║  ┌─────┐   ┌─────────┐  ┌──────────┐                             ║
║  │Steps│   │  Hooks   │  │Checkpoint│                             ║
║  │(可配│   │(可插拔)  │  │(可恢复)  │                             ║
║  │ 置) │   │          │  │          │                             ║
║  └─────┘   └─────────┘  └──────────┘                             ║
║                │                                                  ║
║    ┌───────────┼───────────────┐                                  ║
║    ▼           ▼               ▼                                  ║
║  Logging   Throttle    NameCorrection                             ║
║  Result    StateExtract  [自定义...]                               ║
║                                                                   ║
║  优势: 关注点分离 · 可测试 · 可扩展 · 断点续跑                    ║
╚═══════════════════════════════════════════════════════════════════╝
"""
