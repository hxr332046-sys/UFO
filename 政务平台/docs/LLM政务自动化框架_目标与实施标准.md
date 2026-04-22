# LLM 为核心的政务自动化提交框架 — 目标与实施标准

> **版本**：2026-04-19c  
> **地位**：本仓库后续自动化、逆开发、演练与产品化工作的**共同标准与动力源**。  
> **维护**：每次重大架构调整或阶段验收后，应更新「当前阶段」「普查结论」两节，并保留变更日期。  
> **总序（与产品路线对齐）**：**先**把样本与选项维度的普查做全、**真实跑**并落盘问题；**再**整合 LLM 规划壳。不以「LLM 能演示」替代普查闭环。  
> **方法论（思维顺序）**：上下文先行、框架撑骨、数据后填——见 **[逆向复现方法论_上下文先行与数据填充.md](./逆向复现方法论_上下文先行与数据填充.md)**。

---

## 1. 终极目标（我们要建成什么）

建设一套以 **大语言模型（LLM）为决策中枢**、以 **可观测、可约束、可审计** 的工程壳为支撑的**政务登记类业务自动化框架**，在合法合规前提下尽可能替代重复人工，实现：

- **自动识别**当前所处流程阶段、待办字段、需上传材料类型及与主体/事项的对应关系。  
- **自动判断**材料与填写内容在「系统规则 + 我方知识库」层面是否**疑似合规**，并区分：确定不合规 / 疑似不合规需人审 / 已通过机审。  
- **自动收集**运行中的错误、阻塞、接口返回、界面提示，并结构化输出**建议、推荐下一步、复盘条目**（成功与失败均记录）。  
- **推进进程**：在策略与安全栅栏内自动点击、填表、上传、导航；在不确定或高风险点**暂停**。  
- **随时回退、随时修改、随时上传**：基于显式状态与事件日志支持撤销上一步、重填、补传，而非仅「从头重跑」。  
- **随时听取命令、随时询问下一步**：自然语言或指令式任务队列 + 人机协同（HITL），默认在**云提交、实人、支付、签章**等闸门前交还人类。

**边界声明**：「完全替代人工」不作为硬性 KPI；以**可量化的无人值守比例**与**明确的人类闸门**为目标。法律后果、材料真实性、政策解释等责任边界须在产品与流程中写清，LLM 输出**不得**作为唯一法律依据。

---

## 2. 设计原则（不可妥协）

| 原则 | 含义 |
|------|------|
| **人在回路（HITL）** | 云提交、身份强核验、对外产生法律效力的动作，默认需人工确认，除非取得书面授权与合规评审。 |
| **确定性执行** | 点击、上传、写库等副作用由**白名单工具**执行；LLM 只产出**结构化计划**，经校验后再调用工具。 |
| **可审计** | 每一步：观测快照、动作、参数摘要、接口关键字段、截图路径、模型版本与提示词版本可追溯。 |
| **最小权限** | 运行时凭证不落库、不进 git；CDP 与 API 密钥分域管理。 |
| **可失败** | 任何一步允许失败并分类；失败必须带来**证据**与**下一步建议**，而非静默卡死。 |
| **类人节奏（防风控）** | 操作间隔须与真人同量级（乘子、抖动、关键页多等），**禁止**毫秒级连点、无等待叠请求；默认启用 `config/human_pacing.json`，调试可用 `--human-fast` 但不得用于对生产站点压测。 |
| **顺序与节拍（固化）** | **业务动作**须符合页面主流程的先后逻辑（先观测再动作、先关弹窗再下一步、与 `l3_step_code` 一致的大方向）；**每一次** CDP 侧「可感知操作」（导航、点击、表单 eval、**每个 file 槽位上传**）之后，间隔 **≥ 1 秒**（由 `sleep_human` + `min_delay_sec` 保证，默认 **1.0**）。**例外**：纯轮询（如 `wait_href`）、WebSocket 重连退避可用 **短 `time.sleep`**，以免拖死。 |

### 2.1 动作顺序与节拍（工程固化说明）

1. **顺序**：自动化须遵循门户 → 专区/名称子应用 → `guide/base`（若出现）→ `core` → 云提交**文案停点**的主路径；在同一页内为先读 `YUN_SUBMIT_PROBE` / `READ_BLOCKER_UI` 再执行「关弹窗 / 级联 / 主按钮」，与 `packet_chain_portal_from_start` 中 `steps` 顺序一致；不得在无观测时连点。  
2. **节拍**：所有上述动作之间的等待统一走 **`system/human_pacing.sleep_human`**；`config/human_pacing.json` 中 **`min_delay_sec` 不得低于 1.0**（代码会强制抬升）。  
3. **上传**：`DOM.setFileInputFiles` **每注入一个槽位后**再 `sleep_human(1.0)`，避免多槽连发。  
4. **实现入口**：`configure_human_pacing(ROOT/"config/human_pacing.json")` 在脚本 `run()` 起始调用；新脚本禁止跳过。  

