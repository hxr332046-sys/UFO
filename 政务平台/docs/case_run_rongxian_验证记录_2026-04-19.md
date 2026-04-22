# 资料案例「广西容县李陈梦软件开发有限公司」— 跑通验证记录

**资料来源**：`docs/资料.txt`  
**结构化案例**：`docs/case_广西容县李陈梦.json`  
**附件配置**：`config/rehearsal_assets_rongxian.json`（已扩展支持 `lease_contract`，见 `system/cdp_attachment_upload.py`）  
**执行脚本**：`system/run_case_rongxian_to_yun_submit.py`（内部调用 `packet_chain_portal_from_start`，至**云提交文案停点**，不点提交）

---

## 1. 附件路径预检（本机）

| 文件 | 路径 | 本次检查 |
|------|------|----------|
| 身份证正面 | `G:\YU\资料\身份证正面_副本.jpg` | 存在 |
| 身份证反面 | `G:\YU\资料\身份证正面.jpg`（资料原文档文件名如此） | 存在 |
| 租赁合同图 | `G:\YU\资料\微信图片_20260411104217_91_17.jpg` | 存在 |

---

## 2. 运行 A：从门户入口（默认）

**命令**：`run_case_rongxian_to_yun_submit.py --human-fast`

**现象**：

- CDP 连接成功；导航至门户「全部服务」后，快照中顶栏出现 **「登录 / 注册」访客条**，`likelyLoggedIn=false`。  
- `try_activefuc_establish` 报 `no_card`（卡片列表与 activefuc 未命中），靠 DOM 点「设立登记」继续。  
- 随后 **`blocked_need_login`** → **`abort`**：脚本策略为「顶栏不像已登录则中止」，避免在访客态空转。

**结论**：当时 **CDP 所连页签** 在门户页上呈现为访客顶栏（或存在多标签、未切到已登录办件页）。**未进入** name-register / guide/base / core，**未到云提交**。

**建议**：仅保留一个已登录 9087 页签并置于前台；或直接使用 **运行 B**。

---

## 3. 运行 B：从当前页续跑（`--resume-current`）

**命令**：`run_case_rongxian_to_yun_submit.py --resume-current --human-fast`

**现象**：

- 跳过门户重跑，从当前 9087 页装 hook 进入主循环。  
- 若干轮后，页面 **`href` 变为 `chrome-error://chromewebdata/`**，正文为 **「您的连接不是私密连接」**，**`NET::ERR_CERT_DATE_INVALID`**（证书日期无效）。  
- 后续轮次无可用主按钮、无 file 输入、hook 为空；最终 **`stopped_without_yun_submit`**（`max_primary_rounds_or_abort_streak`），**未检测到云提交文案**。

**结论**：**浏览器/系统证书或系统时间异常**导致 HTTPS 中断，自动化无法停留在 `icpsp-web-pc` 业务页。这与业务表单是否填全无关，属于 **环境阻塞**。

**建议**：

1. 校准本机系统时间；  
2. 使用仓库内 **「忽略证书错误」** 方式启动 Chrome（若已有 `打开登录器_忽略证书错误.cmd` 等）；  
3. 待能在同一 CDP 页签稳定打开 `https://zhjg.scjdglj.gxzf.gov.cn:9087/...` 后，再重跑本脚本（可先 `--resume-current`）。

---

## 4. 与「按资料填公司信息」的差距说明

当前 `packet_chain` 主链以 **导航 + 主按钮 + 附件槽位匹配** 为主，**未**把 `case_广西容县李陈梦.json` 中的公司全称、住所、注册资本、人员信息等 **逐字段写入** Vue 表单（需单独 CDP 填表脚本或人工在浏览器中填写）。

本次跑批价值在于：**真实环境下调试链路与错误类型**（登录态、证书、多标签、附件探测等）。待 HTTPS 与登录态稳定后，可：

- 人工在页面中按 `资料.txt` 填写；或  
- 后续增加「按 case JSON 注入 `businessDataInfo` / 表单项」的专用脚本，与 `packet_chain` 分段衔接。

---

## 5. 产出文件路径

| 类型 | 路径 |
|------|------|
| 完整 JSON（含 `case_profile`、`preflight`、`task`） | `dashboard/data/records/case_run_rongxian_latest.json` |
| 演练摘要 MD | `dashboard/data/records/case_run_rongxian_rehearsal.md` |
| 迭代对照 | `dashboard/data/records/establish_iterate_latest.json` |

---

*记录生成：自动化跑批与日志整理；请在修复证书/登录后重新执行并更新本节。*
