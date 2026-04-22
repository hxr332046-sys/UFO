# UFO² Desktop AgentOS — 能力边界文档

> 测试环境：Windows 10 (10.0.19045) | Python 3.13.1 | UFO² v2.0.0 (仓库最新 main 分支)  
> 测试时间：2026-04-12  
> 测试方式：全功能自动化边界测试（104 项测试）

---

## 一、能力总览

| 能力域 | 状态 | 能力等级 |
|--------|------|---------|
| 窗口枚举 | ✅ 可用 | ★★★★☆ |
| 控件检测 | ✅ 可用 | ★★★☆☆ |
| 命令执行 | ✅ 可用 | ★★★★★ |
| 截图标注 | ✅ 可用 | ★★★★☆ |
| MCP 集成 | ✅ 可用 | ★★★★☆ |
| Office 自动化 | ✅ 可用 | ★★★★☆ |
| LLM 集成 | ⚠️ 需配置 | ★★★★☆ |
| 安全护栏 | ✅ 可用 | ★★★☆☆ |
| RAG 知识基底 | ✅ 可用 | ★★★☆☆ |
| 画中画桌面 | ⚠️ 需额外配置 | ★★☆☆☆ |
| 多动作推测执行 | ✅ 可用 | ★★★★☆ |
| 自定义 Agent | ✅ 可用 | ★★★★☆ |

---

## 二、窗口枚举能力

### ✅ 能做到

| 功能 | 说明 | 实测结果 |
|------|------|---------|
| 枚举所有顶层窗口 | UIA + Win32 双通道 | UIA 检测 10 个 / Win32 检测 19 个可见窗口 |
| 获取窗口属性 | 名称、类名、PID、控件类型、位置 | 全部可获取 |
| 获取不可见窗口 | Win32 可枚举 353 个窗口（含 334 个不可见） | 可枚举但无法交互 UI 树 |
| 系统托盘窗口 | Shell_TrayWnd / Shell_SecondaryTrayWnd | ✅ 可检测 |
| 桌面背景窗口 | Progman / WorkerW | ✅ 可检测 |
| 最小化窗口 | 可检测到 2 个 | 可检测但 UIA 树可能不完整 |
| 进程信息关联 | PID → 进程名、用户名 | ✅ 通过 psutil 获取 |

### ❌ 做不到

| 限制 | 说明 |
|------|------|
| **跨用户会话窗口** | 无法访问其他用户登录会话的窗口 |
| **安全桌面窗口** | UAC 提示框、登录界面在独立安全桌面，完全不可见不可控 |
| **其他虚拟桌面窗口** | Windows Task View 的非活动虚拟桌面上的窗口，UIA 无法看到 |
| **不可见窗口的 UI 树** | Win32 可枚举 hwnd，但 UIA 无法穿透获取内部控件 |

### ⚠️ 注意

- **UIA vs Win32 差异**：UIA 只返回"有意义"的窗口（约 10 个），Win32 返回所有可见窗口（约 19 个）。UFO² 内部同时使用两者互补。
- **最小化窗口**：UIA 树可能为空或不完整，需先 Restore 窗口才能完整操作。

---

## 三、控件检测能力

### ✅ 能做到

| 功能 | 说明 | 实测结果 |
|------|------|---------|
| 26 种标准控件类型 | Button/Edit/Text/List/Tree/Tab/Menu/ComboBox/CheckBox/Radio/Slider/Spinner/Hyperlink/ScrollBar/DataItem/DataGrid/Document/Group/Header/Image/ProgressBar/StatusBar/ToolBar/ToolTip/Window/Pane | 全部可用 |
| UI 树遍历 | 递归获取控件层级 | 最深实测 5 层（受限于当前打开的窗口），理论上无硬性深度限制 |
| 控件属性读取 | BoundingRectangle/ControlTypeName/AutomationId/IsEnabled/IsOffscreen/ProcessId 等 | 全部可读 |
| 混合检测 | UIA 元数据 + 视觉模型（OmniParser）融合 | 代码支持，需额外部署 OmniParser 端点 |

### ❌ 做不到