---

## 3. 目标技术架构（分层）

```
[ 人机接口层 ]  自然语言 / 面板 / API — 命令、澄清、审批
       ↓
[ 规划层 ]      LLM：理解观测、分解任务、生成结构化计划与解释
       ↓
[ 策略与安全 ] 规则引擎 + 风险评分 + 闸门（禁止自动提交等）
       ↓
[ 执行层 ]      CDP / 官方 API / 文件系统 — 确定性动作
       ↓
[ 观测层 ]      DOM、无障碍树、Network、hook、截图、业务 JSON
       ↓
[ 持久化 ]      状态机状态、事件日志、证据包、材料版本
```

**合规子系统**（横切）：规则库、证照与文档解析（OCR/版式）、与 **`icpsp-api` 返回码** 对齐的判定；LLM 仅辅助归纳，**机审结论**须可追溯到规则或接口原文。

---

## 4. 实施路线图（阶段标准）

### 4.0 普查优先、LLM 殿后（不可颠倒的顺序）

| 顺序 | 内容 | 完成含义 |
|------|------|----------|
| **A** | **全矩阵普查**：在下列 **§6.3 维度** 上，按「单元格」推进，每格至少 **一次真实登录态跑通或明确失败原因**（见 **§6.4 运行记录**）。 | 每一格有 **证据**（JSON/截图/接口摘要）+ **问题列表**；未知项从「猜」变为「记过」。 |
| **B** | **问题入库**：将 A 中现象并入 §6.2 / §7、replay 断言、字典 V2、脚本分支；**不**指望 LLM 现场发明规则。 | 同类问题第二次出现可 **分类**、可 **回归**。 |
| **C** | **工具与验收线**：`packet_chain`、验收线 L1、普查脚本、重放实验室 —— 全部为 **B** 服务。 | 自动化是 **记录与复现** 的放大器，不是捷径。 |
| **D** | **LLM 整合（阶段 2）**：仅在 **A 对目标业务范围签收敛**（或明确「未覆盖范围」书面接受）后，把 Observation / digest / 工具链接进规划循环。 | LLM 只做 **已观测空间内** 的规划与归纳，**不**替代普查。 |

**你方「不急、但要所有细节都普查、真实跑、记下来」**：即上表 **A+B**；工程上已提供 **`ufo.census_run_record.v1`** 示例（`dashboard/data/records/census_run_record.v1.example.json`），每次真实跑复制一份改名填写 **`observed_issues[]`**，与脚本产出 JSON **并列保存**。

### 阶段 0 — 观测与取证基线（当前主力）

- CDP 稳定连接、登录态同步、关键路由与 **`l3_step_code`** 粗对齐。  
- **四层取证**（mitm 可选 + Network/Performance + 页内 hook + 步骤 JSON）与 **`blocker_evidence`**、**`acceptance`（AC-*）**。  
- 演练停点：**云提交等文案出现即停**，脚本不自动点击云提交。

**阶段完成判据**：任意一次失败可在 10 分钟内从 JSON + 截图定位到「页面阶段 + 最近 API + UI 报错」。  
**增量（2026-04-19b）**：`packet_chain_portal_from_start` 每轮写入 **`llm_observations[]`**（`schema=ufo.llm_observation.v1`），与 `steps` 并行，供后续规划层直接消费；S08 级联前增加 **`CASCADE_OPEN_MULTI_JS`**；`GUIDE_BASE_AUTOFILL_V2` 增补 MessageBox「我知道了」与大弹窗底部「我已知晓/确认」等。

### 阶段 1 — 状态机与可逆操作日志

- 显式 **状态 / 事件 / 证据** 模型；支持从中间态恢复、分支与受控回退。  
- 与现有 `packet_chain_portal_from_start.py` 等脚本对齐：输出统一进入「任务一次运行」的 schema，而非仅散落 JSON。

**阶段完成判据**：同一办件可「重放事件到第 N 步」或「从状态 S 继续执行」而不必强制从门户首页重开。

### 阶段 2 — LLM 规划壳（受限工具调用）

