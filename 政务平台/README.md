# 广西经营主体登记平台 — 自动化工程

**专业工作流程（推荐全员按此执行，避免无证据乱改脚本）**：[docs/专业逆向与自动化流程_SOP.md](docs/专业逆向与自动化流程_SOP.md)（环境 → 抓包取证 → 状态机 → 自动化边界 → 普查证据 → 最后才 LLM）。  
**阶段验收（何谓完成、能否下一步）**：[docs/阶段验收清单.md](docs/阶段验收清单.md)；跑批输出 JSON 中看 **`phase_verdict`** + **`acceptance`**（勿只看点没点着）。

长期目标与实施标准（**先普查与真实跑记录、后整合 LLM**；分阶段路线图与普查死角）见：**[docs/LLM政务自动化框架_目标与实施标准.md](docs/LLM政务自动化框架_目标与实施标准.md)**。每次真实跑可归档：**[dashboard/data/records/census_run_record.v1.example.json](dashboard/data/records/census_run_record.v1.example.json)**（`ufo.census_run_record.v1` 模板）。  
逆开发与复现的**思维顺序**（上下文 → 框架 → 填数据）：**[docs/逆向复现方法论_上下文先行与数据填充.md](docs/逆向复现方法论_上下文先行与数据填充.md)**。  
提升「坚固性」的**待办路线图**（环境 → 状态机 → 断言/回归 → 普查 → 数据 → LLM）：**[docs/加固路线图_要做的事.md](docs/加固路线图_要做的事.md)**。  
9087 **实网调试纪律**（单步、延时、禁止死循环与并发）：**[docs/实网开发操作纪律_单步与风控.md](docs/实网开发操作纪律_单步与风控.md)**（与 `docs/资料.txt` 等案例数据配合使用）。  
**设立登记两阶段**（名称登记 → 我的办件继续办理 → 资料录入至云提交停点）：**[docs/设立登记两阶段流程.md](docs/设立登记两阶段流程.md)**。  
**仅第一阶段（名称入口 + 快照，不跑至云提交）**：[docs/第一阶段_名称登记执行说明.md](docs/第一阶段_名称登记执行说明.md)。轻量：`run_case_rongxian_to_yun_submit.py --phase1-only`；**按案例推进专区→须知→guide→名称查重填字号**：`python system/run_phase1_from_case.py`。  
**类人边界与风控**（无法承诺平台 100% 不拦截；工程上如何保证节奏与实战自检）：**[docs/类人边界与实战约定.md](docs/类人边界与实战约定.md)**。

## 目录结构

```
政务平台/
├── docs/                    # 标准与架构（含 LLM 自动化框架目标与实施标准）
├── config/                  # 配置文件
│   ├── browser.json         # 浏览器启动配置（CDP端口、User Data目录）
│   ├── human_pacing.json    # CDP 类人节奏（min_delay_sec≥1s、乘子+抖动；业务动作间隔固化）
│   └── site.json            # 网站技术栈、页面结构、导航配置
├── survey/                  # 普查数据
│   ├── survey_result_raw.json   # CDP 原始普查结果
│   └── automation_strategy.md   # 自动化策略文档
├── routes/                  # 路由清单
│   └── routes_all.json      # 全部 100 条 Vue Router 路由（含分类、认证标记）
├── services/                # 服务清单
│   └── services_all.json    # 全部 40+ 项服务（含自动化优先级、难度评估）
├── scripts/                 # 脚本工具
│   ├── cdp_helper.py        # CDP 自动化核心库（连接、跳转、表单操控、截图）
│   ├── survey.py            # 网站普查脚本
│   └── launch_browser.py    # 浏览器启动脚本
└── automation/              # 自动化用例（待开发）
```

## 快速开始

### 1. 启动浏览器（Chrome Dev + CDP 9225）
配置集中在 `config/browser.json`（可改 `executable` / `user_data_dir` / `start_url`）。推荐：
```powershell
cd G:\UFO\政务平台
.\scripts\start_chrome_dev_cdp.ps1
```
或：`python scripts\launch_browser.py`（需在 `政务平台` 目录下执行，以便读取 `config/browser.json`）。