| 限制 | 说明 |
|------|------|
| **DirectX/OpenGL 游戏控件** | 游戏窗口 UIA 返回空树或极简树，无可用控件信息 |
| **自绘/Owner-draw 控件** | 部分旧版 MFC/Win32 应用自绘控件，UIA 无法识别内部结构 |
| **Chrome 渲染内容** | Electron/Chrome 窗口的网页内容区域，UIA 只能访问地址栏/标签栏，无法访问 DOM |
| **虚拟机内部控件** | VM 控制台窗口只能操控窗口框架，无法穿透到 Guest OS 内部 |
| **RDP 远程会话控件** | RDP 客户端窗口同上，无法控制远程桌面内容 |

### ⚠️ 注意

- **Electron 应用**（如 VS Code、Windsurf、Discord）：UIA 树非常浅，主要依赖视觉检测。本机实测 6 个 Electron 应用。
- **WPS Office**：`KPromeMainWindow` 类，UIA 支持可能不如 Microsoft Office 完善。
- **OmniParser**：混合检测的视觉部分需要单独部署 OmniParser Gradio 服务端点，默认配置指向公共 demo 地址，不稳定。

---

## 四、命令系统能力

### ✅ 全部 20 个命令可用

| 命令 | 类别 | 说明 |
|------|------|------|
| `ClickCommand` | 控件点击 | 基于 UIA 控件的点击 |
| `ClickInputCommand` | 模拟点击 | 模拟鼠标输入事件 |
| `ClickOnCoordinatesCommand` | 坐标点击 | 指定屏幕坐标点击（兜底方案） |
| `DoubleClickCommand` | 双击 | 控件双击 |
| `SetEditTextCommand` | 文本输入 | 设置编辑框文本（两种模式） |
| `TypeCommand` | 键入文本 | 模拟键盘逐字输入 |
| `KeyPressCommand` | 按键 | 单个按键（支持组合键需多次调用） |
| `keyboardInputCommand` | 键盘输入 | 底层键盘输入命令 |
| `WheelMouseInputCommand` | 滚轮 | 鼠标滚轮滚动 |
| `ScrollCommand` | 滚动 | 控件滚动 |
| `DragCommand` | 控件拖拽 | 基于 UIA 控件的拖拽 |
| `DragOnCoordinatesCommand` | 坐标拖拽 | 指定坐标的拖拽 |
| `MouseMoveCommand` | 鼠标移动 | 移动鼠标到指定位置 |
| `AnnotationCommand` | 标注 | 在截图上标注控件 |
| `GetTextsCommand` | 获取文本 | 获取控件文本内容 |
| `SummaryCommand` | 摘要 | 生成控件摘要信息 |
| `NoActionCommand` | 无操作 | 占位/跳过 |
| `WaitCommand` | 等待 | 等待指定时间 |
| `ControlCommand` | 控制命令 | 基础控制命令类 |
| `AtomicCommand` | 原子命令 | 最小执行单元 |

### ⚠️ 边界

| 限制 | 说明 |
|------|------|
| **控件级 vs 坐标级** | 控件级操作更可靠；坐标级是兜底方案，受 DPI 缩放影响 |
| **文本输入两种模式** | `set_text` 直接设置（不触发事件）vs `type_keys` 模拟键入（触发 onChange 等事件） |
| **组合快捷键** | 需多次 `KeyPressCommand` 组合实现，如 Ctrl+C 需分别发送 Ctrl↓ → C → Ctrl↑ |
| **跨窗口拖拽** | 窗口重叠位置不正确时可能失败 |
| **Receiver 系统** | `ReceiverManager` + `UIControlReceiverFactory` 负责命令分发，支持扩展 |

---

## 五、截图与标注能力

### ✅ 能做到

| 功能 | 说明 | 实测结果 |
|------|------|---------|
| 桌面截图 | DesktopPhotographer | 1920×2160（含任务栏区域） |
| PIL 截图 | ImageGrab.grab() | 1920×1080 ✅ |
| PyAutoGUI 截图 | pyautogui.screenshot() | 1920×1080 ✅ |
| 控件截图 | ControlPhotographer | 可对单个控件截图 |
| 控件标注 | AnnotationDecorator / TargetAnnotationDecorator | 在截图上标注控件边界和类型 |
| 摄影师工厂 | PhotographerFactory | 自动选择截图方式 |