- **门禁**：阶段 0–1 与 **§6.3 普查矩阵** 对约定业务范围（至少：目标 `busiType`×`entType`×入口路径）已 **有运行记录与问题归档**，或已书面列出「刻意不覆盖」项。  
- 定义 **Observation → Plan → Validate → Act** 循环；工具集固定（导航、填表、上传、读接口摘要、问人）。  
- 每步 **程序断言**（URL/hash、关键元素、接口 code）验证成功后再进入下一步。

**阶段完成判据**：在固定场景（如单一 busiType + 固定材料包）下，由 LLM 驱动完成从入口到云提交停点的比例 ≥ 约定阈值，且零越权动作；且失败案例均可映射回 **已普查** 的阻塞类型而非「模型幻觉」。

### 阶段 3 — 合规与材料智能 + 产品化指挥台

- 材料包版本、字段级合规规则、与政务侧校验反馈闭环。  
- 指挥台：任务队列、实时日志、人工闸门、一键暂停/继续。

**阶段完成判据**：合规结论可解释、可导出审计报告；生产环境配置与密钥管理通过安全评审。

---

## 5. 与当前仓库的对应关系（已有资产）

| 能力 | 现状载体（示例） |
|------|------------------|
| 浏览器与 CDP | `config/browser.json`、`scripts/launch_browser.py` |
| 登录态 | `packet_lab/sync_runtime_auth_from_browser_cdp.py`、`packet_lab/out/runtime_auth_headers.json` |
| 主流程演练与 AC | `system/packet_chain_portal_from_start.py`、`演练设立至云提交_含附件.cmd` |
| 附件 CDP 注入 | `system/cdp_attachment_upload.py`、`config/rehearsal_assets.json` |
| 名称子应用 / guide 逆向纪要 | `dashboard/data/records/*playbook*.md`、`guide_base_*` |
| 协议与重放 | `packet_lab/`、`system/replay_*` |
| 演练摘要 | `dashboard/data/records/framework_rehearsal_latest.md` |

缺口集中在：**统一状态机**、**LLM 规划循环**、**合规子系统**、**对话式指挥与闸门**，见下节。

---

## 6. 普查复盘：已覆盖 vs 未充分覆盖

### 6.0 高效入口（推荐）

- **已有「填写中」办件**：从门户 **办件进度** 点 **继续办理** 进入 `core` / 表单，再按需 **上一步** 探路，通常比从 `name-register/guide/base` 重开更高效。脚本：`system/cdp_resume_draft_explore.py` 或 `办件继续办理并回退探索.cmd`（输出 `dashboard/data/records/cdp_resume_draft_explore_latest.json`）。若列表为空或系统异常提示，需稍后重试或换网络/代理。
- **guide/base → core 矩阵普查**：`system/cdp_guide_base_to_core_census.py` 或 `guide_base到core普查.cmd`；根字段 **`census_schema=ufo.guide_base_core_census.v1`**，按 **`entTypes`** 分段写 **`segments[].rounds[]`**（每轮含 S08 级联/MessageBox 摘要、是否出现 `core.html` / 云提交文案）；默认跑满 ent 列表，**`--stop-on-core`** 可在首段进 core 后早停。

### 6.0b 验收线 L1（你方已确认愿意收敛的范围）

**范围（固定）**：`busiType=02_4`、`entType=1100`（有限公司等常见设立组合之一，**不**代表已扫清其它主体类型）。

**路径**：`name-register.html#/guide/base?...` → **`core.html`** → 在 core 内用类人节奏多次执行「关弹窗/主按钮」推进，直至满足下面「材料第一屏」判据或轮次耗尽。

**「材料第一屏」判据（可自动化验收）**，满足任一即 **`AC-L1-MATERIALS-FIRST`** 为真：

1. 页面上存在 **可见** 的 `input[type=file]`（`visible_file_inputs ≥ 1`）；或  
2. `input[type=file]` 总数 ≥ 1 **且**（正文命中材料类关键词 **或** hash 含 material/attach/upload 等提示）；或  
3. 正文命中材料类关键词 **且** 存在 Element **`el-upload`** 区域（`el_upload_count ≥ 1`）。

**不做什么**：不自动点击「云提交」；若提前出现云提交类文案，脚本停在本线并记 **`verdict=partial`/`fail`**，由人决定后续。

**产出**：`system/cdp_acceptance_line_02_4_1100.py` 或 **`验收线L1_02_4_1100.cmd`** → `dashboard/data/records/acceptance_line_02_4_1100_latest.json`，根字段 **`acceptance_line_schema=ufo.acceptance_line_02_4_1100.v1`**，内含 **`acceptance[]`** 与 **`verdict`**（**`pass`** = 五项 AC 全过；**`partial`** = 已进 core 但未达材料判据；**`fail`** = 未进 core）。**退出码**：`0` = `pass`，`1` = 其它结束态，`2` = 无 CDP 页签。