**登录态（与「每次都要重新登录」的区别）**：`launch_browser.py` 使用的 `user_data_dir` 在 `config/browser.json` 中固定（默认 `C:\Temp\ChromeDevCDP`）。**只要一直用这套配置启动**，Token / 本地存储会保留，**再次打开往往仍是已登录**，不必像新开无痕或换用户目录那样从头登录。换目录、换浏览器配置、或另开未走该配置的 Chrome，才会变成「全新会话」。

### 2. 连接并操作
```python
from cdp_helper import CDPHelper

helper = CDPHelper()
helper.connect()

# 页面跳转
helper.navigate('/index/enterprise/enterprise-zone')

# 填写表单
helper.set_el_input('.el-input__inner', '测试值')

# 点击按钮
helper.click_button('提交')

# 读取表格数据
data = helper.get_el_table_data()

# 截图
helper.screenshot('screenshot.png')

helper.close()
```

### 3. 执行普查
```powershell
python g:\UFO\政务平台\scripts\survey.py
```

## 技术栈

- **平台**: Vue 2 + Element-UI + Vuex + Vue-Router (hash mode)
- **控制**: Chrome DevTools Protocol (CDP) 端口 9225
- **浏览器**: Chrome Dev (`C:\Program Files\Google\Chrome Dev\Application\chrome.exe`)
- **User Data**: `C:\Temp\ChromeDevCDP`（登录态持久化）

## 认证机制

**纯 Token 认证，无 Cookie。**

| 认证项 | 存储位置 | 说明 |
|---|---|---|
| `Authorization` | localStorage | API 请求头认证（32位hex） |
| `top-token` | localStorage | 辅助认证（UUID格式） |

API 请求通过 Header 注入：`Authorization: 2060d9e762d64024a76bb3bea2fb5c09`

详见 `survey/auth_analysis.md`

## 反向代理 / API 网关

### 方案一：简单反向代理
```powershell
python g:\UFO\政务平台\scripts\reverse_proxy.py --port 8080
```

### 方案二：API 网关（推荐）
```powershell
python g:\UFO\政务平台\scripts\api_gateway.py --port 8080
```

**网关特性：**
- Token 自动注入（从 CDP 浏览器获取）
- Token 自动刷新（每5分钟，401时立即刷新）
- API 响应缓存（LRU，减少重复请求）
- 请求日志记录
- Web 管理面板

**管理接口：**
| 路径 | 说明 |
|---|---|
| `/_admin/status` | 网关状态、Token 信息 |
| `/_admin/token/refresh` | 手动刷新 Token |
| `/_admin/cache/clear` | 清理缓存 |
| `/_admin/token/set` (POST) | 手动设置 Token |

**使用示例：**
```bash
# 查询网关状态
curl http://localhost:8080/_admin/status

# 调用政务平台 API（Token 自动注入）
curl http://localhost:8080/icpsp-api/v4/pc/common/tools/getCacheCreateTime

# 手动设置 Token
curl -X POST http://localhost:8080/_admin/token/set \
  -H "Content-Type: application/json" \
  -d '{"authorization":"your-token","top_token":"your-top-token"}'
```

## 开工准备（环境一次装好）

1. **Python**：3.10 或 3.11（与仓库 UFO 说明一致）。
2. **安装依赖**（二选一）：
   - **全量 UFO 环境**（在仓库根目录 `G:\UFO`）：
     ```powershell
     cd G:\UFO
     python -m pip install -U pip
     python -m pip install -r requirements.txt
     ```
     若 `requirements.txt` 含非 ASCII 注释导致 pip 在部分 Windows 区域设置下报错，请确保该文件为 UTF-8；当前仓库内该文件注释为英文以避免 GBK 解码失败。
   - **仅政务平台脚本**（推荐单独虚拟环境，避免与全局包冲突）：
     ```powershell
     cd G:\UFO\政务平台
     python -m venv .venv-portal
     .\.venv-portal\Scripts\Activate.ps1
     python -m pip install -U pip
     python -m pip install -r requirements-portal.txt
     ```
   - **一键装好（推荐）**：用 **Python 3.11** 创建 `.venv-portal` 并安装 `requirements-portal.txt`（mitmproxy 在 Windows 上比 3.13 全局环境更稳）：
     ```powershell
     cd G:\UFO\政务平台
     .\scripts\setup_portal_env.ps1
     ```
3. **快速自检**（激活 venv 后应打印 `ok`）：
   ```powershell
   cd G:\UFO\政务平台
   .\.venv-portal\Scripts\python.exe -c "import requests, websocket, mitmproxy.http; print('ok')"
   ```