### ❌ 做不到

| 限制 | 说明 |
|------|------|
| **安全桌面截图** | UAC 提示框/登录界面在安全桌面，无法截图 |
| **锁屏截图** | 屏幕锁定后无法截图或交互 |
| **多显示器独立截图** | `grab_allmonitors()` 在本环境未生效，回退到单显示器 |

### ⚠️ 注意

- **DPI 缩放**：高 DPI（150%/200%）下，截图坐标和 UIA BoundingRectangle 可能不匹配，导致点击偏移。DPI 感知级别需正确设置。
- **截图大小**：DesktopPhotographer 截图尺寸 (1920, 2160) 包含了任务栏区域，与 PIL 单屏 (1920, 1080) 不同。

---

## 六、MCP 服务器集成

### ✅ 本地 MCP 服务器（7 个）

| 服务器 | 文件 | 功能 |
|--------|------|------|
| **CLI** | `cli_mcp_server.py` | 命令行操作 |
| **Constellation** | `constellation_mcp_server.py` | Galaxy 编排支持 |
| **Excel** | `excel_wincom_mcp_server.py` | Excel COM 自动化 |
| **PDF** | `pdf_reader_mcp_server.py` | PDF 文档读取 |
| **PowerPoint** | `ppt_wincom_mcp_server.py` | PPT COM 自动化 |
| **UI** | `ui_mcp_server.py` | UI 控件操作 |
| **Word** | `word_wincom_mcp_server.py` | Word COM 自动化 |

### ✅ HTTP MCP 服务器（3 个，跨设备用）

| 服务器 | 文件 | 功能 |
|--------|------|------|
| **Hardware** | `hardware_mcp_server.py` | 硬件设备控制 |
| **Linux** | `linux_mcp_server.py` | Linux 设备 Agent |
| **Mobile** | `mobile_mcp_server.py` | 移动设备 Agent |

### ⚠️ 边界

| 限制 | 说明 |
|------|------|
| **运行时依赖** | MCP 服务器需先启动才能使用；mcp.yaml 配置了自动启动 |
| **失败回退** | MCP 执行失败时可回退到 GUI 自动化（`MCP_FALLBACK_TO_UI: True`） |
| **超时控制** | `MCP_TOOL_TIMEOUT: 30` 秒，长操作可能超时 |
| **Office MCP** | Excel/Word/PPT 的 MCP 服务器依赖对应 Office 应用已安装且运行 |

---

## 七、Office 自动化能力

### ✅ 可用工具

| 工具 | 用途 | 状态 |
|------|------|------|
| **xlwings** | Excel 单元格/图表直接操作 | ✅ 已安装 |
| **python-pptx** | PowerPoint 幻灯片编辑 | ✅ 已安装 |
| **win32com** | Outlook/Word/Excel COM 自动化 | ✅ 已安装 |
| **MCP Office 服务器** | Excel/Word/PPT 的 MCP 集成 | ✅ 代码可用 |

### ⚠️ 边界

| 限制 | 说明 |
|------|------|
| **Office 未安装** | 若本机无 Microsoft Office，COM 自动化和 xlwings 不可用，只能 GUI 级操作 |
| **xlwings 要求** | 需要 Excel 进程运行中，否则会自动启动 Excel |
| **python-pptx** | 不需要 PowerPoint 安装即可创建/修改 .pptx 文件 |
| **WPS 兼容性** | WPS Office 的 COM 接口与 Microsoft Office 有差异，可能不完全兼容 |

---

## 八、LLM 集成能力

### ✅ 支持的 8 个 LLM 提供商

| 提供商 | API_TYPE | 说明 |
|--------|----------|------|
| **OpenAI** | `openai` | GPT-4o / GPT-4 / GPT-3.5 |
| **Azure OpenAI** | `aoai` | Azure 托管的 OpenAI 模型 |
| **Azure AD** | `azure_ad` | Azure AD 认证方式 |
| **Google Gemini** | `gemini` | Gemini Pro / Flash |
| **Qwen** | `qwen` | 通义千问（本地或 API） |
| **Ollama** | `ollama` | 本地模型托管（免费） |
| **Anthropic Claude** | `anthropic` | Claude 3.5 / 3 |
| **DeepSeek** | `deepseek` | DeepSeek 模型 |

