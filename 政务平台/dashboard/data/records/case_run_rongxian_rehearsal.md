# 设立流程演练（至云提交停点）

- **开始**: 2026-04-20 19:23:23
- **结束**: 2026-04-20 19:24:34
- **门户入口**: namenotice
- **resume_current**: False
- **llm_observations**: 0 条 (ufo.llm_observation.v1)
- **run_id**: `8e34cfe8-50be-49a0-95aa-2d862b398117`
- **task.state**: partial

## 问题 / 阻塞

- 验收项未通过 AC-GUIDE-BASE: 出现过 guide/base（中间里程碑）
- 验收项未通过 AC-CORE-REACHED: 曾进入 core.html（设立主流程/材料等）
- 验收项未通过 AC-YUN-SUBMIT: 本轮未在页面文案中检测到「云提交/云端提交」停点（可能卡在名称引导/材料页之前）

## 提示

- 【第一阶段·新设】拟设主体：完成名称自主申报/核名；办件是否已出现在「我的办件」取决于进度，**未出现不代表核名逻辑已失败**。
- 【第二阶段】进入 core 后完成各步表单与材料上传，直至页面出现「云提交」类文案（本自动化不点提交）。

## 建议

- 第一阶段专用模式已结束：请在浏览器完成核名与材料下载；第二阶段再运行 run_case_rongxian_to_yun_submit.py（不带 --phase1-only，常用 --resume-current）

## 阶段结论（phase_verdict）

- **第一阶段** `status=unknown`: 第一阶段：名称登记/核名可接续（列表是否已有该行取决于进度；可选列表门禁见 case_company_listing_gate）
- **第二阶段** `status=skipped`: 第二阶段：长表单推进至云提交文案停点（不点云提交）（reached_core=False reached_yun=False）

## 验收项摘要

- **OK** `AC-CDP`: 已连接 CDP 且存在 9087 页签
- **OK** `AC-LOGIN`: 顶栏像已登录（办件中心且无 登录/注册 访客条）
- **OK** `AC-CLICK-ESTABLISH`: activefuc 或 DOM 命中「设立登记」
- **OK** `AC-REACH-FLOW`: 技术里程碑：曾出现 enterprise-zone / name-register / guide/base / 云提交停点之一（不等于业务上两阶段已验收）
- **FAIL** `AC-GUIDE-BASE`: 出现过 guide/base（中间里程碑）
- **FAIL** `AC-CORE-REACHED`: 曾进入 core.html（设立主流程/材料等）
- **FAIL** `AC-YUN-SUBMIT`: 本轮未在页面文案中检测到「云提交/云端提交」停点（可能卡在名称引导/材料页之前）
- **OK** `AC-NO-EARLY-AUTH`: 云提交停点前未出现实人/短信类门控（若失败请复核是否环境变更）
- **OK** `AC-BLOCKER-EVIDENCE`: 若有 blocker_evidence 记录，则每条须含 png_path 或 last_api 中非空 hook/perf 摘要