4. **浏览器（Chrome Dev + CDP 9225）**：参数见 `config/browser.json`。启动：
   ```powershell
   cd G:\UFO\政务平台
   .\scripts\start_chrome_dev_cdp.ps1
   ```
   先在该配置档指定的 **User Data**（默认 `C:\Temp\ChromeDevCDP`）里登录政务站点，再跑 CDP/脚本。
5. **mitmproxy 抓包（L0，推荐与 CDP 并行）**：需已执行 `setup_portal_env.ps1`。启动（**无需**再手动 `Activate`，脚本会调用 venv 内 `mitmdump`）：
   ```powershell
   cd G:\UFO\政务平台
   .\scripts\run_mitm_capture.ps1
   ```
   等价命令：`mitmdump -s system\mitm_capture_ufo.py`（需在 `政务平台` 目录下以便 addon 解析输出路径）。默认监听 **127.0.0.1:8080**；将系统或 **Chrome「使用系统代理」/ 手动 HTTP(S) 代理** 指到该端口，并按 mitmproxy 说明安装并信任 **mitm 根证书**。命中 `6087` / `9087` / `icpsp-api` / `TopIP` 的响应会追加写入 `政务平台/dashboard/data/records/mitm_ufo_flows.jsonl`（每行一条 JSON，含请求/响应头与截断后的 body）。
6. **API 网关（可选）**：`python G:\UFO\政务平台\scripts\api_gateway.py --port 8080`（Token 从 CDP 浏览器拉取，见上文管理接口）。
7. **设立登记迭代跑通 + 验收（CDP 已登录、9225 可用）**：
   ```powershell
   cd G:\UFO\政务平台
   .\.venv-portal\Scripts\python.exe system\establish_iterate_dev.py
   ```
   默认从「全部服务」同款入口（`fromPage=/guide/base`）导航并点击「设立登记」；自动点「继续办理设立登记/同意/下一步/保存并下一步」及 **Element 弹窗主按钮兜底**；**以页面出现「云提交」等文案为停点**（不自动点提交）；每轮带 **`l3_step_code`**（与 `context_table_driven_playbook` 粗对齐）与 **L2 hook** 重装；**`Network.enable`** 在会话起点打开；含 CDP 断线重连。**S08（`#/guide/base`）** 使用 **`GUIDE_BASE_AUTOFILL_V2`**（名称类 MessageBox 优先确定、「未办理企业名称预保留」优先于「未申请」）+ **级联双通道**（首轮逐层首项后再开级联并尝试第二项降级）；**同一 hash 连续多轮不变** 时自动再跑一轮 autofill+级联。卡点时：**读 UI 报错/弹窗** 写入 `blocker_evidence`，**`last_api`** 写入 **`hook_tail`（`__ufo_cap` 尾部）** 与 **`perf_resource_tail`（含 `icpsp-api` 的 resource 条目）**，hook 为空时会短重装再读；**CDP 截屏 PNG** 写入 `dashboard/data/records/packet_chain_shots/`，并尝试 `recovery_stuck_js`。JSON 内 `framework` 说明方法论；`acceptance` 含 **AC-YUN-SUBMIT**、**AC-BLOCKER-EVIDENCE**、**AC-NO-EARLY-AUTH**。主输出：`establish_iterate_latest.json`。等价参数见 `python system\packet_chain_portal_from_start.py -h`。**S08 早停**：连续卡在 `name-register#/guide/base` 达阈值会中止并写入 `s08_exit_diagnostic`。**续跑**：`--resume-current` 跳过门户导航（见 `演练从当前页继续.cmd`）。**办件草稿**：从办件进度点「继续办理」再「上一步」探路见 `办件继续办理并回退探索.cmd` / `system/cdp_resume_draft_explore.py`。

## 自动化优先级

| 优先级 | 场景 | 难度 |
|---|---|---|
| P0 | 办件进度查询、名称查询、经营范围查询 | ⭐ |
| P1 | 设立登记、变更备案登记、名称自主申报 | ⭐⭐⭐ |
| P2 | 股权出质、减资公告、迁移登记 | ⭐⭐⭐⭐ |
| P3 | 电子签名、注销登记 | ⭐⭐⭐⭐⭐ |
