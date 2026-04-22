# packet_lab（协议逆向 / 自动化研究）

**目的**：在**隔离环境**里做 mitm 抓包的**脱敏分析**与脚本试验，支撑**合法自动化**（重放协议、对接网关、CDP 取 Token），不用于破坏或越权。

## 登录态在哪

- 协议层：请求头 **`Authorization`**（与门户 `localStorage` 一致）+ 常见 **`Cookie`**。
- 不在此目录存放明文 Token；用 `extract_login_context.py` 只输出 **长度 / SHA256 / Cookie 名列表**。

## 本机 Docker 位置（当前环境）

- **命令行 `docker.exe`**：`C:\Program Files\Docker\Docker\resources\bin\docker.exe`（已在 PATH，`where docker` 可见）
- **Docker Desktop**：`C:\Program Files\Docker\Docker\Docker Desktop.exe`
- **当前上下文**：`desktop-linux`（引擎 `npipe:////./pipe/dockerDesktopLinuxEngine`）

## 容器（Docker）

```bash
cd 政务平台/packet_lab
docker compose build
docker compose run --rm packet-lab
```

报告：`out/login_context_report.json`（挂载到宿主 `packet_lab/out/`）。

## 单独提取登录态（供容器使用）

不改造登录器，只在你完成官方扫码后，从本地监听/抓包中提取运行时请求头：

```powershell
cd G:\UFO\政务平台
.\.venv-portal\Scripts\python.exe packet_lab\export_runtime_auth_headers.py
```

输出文件：

- `packet_lab/out/runtime_auth_headers.json`

容器内路径（已挂载）：

- `/lab/out/runtime_auth_headers.json`

说明：该文件包含运行时 `Authorization`（及可能存在的 `Cookie`），仅用于本地自动化，勿提交到远端仓库。

## 用登录态复现「刚才那一串操作」（按包顺序重放）

抓包里每条请求都带当时的 **`Authorization` + `Cookie`**，脚本按 mitm 文件顺序重放即可（Token 有效期内）。

在 `政务平台` 目录执行（`--skip-lines` = 跳过前面行数，从下一行开始；你上次基线可用 `308`）：

```powershell
cd G:\UFO\政务平台
.\.venv-portal\Scripts\python.exe system\replay_mitm_flow_slice.py --mitm dashboard/data/records/mitm_ufo_flows.jsonl --skip-lines 308 --max 60 -o dashboard/data/records/replay_mitm_flow_slice.json
```

更稳的自动化：不要依赖旧 mitm，而用 **CDP** 每次从页面读 `localStorage` 再发请求（见 `scripts/api_gateway.py` 思路）。

## 本地网页：这一小段是否「掌握」了

启动（勿用 Cursor 直接点开 `.py`，用 cmd 或下面 `.cmd`）：

```text
双击 政务平台\START_REPLAY_LAB.cmd
```

或：`cd G:\UFO\政务平台` 后执行  
`.\\.venv-portal\\Scripts\\python.exe packet_lab\\replay_lab_ui.py`  
浏览器打开 **http://127.0.0.1:8766/**

- **mitm 路径、skip、条数** 可在页面上改（默认读 `.mitm_listen_baseline` 与默认 jsonl，仍可不写死）。
- **加载片段** → 列出你抓到的 `icpsp-api` 步骤；**重放本条** / **按序全部重放** 即用包里的登录态再打一遍。  
- **带断言重放**：`POST /api/replay_one_assert`，JSON 体示例 `{"index": 0, "assertions": [{"type": "http_status", "equals": 200}, {"type": "json_field_equals", "path": "code", "value": "00000"}]}`，响应当中含 `replay.resp_json` 与 `assertion_result`。  
- **LLM digest**：`GET /api/llm_digest?rel_path=packet_chain_portal_from_start.json&obs_tail=28` 或 `POST /api/llm_digest` 同参；路径**必须**落在 `dashboard/data/records/` 下且为 `.json`。页内「LLM 运行摘要」卡片可一键生成。
- **名称可用性查询（按包）**：页面下半区可直接输入 *区域码/主体类型/组织形式/行业码/行业特征* 与名称，调用：
  - `bannedLexiconCalibration`（禁限用字词提示）
  - `nameCheckRepeat`（名称库查重与 stop 原因）
- **逆开发字典数据库 V2**：页面下半区可重建并检索 SQLite 字典库（分类检索、协议规范、操作方法）。
- **V2.1 查询样本沉淀**：每次调用“名称可用性查询（按包）”会自动写入 `dict_v2.sqlite` 的 `query_cases`，可在面板“查看最近查询样本”中追溯。

若列表与真实操作一致、且关键 `POST` 重放仍返回业务 `00000`，可以认为：**这一小段的请求形态与登录态用法已被你方逆向掌握**（后续自动化应改为 CDP 动态取 Token，而不是长期绑死旧包）。

## 与主工程的关系

- 抓包源文件：`dashboard/data/records/mitm_ufo_flows.jsonl`（mitmdump + `mitm_capture_ufo.py`）。
- 方法论：`dashboard/data/records/four_layer_packet_breakthrough_method.md`。
- V2 数据库：
  - 构建脚本：`system/build_dict_v2.py`
  - 存储引擎：`system/dict_v2_store.py`
  - 数据库文件：`dashboard/data/records/dict_v2.sqlite`
  - 查询样本：`query_cases`（字段含 name/dist/entType/提示/stop 原因/结果快照）
