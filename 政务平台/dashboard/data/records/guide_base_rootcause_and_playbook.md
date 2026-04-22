# guide/base 根因报告与修复手册

## 根因结论
- 根因一（前端）：`guide/base` 处于“文案可见、对话容器不可见”的异常态，点击动作未进入业务 VM 状态机。
- 根因二（前后端契约）：即便强制调用 `flowSave/fzjgFlowSave`，在隐藏上下文未满足时也不会产生命中后端的副作用。
- 根因三（跨类型一致性）：`02_4` 与 `07` 行为一致，说明问题属于通用门控层，不是单一企业类型参数问题。

## 证据链
- `guide_base_state_machine_trace.json`
- `guide_base_strategy_engine_run.json`
- `guide_base_constraint_graph.json`
- `guide_base_backend_contract.json`

## 修复手册（框架执行）
1. 进入 `guide/base` 后先执行 `StateProbe`，不要直接点“下一步”。
2. 若提示文案存在但 `dialogCount=0`，标记 `ghost_dialog_state`，禁止继续普通点击流。
3. 执行动作后必须触发断言：
   - `hash` 变化，或
   - `/icpsp-api/` 请求计数增加。
4. 若断言失败，进入降级：
   - 切换选择器策略（容器级 -> 文案级 -> VM 级）。
   - 尝试 VM fallback 调用。
   - 若仍失败，立即停机并归档。
5. 归档内容必须包含：动作序列、断言结果、最后页面状态、请求计数、busiType。

## 建议的长期修复方向
- 在策略引擎中增加 Storage/Router hook 快照，识别隐藏门控字段变化。
- 将“动作成功”定义从“点击成功”升级为“业务副作用成功”。
- 建立 nightly 回归：至少覆盖 `02_4`、`07` 两类样本。