**与「未知已清零」的关系**：本线 **只证明** 在 02_4+1100 下「能自动走多远」；**不**等价于 core 全表单、其它 entType、云提交后链路已普查完毕。

### 6.3 全量普查矩阵（样本与选项：目标清单）

下列维度需 **组合成「单元格」** 逐格推进；**每一格** 理想产出 = 一次 **真实跑** + **`census_run_record` 或等价 JSON** + 脚本原始输出。未跑的格子在矩阵表中保持 **空白/待办**，**不**与「已普查」混淆。

| 维度 | 说明（示例值，非穷举） |
|------|------------------------|
| **门户/入口** | 全部服务→设立；`enterprise-zone`；`namenotice`；`guide/base` 直进；办件进度→继续办理；`--resume-current` 续跑。 |
| **busiType** | 至少覆盖 `services_all.json` / 业务配置中与设立相关的条目（如 `02_4` 及你们实际会办的其他事项码）。 |
| **entType** | 至少 **1100、4540** 及个体/合伙等实际会办类型（以官方下拉为准逐项扫）。 |
| **name-register / S08** | 名称 MessageBox 各分支；住所级联成功/失败；与 **entType** 交叉。 |
| **core 路由深度** | `#/flow/base/` 下各步：`name-check-info`、`basic-info`、`member-post`、材料/附件相关 hash（以实际路由为准全列）。 |
| **材料与上传** | 每类 `input[type=file]` / `el-upload` 槽位；替换文件；失败 toast；与 **material_pack** 槽位映射。 |
| **云提交与前后** | 云提交文案停点；云帮办若出现；**不自动点提交**前提下截图与接口尾。 |
| **接口与码** | 关键 `icpsp-api`：`code`/`message` 与 UI 一致性；401/会话过期；重复提交类提示。 |
| **环境与劣化** | 6087/证书；代理；弱网；多标签 CDP 选错页；仅记录策略不强行「自动化绕过」。 |
| **强认证** | 实人/短信/银行卡等出现位置与文案；**仅记录与闸门策略**，不录敏感数据。 |

**整合 LLM 的时机**：当 **目标业务范围** 在上述矩阵上的「必跑格」均有记录（或明确 **豁免**），再启动阶段 2 的工程量评估；否则 LLM 只会放大 **未知** 而非消除未知。

### 6.4 真实跑记录义务（ufo.census_run_record.v1）

每次 **真实环境、真实账号/扫码会话** 的普查或长脚本跑批，建议复制 **`dashboard/data/records/census_run_record.v1.example.json`**，填写：

- **matrix_axes**：本跑对应哪几格（入口、`busi_type`、`ent_type` 等）；  
- **artifacts**：关联的 `packet_chain` / 截图目录 / mitm 行号范围；  
- **observed_issues[]**：**原文级** 现象（风控提示、系统异常、静默失败、接口与 UI 不一致）；  
- **conclusion.census_cell_closed**：本格是否可签 **关闭**；**next_matrix_cells** 下一批待跑组合。

原则：**遇到的问题一律记下**——脚本与 LLM **迟早**会在同一格复现；无记录则每次从零 debug。

### 6.1 已相对充分普查的方向

- **9087 门户**：全部服务、设立登记入口、企业专区、`name-register` SPA、`#/guide/base`（S08）行为与部分弹窗、级联交互。  
- **逆开发方法论**：四层抓包、上下文表、设立 02_4 相关 playbook 与多轮 full submit 试验记录。  
- **CDP 工程化**：断线重连、主按钮兜底、弹窗主按钮、部分 stagnate 恢复策略。  
- **附件路径**：`input[type=file]` + `DOM.setFileInputFiles` 的可行性验证（需在已进入含上传控件的页面时生效）。

### 6.2 未充分或仅点状覆盖的方向

- **`core.html` 全链路**：材料页、多步骤表单、校验错误组合、**不同 entType / busiType** 的差异化分支。  
- **从 guide/base 稳定进入 core 的充要条件**：名称选择、住所级联、MessageBox 顺序与 **1100 vs 4540** 等类型组合的系统化矩阵。  
- **云提交页面前后**：文案变体、云帮办模式选择、与后端接口的对应、**停点后**人工操作的日志模板。  
- **变更、注销、名称单独申报** 等非设立主线的服务矩阵（`services_all.json` 中 P1–P3）。  
- **6087 / 证书异常 / 代理不可用** 等运行环境劣化下的降级与提示策略。  
- **实人、短信、银行卡等强认证** 与自动化边界的组合场景（仅记录，不绕过）。  
- **附件合规**：格式、大小、分辨率、签字盖章要求、与字段标签的模糊匹配（当前仅关键词 + accept）。

