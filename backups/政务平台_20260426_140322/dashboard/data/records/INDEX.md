# Dashboard Records Index

统一归档目录：`政务平台/dashboard/data/records`

## 设立登记迭代（开发/验收）

- `packet_chain_shots/`：`packet_chain_portal_from_start.py` 在卡点（无按钮 streak、异常、长程 heartbeat、到达云提交停点）自动 **PNG 截图**；与主 JSON 中 `blocker_evidence[].png_path` 对应。
- `establish_iterate_latest.json`：`python system/establish_iterate_dev.py` 最近一次完整输出（含 `framework` 方法论元数据、`acceptance` 中 **AC-YUN-SUBMIT**、**AC-BLOCKER-EVIDENCE**、**AC-NO-EARLY-AUTH**；每步 `l3_step_code` 与 L2 hook 抓包）。**S08（guide/base）** 使用 `GUIDE_BASE_AUTOFILL_V2`（名称类 MessageBox 优先、未办理预保留优先于未申请）+ **级联双通道**；卡点时 `blocker_evidence[].last_api` 含 **`hook_tail` / `perf_resource_tail`**（L2 尾部与 L1 Performance 摘要，hook 空时会短重装再读）。入口默认 `fromPage=/guide/base`（全部服务截图同款）。
- `packet_chain_portal_from_start.json`：`packet_chain_portal_from_start.py` 默认输出（与上互为补充时可对照）。
- `重大突破_抓包逆向与可复用重放模块纪要_2026-04-18.md`：本次关键突破纪要（mitm 抓包方案、登录态迁移、重放模块化、UI 实验室、验收与复现步骤）。
- `survey_namecheck_dictionaries_latest.json`：名称核查字典普查索引（区划/主体类型/组织形式/行业等），对应 `dict_cache/*_latest.json`。
- `dict_v2.sqlite`：逆开发框架 V2 字典数据库（SQLite，含字典项/协议规范/操作方法）。
- `dict_v2_build_latest.json`：V2 字典库构建结果与统计（条目数、分类分布）。

## 02_4 链路

- `operation_framework_02_4.md`：页面操作框架（人工可读）
- `operation_framework_02_4.json`：页面操作框架（结构化）
- `framework_execution_record_02_4.json`：逐步执行留痕（动作与页面状态）
- `full_submit_test_02_4.json`：全提交流程主记录（会话级）
- `full_submit_test_02_4.md`：全提交流程摘要与结论
- `fix_member_info_and_next_02_4.json`：成员信息补齐尝试记录
- `select_member_roles_and_next_02_4.json`：成员角色选择与推进记录
- `remove_extra_member_and_next_02_4.json`：成员清理与重试记录
- `force_memberpost_flowsave_02_4.json`：强制调用 flowSave 结果
- `force_memberpost_flowsave_with_cb_02_4.json`：带回调 flowSave 返回体证据
- `force_memberpost_next_with_itemid_02_4.json`：注入 itemId 强制推进记录
- `submit_memberpost_via_flowcontrol_02_4.json`：通过 flow-control 提交尝试记录
- `click_save_next_after_member_fix_02_4.json`：按钮恢复后保存重试记录
- `retry_member_save_with_resp_capture_02_4.json`：保存请求与 A0002 回包抓包证据
- `full_submit_test_02_4_round2.json`：round2 全链路重测主记录
- `full_submit_test_02_4_round2.md`：round2 测试结论摘要
- `round2_submit_success_evidence.json`：round2 提交成功页证据快照
- `full_submit_test_02_4_round3_to_yunbangban.json`：round3 到云帮办节点主记录（含阻断状态）
- `full_submit_test_02_4_round3_to_yunbangban.md`：round3 摘要
- `round3_error_fix_log.json`：round3 错误修复与复测日志
- `round3_yunbangban_stop_evidence.json`：round3 停止页证据（当前为 guide/base 阻断现场）
- `round3_cdp_screenshots_index.json`：round3 CDP 截图证据索引（对应 `round3_cdp_shots/`）
- `round3_force_guide_flowsave.json`：round3 组件方法强制触发记录（flowSave/fzjgFlowSave）
- `guide_popup_targeted_close.json`：round3 弹窗容器定向关闭与后续动作记录
- `guide_base_strategy_engine_run.json`：guide/base 通用策略引擎运行记录（含 02_4/07）
- `guide_base_state_machine_trace.json`：guide/base 业务组件方法调用链追踪
- `guide_base_constraint_graph.json`：guide/base 前置条件约束图谱
- `guide_base_backend_contract.json`：guide/base 后端触发契约逆向结果
- `guide_base_generic_engine_design.md`：guide/base 通用策略引擎设计说明
- `guide_base_cross_busitype_verify.json`：guide/base 跨 busiType 迁移验证结果
- `guide_base_frontend_state_machine.md`：guide/base 前端状态机逆向说明
- `guide_base_rootcause_and_playbook.md`：guide/base 根因与修复手册
- `guide_base_frontend_full_reverse.json`：guide/base 前端全逆向追踪（事件传播+VM调用+storage快照）
- `guide_base_backend_contract_full.md`：guide/base->core 后端契约全量逆向说明
- `guide_base_breakthrough_runner.json`：guide/base 打穿脚本多轮回放结果（含 02_4/07）
- `guide_base_full_reverse_final_report.md`：全逆向并行攻坚最终报告
- `phase_summary_guide_to_namecheck_2026-04-15.md`：阶段性总结（guide/base 打穿到 name-check-info，含新阻断与下一步计划）
- `final_breakthrough_push_next.json`：guide/base 绕过 `getFormData` 分支后进入 core 的关键抓包证据
- `continue_core_to_yunbangban.json`：从 core 续跑到云帮办的阶段推进记录（当前停在 name-check）
- `fill_namecheck_industry_org.json`：name-check 行业/组织形式定点填充尝试记录
- `push_namecheck_flowsave.json`：name-check 直接 flowSave 调用异常与无请求证据
- `dump_namecheck_index_fields.json`：name-check `index` 组件字段快照（flowData/formInfo/nameCheckDTO）
- `inspect_namecheck_vm.json`：name-check 页面组件树与关键组件识别记录
- `phase_summary_namecheck_to_backend_limit_2026-04-15.md`：阶段总结（name-check 前端门控清零后转为后端限流阻断）
- `fix_org_by_label_and_input.json`：组织形式以“代码+名称”联动修正并清空前端错误的证据
- `set_namecheck_checkbox_and_next.json`：`isCheckBox/declarationMode` 置位与提交流程证据
- `accept_notice_and_next_namecheck.json`：须知提示处理与保存重试记录
- `hook_namecheck_org_chain.json`：组织形式链路钩子追踪（`radioChange/getFormPromise/flowSave`）
- `inspect_organization_select_runtime.json`：`organization-select` 运行时数据结构与样本
- `breakthrough_cdp_packet_playbook_2026-04-15.md`：突破技术沉淀（CDP+数据包主链路、点击辅助、阻断码判定打法）
- `namecheck_breakthrough_sop_5s_manual_2026-04-15.md`：5秒节奏单步SOP（人工可控、异常即停、零死循环）
- `context_table_driven_playbook.md`：上下文保持与表格驱动手册（状态表/字段表/错误码表/动作表）

## 归档规则

- 所有新增执行记录、调查记录、回归记录，统一复制到本目录
- 同名文件按日期或任务后缀区分，避免覆盖历史证据
