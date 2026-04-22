# 阶段性总结：guide/base 打穿至 name-check-info（2026-04-15）

## 阶段目标

- 在用户重新登录后，恢复 `02_4 / 个体独资企业` 链路推进能力。
- 打穿 `guide/base` 阻断，继续向“云帮办流程模式选择”推进。
- 对新增阻断点进行可复现、可证据化记录。

## 本阶段已完成成果

- 已确认并复现 `guide/base` 关键卡点根因：`flowSave` 内部触发 `addressChild.getFormData` 时对象缺失。
- 已通过分支规避（`havaAdress='0'`）成功绕过该异常，产生真实请求并从 `name-register` 成功跳转到 `core`。
- 当前链路已稳定落到 `core.html#/flow/base/name-check-info`，不再回退到早期 `guide/base` 阻断态。
- 已完成 name-check 页面组件逆向基础盘点：
  - 业务容器组件：`name-check-info`
  - 子业务组件：`index`（包含 `flowSave/getFormPromise/nameCheckRepeat`）
  - 关键控件组件：`tni-industry-select`、`organization-select`
- 已识别当前主阻断为 name-check 页面必填门控，不再是 guide/base。

## 关键发现（新增）

### 1) guide/base 根因与突破

- 证据显示 `guide/base` 点击“下一步”路径在旧分支会触发 `getFormData` 空对象异常。
- 当切换到不走该分支后，出现真实网络请求并进入 `core#/flow/base/name-check-info`。

### 2) name-check-info 新阻断

- 当前稳定必填错误为：
  - `请选择行业/经营特点`
  - `请选择组织形式`
- 即使直接注入 `formInfo.industry / industryName / organize`，页面仍判定未完成。
- 说明这两个字段存在更深层组件态/提交态约束，不能仅靠外层 `formInfo` 值通过。

### 3) 组件行为异常信号

- `organization-select.radioChange` 触发过程中出现 `_value` 相关异常迹象。
- 直接调用 `index.flowSave` 出现 `Cannot read properties of undefined (reading 'success')`，且无后续网络请求，显示当前调用上下文仍不完整。

## 产出证据清单（本阶段）

- `final_breakthrough_push_next.json`：guide/base 绕过 `getFormData` 分支后进入 core 的关键证据。
- `continue_core_to_yunbangban.json`：从 core 续跑至目标前的循环推进记录（当前卡在 name-check）。
- `fill_namecheck_industry_org.json`：行业/组织形式定点填充与组件调用尝试记录。
- `push_namecheck_flowsave.json`：直接调用 name-check `flowSave` 的异常与无请求证据。
- `dump_namecheck_index_fields.json`：name-check `index` 关键数据结构与字段快照。
- `inspect_namecheck_vm.json`：name-check 页面组件树与关键组件识别结果。
- `inspect_namecheck_children.py`（脚本产出见终端）：行业/组织形式子组件方法与数据键枚举结果。

## 当前状态结论

- 链路状态：**已突破 guide/base，当前阻断在 name-check-info 必填门控**。
- 达成程度：阶段性突破成功（恢复到 core），但尚未到“云帮办流程模式选择”停点。

## 下一阶段建议动作

- 对 `tni-industry-select` 与 `organization-select` 做提交前钩子追踪（含输入、选中、校验、回填时序），锁定“已选择”判定变量。
- 在 `index.getFormPromise` 之前插桩采集组件内部最终 payload，建立“页面展示值 vs 提交值”映射。
- 完成两字段真值同步后，恢复自动推进，目标到“云帮办流程模式选择”即停并固化证据。