### ⚠️ 当前状态

- **API Key 未配置**：`agents.yaml` 中 `API_KEY` 仍为模板值，LLM 调用将失败
- **默认模型**：GPT-4o（需 OpenAI API Key）
- **视觉模式**：`VISUAL_MODE: True`，需要视觉能力模型

### ⚠️ 边界

| 限制 | 说明 |
|------|------|
| **视觉模型必需** | VISUAL_MODE=True 需要视觉模型（GPT-4o/Gemini Pro Vision 等） |
| **非视觉模式降级** | VISUAL_MODE=False 可用纯文本模型，但 GUI 自动化能力大幅下降 |
| **每步延迟** | 每步需 1+ 次 LLM 调用，典型延迟 2-10 秒/步 |
| **成本** | GPT-4o 约 $0.005-0.01/步；本地模型免费但更慢 |
| **最大步数** | MAX_STEP=50，复杂任务可能触及上限 |
| **截图隐私** | LLM 接收屏幕截图，可能含敏感数据（密码、个人信息） |

---

## 九、安全护栏机制

### ✅ 已启用

| 机制 | 配置值 | 说明 |
|------|--------|------|
| **SafeGuard** | `True` | 防止对非白名单控件的操作 |
| **控件白名单** | 15 种类型 | Button/Edit/TabItem/Document/ListItem/MenuItem/ScrollBar/TreeItem/Hyperlink/ComboBox/RadioButton/Spinner/CheckBox/Group/Text |
| **最大步数限制** | 50 步 | 防止无限循环 |
| **最大重试** | 20 次 | 防止重复失败 |

### ❌ 安全边界

| 限制 | 说明 |
|------|------|
| **无法绕过 UAC** | UAC 提示在安全桌面，所有自动化被完全阻断 |
| **继承调用者权限** | UFO 以启动者的权限运行，非管理员启动则无法操作管理员窗口 |
| **凭证暴露风险** | 屏幕截图发送到 LLM 提供商，可能泄露密码等敏感信息 |
| **文件系统间接访问** | UIA 不能直接修改文件，需通过 MCP/API 或 GUI 操作 |

---

## 十、RAG 知识基底

### ✅ 可用

| 组件 | 状态 | 说明 |
|------|------|------|
| **FAISS 向量索引** | ✅ | 已安装，可创建索引 |
| **HuggingFace Embeddings** | ✅ | 可导入 |
| **LangChain FAISS** | ✅ | 可导入 |
| **Sentence Transformers** | ✅ | 可导入 |
| **RAG 配置** | ✅ | `config/ufo/rag.yaml` 存在 |

### ⚠️ 边界

| 限制 | 说明 |
|------|------|
| **首次下载** | 首次运行需下载嵌入模型（~100MB） |
| **3 种知识源** | 帮助文档、演示轨迹、执行经验 |
| **范围有限** | RAG 仅增强应用特定知识，不改善通用 OS 交互 |
| **知识时效** | 知识在会话内静态，新经验在任务完成后保存 |

---

## 十一、Agent 架构

### ✅ 模块结构

