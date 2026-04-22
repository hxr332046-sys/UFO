# guide/base 通用策略引擎设计

## 引擎目标
- 把“点击脚本”升级为“前置条件校验 + 动作执行 + 强断言 + 自动降级”。
- 面向多 `busiType` 复用，默认对每一步做副作用证据校验。

## 模块
- `ContextLoader`：读取当前 URL、hash、`busiType/entType`、VM 能力（是否存在 `flowSave`）。
- `StateProbe`：采集提示文案、按钮可见性、请求计数、hash。
- `ActionPlanner`：按优先级生成动作序列：
  1) 资格提示处理
  2) 名称提示处理
  3) 选择“未申请”
  4) 下一步
  5) VM fallback（`flowSave/fzjgFlowSave`）
- `AssertionGate`：每步后强制校验 `request_count` 或 `hash` 变化。
- `DegradeController`：断言失败后进入降级策略（切换选择器策略、VM 调用策略、重建上下文策略），并记录失败类型。

## 断言规范
- A1: `after.hash != before.hash` 或 `after.probeReqCount > before.probeReqCount`
- A2: 连续 3 次 A1 失败即标记 `blocked_no_side_effect`
- A3: fallback VM 调用后仍失败，标记 `frontend_gate_or_hidden_context_block`

## 当前实现落点
- 脚本：`政务平台/system/guide_base_strategy_engine.py`
- 结果：`政务平台/dashboard/data/records/guide_base_strategy_engine_run.json`

## 扩展点（下一阶段）
- 加入 Storage 快照比对（`localStorage/sessionStorage`）识别隐藏门控字段。
- 加入 Network 域级监听（非 XHR patch）避免页面重写 XHR 导致漏记。
- 把 `busiType` 策略配置外置到 JSON，支持批量回归。

