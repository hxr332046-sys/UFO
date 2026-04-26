# 设立流程演练（至云提交停点）

- **开始**: 2026-04-23 22:15:51
- **结束**: 2026-04-23 22:17:37
- **门户入口**: namenotice
- **resume_current**: False
- **llm_observations**: 6 条 (ufo.llm_observation.v1)
- **run_id**: `90d22abb-e740-409a-abc8-eb61d2dbc569`
- **task.state**: partial

## 问题 / 阻塞

- 【阶段结论】第二阶段未达云提交文案停点：见 phase_verdict.phase2_to_yun_submit_stop 与 acceptance 中 AC-YUN-SUBMIT
- 验收项未通过 AC-GUIDE-BASE: 出现过 guide/base（中间里程碑）
- 验收项未通过 AC-CORE-REACHED: 曾进入 core.html（设立主流程/材料等）
- 验收项未通过 AC-YUN-SUBMIT: 本轮未在页面文案中检测到「云提交/云端提交」停点（可能卡在名称引导/材料页之前）
- 验收项未通过 AC-BLOCKER-EVIDENCE: 若有 blocker_evidence 记录，则每条须含 png_path 或 last_api 中非空 hook/perf 摘要

## 提示

- 【第一阶段·新设】拟设主体：完成名称自主申报/核名；办件是否已出现在「我的办件」取决于进度，**未出现不代表核名逻辑已失败**。
- 【第二阶段】进入 core 后完成各步表单与材料上传，直至页面出现「云提交」类文案（本自动化不点提交）。
- 未检测到「云提交」文案：可看 blocker_evidence 截图与最后数步 snap

## 建议

- 全程未出现可见 input[type=file]（多在 core 材料步骤）；若卡在 name-register/guide/base，需先人工关闭「请选择是否需要名称」等弹窗并完成级联住所，再继续跑或改从已进 core 的页签启动
- 本轮已生成 6 条 llm_observation.v1（供后续 LLM 规划/RAG）；见 rec.llm_observations

## 阶段结论（phase_verdict）

- **第一阶段** `status=unknown`: 第一阶段：名称登记/核名可接续（列表是否已有该行取决于进度；可选列表门禁见 case_company_listing_gate）
- **第二阶段** `status=fail`: 第二阶段：长表单推进至云提交文案停点（不点云提交）（reached_core=False reached_yun=False）

## 验收项摘要

- **OK** `AC-CDP`: 已连接 CDP 且存在 9087 页签
- **OK** `AC-LOGIN`: 顶栏像已登录（办件中心且无 登录/注册 访客条）
- **OK** `AC-CLICK-ESTABLISH`: activefuc 或 DOM 命中「设立登记」
- **OK** `AC-REACH-FLOW`: 技术里程碑：曾出现 enterprise-zone / name-register / guide/base / 云提交停点之一（不等于业务上两阶段已验收）
- **FAIL** `AC-GUIDE-BASE`: 出现过 guide/base（中间里程碑）
- **FAIL** `AC-CORE-REACHED`: 曾进入 core.html（设立主流程/材料等）
- **FAIL** `AC-YUN-SUBMIT`: 本轮未在页面文案中检测到「云提交/云端提交」停点（可能卡在名称引导/材料页之前）
- **OK** `AC-NO-EARLY-AUTH`: 云提交停点前未出现实人/短信类门控（若失败请复核是否环境变更）
- **FAIL** `AC-BLOCKER-EVIDENCE`: 若有 blocker_evidence 记录，则每条须含 png_path 或 last_api 中非空 hook/perf 摘要