| 模块 | 子模块 | 说明 |
|------|--------|------|
| **agents/** | agent/, memory/, presenters/, processors/, states/ | Agent 核心实现 |
| **7 种处理策略** | app/host/customized/linux/mobile/processing/strategy_dependency | 可扩展策略模式 |
| **7 种状态模块** | app_agent/host_agent/evaluation/linux/mobile/operator/basic | FSM 状态管理 |

### ⚠️ 边界

| 限制 | 说明 |
|------|------|
| **层级架构** | HostAgent（桌面级编排）→ AppAgent（应用级执行），两层 |
| **顺序协调** | 一个 AppAgent 对应一个应用；HostAgent 顺序协调多个 AppAgent |
| **自定义 Agent** | 通过 third_party 配置和 processor strategy 扩展 |

---

## 十二、画中画（PiP）桌面

### ✅ 基础条件

| 条件 | 状态 |
|------|------|
| **mstsc.exe** | ✅ 存在 |
| **Win32 API** | ✅ 可用 |

### ⚠️ 边界

| 限制 | 说明 |
|------|------|
| **需启用 RDP** | PiP 使用 RDP 环回（连接 localhost），需系统启用远程桌面 |
| **Windows 版本限制** | Windows Pro/Enterprise 支持 RDP 服务端；**Windows Home 不支持** |
| **额外资源** | 虚拟桌面会话占用 ~200-500MB RAM + GPU |
| **非即插即用** | 需额外配置，不是开箱即用功能 |

---

## 十三、特殊场景能力矩阵

| 场景 | 窗口检测 | 控件检测 | 操作能力 | 说明 |
|------|---------|---------|---------|------|
| **Win32 原生应用** | ✅ 完整 | ✅ 完整 | ✅ 完整 | 最佳支持（记事本/画图/资源管理器等） |
| **Windows Forms/WPF** | ✅ 完整 | ✅ 完整 | ✅ 完整 | UIA 支持良好 |
| **UWP 应用** | ✅ 良好 | ✅ 良好 | ✅ 良好 | ApplicationFrame 窗口，需特殊处理 |
| **Microsoft Office** | ✅ 完整 | ✅ 完整 | ✅ API+GUI | 混合执行，API 优先 |
| **WPS Office** | ✅ 可检测 | ⚠️ 有限 | ⚠️ 仅 GUI | COM 接口可能不兼容 |
| **Electron 应用** | ✅ 可检测 | ⚠️ 浅层 | ⚠️ 视觉为主 | VS Code/Discord/Slack 等 |
| **浏览器内容** | ✅ 框架 | ⚠️ 地址栏/标签 | ⚠️ 有限 | 网页 DOM 需其他方案 |
| **控制台/终端** | ✅ 可检测 | ⚠️ 文本区 | ⚠️ 有限 | cmd/PowerShell，UIA 支持有限 |
| **DirectX 游戏** | ✅ 窗口 | ❌ 无控件 | ❌ 不可靠 | 无 UIA 控件，视觉检测精度低 |
| **VM 控制台** | ✅ 窗口 | ❌ 仅框架 | ❌ 不可穿透 | 只能操控宿主窗口框架 |
| **RDP 客户端** | ✅ 窗口 | ❌ 仅框架 | ❌ 不可穿透 | 同 VM 控制台 |
| **UAC 安全桌面** | ❌ 不可见 | ❌ 不可见 | ❌ 完全阻断 | 安全桌面隔离 |
| **锁屏界面** | ❌ 不可见 | ❌ 不可见 | ❌ 完全阻断 | 锁定状态无法操作 |
| **Toast 通知** | ⚠️ 瞬态 | ⚠️ 瞬态 | ⚠️ 可能错过 | 通知消失太快 |
| **最小化窗口** | ✅ 可检测 | ⚠️ 不完整 | ⚠️ 需先恢复 | UIA 树可能为空 |
| **系统托盘** | ✅ 可检测 | ⚠️ 有限 | ⚠️ 有限 | 托盘图标操作受限 |

---

## 十四、硬性边界总结（绝对做不到）

1. **UAC 安全桌面**：无法绕过、无法截图、无法交互
2. **锁屏状态**：无法截图、无法交互
3. **DirectX/OpenGL 游戏内部**：无 UIA 控件，无法可靠操作
4. **VM/RDP 远程内容穿透**：只能操控本地窗口框架
5. **跨用户会话**：无法访问其他登录会话的窗口
6. **非活动虚拟桌面**：只能看到当前活动桌面的窗口
7. **Windows Home 版 PiP**：Home 版不支持 RDP 服务端，PiP 不可用

---

## 十五、待配置项

| 项目 | 当前状态 | 影响 |
|------|---------|------|
| **LLM API Key** | ❌ 未配置 | **UFO 无法执行任何智能任务** |
| **OmniParser 端点** | ⚠️ 默认公共地址 | 混合检测不稳定，建议自部署 |
| **RDP 服务** | 未验证 | PiP 功能不可用 |
| **Office 应用** | 未验证 | Office MCP/API 自动化不可用 |

---

*文档生成自 104 项自动化边界测试，测试脚本：`D:\UFO\test_boundary_v2.py`，原始数据：`D:\UFO\test_results_v2.json`*
