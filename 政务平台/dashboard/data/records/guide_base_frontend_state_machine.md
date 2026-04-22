# guide/base 前端状态机逆向（02_4）

## 观测结论
- 页面存在两个同名 `index` 组件，真正业务组件是“带 `flowSave` 的 index”。
- `guide/base` 上可见“未申请/下一步/确定/关 闭”按钮，但点击链路未触发业务组件方法。
- 直接调用业务组件 `flowSave/fzjgFlowSave` 可执行，但仍无路由推进和网络副作用。

## 关键证据
- `guide_base_state_machine_trace.json`
  - `inject_trace.wrapped` 成功包裹 `flowSave/fzjgFlowSave/checkchange` 等方法。
  - `simulate_clicks.trace` 为空，说明 UI 点击没有流入这些方法。
  - `manual_call.trace` 出现 `flowSave/fzjgFlowSave`，说明方法可达但结果被更深层门控拦截。
- `guide_base_strategy_engine_run.json`
  - `hasNamePrompt=true`、`hasQualificationPrompt=true` 且 `probeReqCount` 恒为 0。
  - 断言 `request_or_hash_changed` 连续失败。

## 逆向状态机（简化）
1. 进入 `guide/base`，展示资格提示 + 名称提示文本。
2. UI 允许点击按钮，但事件命中的是展示层或无效节点（非业务 VM 入口）。
3. 业务 VM 方法手动调用可执行，但未满足隐藏前置门控（非可见 UI 条件）。
4. 最终停留在 `guide/base`，出现“动作假成功”（可点击，无副作用）。

## 根因定位（前端侧）
- 不是“按钮不可点”问题，而是“点击路径未绑定到有效业务状态机入口”。
- 页面存在“文案可见但对话容器不可见（dialogCount=0）”的异常态，导致基于容器的处理器失效。
- 该异常态与 `busiType` 无关（`02_4` 与 `07` 同样复现）。