---

## 7. 死角与暗角清单（优先补普查）

以下项易导致「脚本以为在跑、实际在空转或走错分支」，列为 **P0 普查**：

1. **S08 级联失败**：`el-cascader` 未展开、遮罩层、只读、或选项异步未返回时的 DOM 状态。（工程上已实现：连续停留 `guide/base` 达阈值则早停并写 **`s08_exit_diagnostic`** + `blocker_evidence`；可用 **`--resume-current`** 从当前 9087 页续跑。）  
2. **多标签页 / 多窗口**：CDP 选中非目标页签时的 `pick_icpsp_target` 行为与误判登录态。  
3. **Vue 异步校验**：点击「下一步」后校验未通过但无 `.el-form-item__error` 的静默失败。  
4. **iframe / 微前端**：若存在子框架，当前 `document` 级 probe 是否失效。  
5. **文件上传后前端状态**：`el-upload` 列表更新、二次提交同一 slot、替换文件。  
6. **接口成功但 UI 失败**：`code=00000` 与页面仍 toast 不一致的交叉取证。  
7. **会话过期中途**：`Authorization` 失效时 UI 与接口的联合表现及自动刷新策略（若有）。  
8. **长任务与 WebSocket 超时**：截图或 CDP 阻塞对「证据链完整性」的影响。

**P1 普查**：各 `busiType` 与 `entType` 组合下的路由深度、材料清单差异、字典依赖接口全集。

---

## 8. 下一步开发优先级（对齐路线图）

**硬规则**：在 **§6.3 矩阵** 对约定范围未形成「可签字的运行记录集」前，**不以「接 LLM」为当期主里程碑**；当期主里程碑是 **补格 + 记问题 + 断言/字典沉淀**。

1. **统一「一次任务」数据模型**（阶段 1）：**已落地** `ufo.gov_task_run.v1` — `packet_chain_portal_from_start` 每条 run 含 **`run_id`**、**`task`**（`state`: completed / partial / failed、`events[]` 步骤摘要、`summary`）；与既有 `steps` / `acceptance` 并存，便于外部流水线索引。  
2. **guide/base → core**：`blocker_evidence` 在 URL 含 `guide/base` 时附加 **`guide_base_structured`**；**普查脚本已提供**：`system/cdp_guide_base_to_core_census.py`（`--ent-types` 矩阵、`--no-autoclick` 只读诊断）；仍待：**§6.3 全矩阵** 逐格真实跑 + **`census_run_record`**。  
3. **观测摘要管道**：`packet_chain` 已写 **`llm_observations[]`**；另提供 **`system/llm_run_digest.py`** 从完整 JSON 生成 **`ufo.llm_run_digest.v1`**（`acceptance` + `observations` 尾部 + `task` + `blocker` 标签等），供规划层固定上下文窗口。  
4. **合规与材料**：**`config/material_pack.schema.json`**（**`ufo.material_pack.v1`**）描述槽位、角色、路径与合规备注；示例实例 **`config/rehearsal_material_pack.example.json`**。与现有 **`config/rehearsal_assets.json`**（CDP `--assets` 直读）并存，后续可将附件脚本改为优先读 material_pack 再回落 assets。  
5. **重放断言（回归）**：`replay_lab_ui` 提供 **`POST /api/replay_one_assert`**（`index` + `assertions[]`）；`mitm_replay_core.replay_one_record` 返回 **`resp_json`**（可解析 JSON 体时）。  
6. **digest HTTP**：`replay_lab_ui` 提供 **`GET/POST /api/llm_digest`**（`rel_path` 仅限 `dashboard/data/records/*.json`、`obs_tail`）；与 CLI **`system/llm_run_digest.py`** 等价；已支持 **`acceptance_line_02_4_1100_latest.json`**（`acceptance_line_schema`）摘要。  
7. **LLM 规划壳（阶段 2）**：排在 **§6.3–6.4** 对目标业务范围收敛之后；见 **§4.0**。

---

## 9. 文档使用约定

- 新功能评审自问：**是否增强观测、是否落入 HITL、是否可审计、是否写进阶段判据**。  
- 重大演练或生产试验后：**更新第 6、7 节**「已普查 / 新发现死角」。  
- 与本标准冲突的旧习惯：**以本标准为准**，旧文档可保留历史价值但须在头部注明「已被 xxx 替代」。

---

*本文件路径：`docs/LLM政务自动化框架_目标与实施标准.md`*
