# SESSION_CONTEXT — 广西政务平台协议化登记 全量上下文恢复

> **用法**：新对话里说 **"读 docs/SESSION_CONTEXT.md"** 即可恢复全部上下文。
>
> **最后更新**：2026-04-24 20:00（Cascade 整理）

---

## 〇、项目一句话

把广西经营主体登记平台（`zhjg.scjdglj.gxzf.gov.cn:9087` / `icpsp-api`）的**企业设立登记**全流程，从"浏览器人工点击填表"转成**纯 HTTP 协议调用**，封装为 FastAPI 服务。

---

## 一、里程碑总览

| 线路 | 企业类型 | entType | 状态 | 说明 |
|------|---------|---------|------|------|
| **A 线** | 个人独资企业 | 4540 | ✅ **PreSubmitSuccess 云提交停点达标** | 25 步全通，status=90 |
| **B 线** | 有限责任公司（自然人独资） | 1151 | ⏸️ ~30% | 卡在 BenefitUsers iframe + MemberPost A0002 |

### A 线达标证据（2026-04-24）
- `POST /api/phase2/register` → `success=True, stopped_at_step=25, code=00000`
- `flowData.status=90, currCompUrl=PreSubmitSuccess`
- busiId: `2047122548757872642`, nameId: `2047094115971878913`
- 案例: 有为风（广西容县）软件开发中心（个人独资）, 投资人: 黄永裕
- 完整响应: `dashboard/data/records/api_verify_yun_submit.json`

### B 线进度（1151 有限公司）
- 企业: 泽昕（广西容县）科技有限公司, 法人: 黄永裕
- busiId: `2047225160991752194` (status=90 已提交，不可续跑)
- nameId: `2047218022607474690`
- 已过组件: NameInfoDisplay → BasicInfo → MemberPost → MemberPool → ComplementInfo ✅ → Rules(当前)
- 28 步驱动器: `get_steps_spec("1151")` → 28 步（vs 4540 的 25 步）
- step19 三级策略: 纯协议 → HTTP BenefitCallback → CDP 驱动 syr iframe
- CDP 模块: `system/cdp_benefit_users.py`

---

## 二、项目结构

```
D:\UFO\政务平台\
├── system/                          # 核心协议驱动 & 基础设施
│   ├── phase1_protocol_driver.py    # Phase 1 纯协议驱动器（7 步）
│   ├── phase2_protocol_driver.py    # Phase 2 纯协议驱动器（25/28 步）
│   ├── phase2_constants.py          # 常量中心：魔数/API路径/过滤表/错误码
│   ├── phase2_bodies.py             # 6 个 body 构造器
│   ├── phase2_enums.py              # 枚举字段字典（业务语言→code）
│   ├── icpsp_api_client.py          # HTTP 客户端（Auth 自动刷、session cookie 同步）
│   ├── icpsp_crypto.py              # RSA / AES 加密
│   ├── session_bootstrap_cdp.py     # CDP 浏览器会话同步
│   ├── login_qrcode.py              # 扫码登录
│   ├── cdp_benefit_users.py         # CDP BenefitUsers 模块（1151 专用）
│   ├── cdp_attachment_upload.py     # 文件上传 CDP 辅助
│   ├── packet_chain_portal_from_start.py  # 108KB 浏览器 UI 自动化主链路
│   └── _archive/                    # 500+ 探索脚本归档
├── phase1_service/                  # FastAPI 服务
│   ├── api/main.py                  # 入口
│   ├── api/routers/                 # 路由（auth, phase2_register, matters, dictionaries...）
│   ├── api/core/                    # 核心（phase2_adapter, session_recovery, idempotency...）
│   └── api/schemas/                 # Pydantic 模型
├── docs/                            # 技术文档（29 篇 MD）
├── dashboard/data/records/          # mitm 样本 + 运行留痕 + 字典缓存
├── schemas/                         # BasicInfo/BDI 字段 schema
├── config/                          # 浏览器/凭证/素材配置
├── .venv-portal/                    # Python 虚拟环境
└── pyproject.toml                   # 项目元数据
```

---

## 三、FastAPI 服务（27 个端点）

**启动**:
```powershell
.\.venv-portal\Scripts\python.exe -m uvicorn phase1_service.api.main:app --host 127.0.0.1 --port 8800
```

### 关键端点

| 路由 | 方法 | 用途 |
|------|------|------|
| `/api/auth/token/ensure` | POST | 智能获取 token |
| `/api/auth/qr/start` | POST | 生成二维码 |
| `/api/auth/qr/status?sid=X` | GET | 轮询扫码状态 |
| `/api/phase1/register` | POST | Phase 1 七步核名 → busiId |
| `/api/phase2/register` | POST | **Phase 2 协议链**（stop_after=1~25/28） |
| `/api/phase2/session/recover` | POST | CDP → Python session 同步 |
| `/api/phase2/progress?busi_id&name_id` | GET | 查询办件当前位置 |
| `/api/matters/list` | GET | 我的办件列表 |
| `/api/phase1/dict/*` | GET | 字典（企业类型/行业/区划） |
| `/api/system/sysparam/snapshot` | GET | sysParam 快照（aesKey/RSA 公钥） |
| `/api/debug/mitm/*` | GET | mitm 样本查询 |

完整清单: `docs/API调用手册_Phase1_Phase2.md`

---

## 四、Phase 2 驱动器 25 步全景（4540 个人独资 A 线）

| 步 | 组件 | 类型 | 关键点 |
|----|------|------|--------|
| 1-9 | Phase 1 后半段 | load/save | NameSupplement → NameShareholder → submit → NameSuccess |
| 10-11 | matters/operate [108] | save | before → operate，切换到 establish domain |
| 12 | loadCurrentLocationInfo | load | 定位 establish 首页 |
| 13 | YbbSelect load | load | 可选，D0021 可忽略 |
| 14 | BasicInfo load | load | 捕获 busiData 模板 + dynamic signInfo |
| **15** | **BasicInfo save** | save | 42-key body，创建 establish busiId |
| 16 | MemberPost save | save | board=0, boardSup=0, pkAndMem 四角色 |
| 17 | MemberPool list load | load | 捕获 raw_member |
| 18 | MemberInfo save | save | politicsVisage="13" + isOrgan="02" |
| 19 | ComplementInfo save | save | 空体推进 |
| 20 | TaxInvoice save | save | 空体推进 |
| 21 | SlUploadMaterial | 三步法 | upload → special(cerno 小写) → save |
| 22 | BusinessLicenceWay save | save | 空体推进 |
| 23 | YbbSelect save | save | isSelectYbb="0" |
| 24 | PreElectronicDoc save | save | 空体推进 |
| **25** | **PreSubmitSuccess load** | load | **终点** status=90 |

**1151 有限公司 B 线**额外步骤: step 16-28（MemberPost/MemberPool/ComplementInfo+BenefitUsers/Rules/BankOpenInfo/MedicalInsured/Engraving/SocialInsured/GjjHandle 等）

---

## 五、铁律清单（刻在墙上）

### 铁律 1：signInfo 魔数按域切换
```python
SIGN_INFO_NAME       = -252238669   # Phase 1（NameCheckInfo/NameSupplement/NameShareholder）
SIGN_INFO_ESTABLISH  = -1607173598  # Phase 2 establish（BasicInfo/MemberPost/MemberInfo/...）
```

### 铁律 2：字段名大小写字符级匹配
```python
cerno   # ✅ SlUploadMaterial 小写 n（Jackson 严格匹配）
cerNo   # ❌ 大写 N → null → NPE → A0002
```

### 铁律 3：Phase 2 establish busiId 两态
- **初次创建**: `flowData.busiId=null`，BasicInfo save 后服务端分配
- **断点续跑**: 用已知的 establish busiId

### 铁律 4：load 响应元数据必须剥离
- `entDomicileDto` 有 190+ 元数据字段，整体回传 → A0002
- 过滤表: `phase2_constants.BASICINFO_META_STRIP`

### 铁律 5：BasicInfo 两次 save
- 第 1 次 `continueFlag=null` → `resultType=2`（警告）
- 第 2 次 `continueFlag="continueFlag"` → `resultType=0`（成功）
- 项目默认一律传 `continueFlag="continueFlag"` 跳过

### 铁律 6：前端自动推进
- save 成功(resultType=0) → 服务端自动迁移到下一组件
- 协议化只需连续 save，不需要手动 load 中间组件

### 铁律 7：攻克过的别重跑
> 先读 MD 文档 → 找到现有 busiId → 断点续传 → 比从头打省 10 倍时间

---

## 六、常见错误码速查

| code | 含义 | 解法 |
|------|------|------|
| `00000` | 成功 | — |
| `GS52010103E0302` | session 过期 | `POST /api/phase2/session/recover` |
| `D0018` | 业务状态已变化 | 步骤可能已完成过 |
| `D0021` | 越权（上下文错误） | step 13 YbbSelect 返回正常，可跳过 |
| `D0022` | 越权（三层洋葱） | 检查 headers/body/signInfo |
| `D0029` | 操作频繁 | 等 5-10 分钟 |
| `A0002` | 服务端异常 | 检查字段大小写、JSON 结构 |

---

## 七、核心模块签名速查

### Body 构造器 (`system/phase2_bodies.py`)
```python
build_basicinfo_save_body(case, base, ent_type, name_id)        # 42 keys
build_memberpost_save_body(case, ent_type, name_id, busi_id)    # 8 keys
build_memberinfo_save_body(case, raw_member, ent_type, name_id, busi_id, item_id)
build_empty_advance_save_body(comp_url, ent_type, name_id, busi_id, parents)
build_ybb_select_save_body(case, ent_type, name_id, busi_id)
build_sl_upload_special_body(file_id, mat_code, mat_name, ent_type, name_id, busi_id)
```

### API 路径工厂 (`system/phase2_constants.py`)
```python
establish_comp_load("BasicInfo")   # .../BasicInfo/loadBusinessDataInfo
establish_comp_op("MemberPost")    # .../MemberPost/operationBusinessDataInfo
establish_comp_list("MemberPool")  # .../MemberPool/loadBusinessInfoList
busi_comp_url_paths(None)          # "%5B%5D" (顶层)
busi_comp_url_paths(["MemberPool"])# URL-encoded (池内)
```

### 驱动器入口
```python
# 4540: 25 步; 1151: 28 步
get_steps_spec(ent_type)  # → steps 1~25 or 1~28
```

---

## 八、Case 模板 & 数据样本

### Case 文件
| 文件 | 用途 |
|------|------|
| `docs/case_有为风.json` | 4540 个人独资 **主用 case**（已验证到 PreSubmitSuccess） |
| `docs/case_有限公司1151_普查.json` | 1151 有限公司 case |
| `docs/case_广西容县李陈梦.json` | 李陈梦 个人独资 测试 |

### Ground-truth mitm 样本
| 文件 | 说明 |
|------|------|
| `dashboard/data/records/establish_save_samples/BasicInfo__save.json` | 42 keys 真实 body |
| `dashboard/data/records/establish_save_samples/MemberPost__save.json` | 8 keys |
| `dashboard/data/records/establish_save_samples/MemberBaseInfo__save.json` | 48 keys |
| `dashboard/data/records/mitm_ufo_flows.jsonl` | 5.7 MB 全量抓包 |
| `dashboard/data/records/phase2_samples.json` | 140 KB 核心 API 样本 |

---

## 九、环境 & 浏览器

### 浏览器启动（Edge + CDP 9225）
```powershell
Start-Process "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" -ArgumentList @(
  "--remote-debugging-port=9225",
  "--remote-allow-origins=*",
  "--user-data-dir=C:\Temp\EdgeCDP9225",
  "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"
)
# 窗口里扫二维码登录（约 30 秒）
```

### Session 恢复
```powershell
curl -X POST http://127.0.0.1:8800/api/phase2/session/recover
```

### SESSION cookie 域名
- `zhjg.scjdglj.gxzf.gov.cn`（无端口）
- 必须用 `Network.getAllCookies` 获取（getCookies URL 过滤有 bug）

---

## 十、端到端复现

### 全新 case 一条龙
```powershell
# 1. 同步 session
curl -X POST http://127.0.0.1:8800/api/phase2/session/recover

# 2. 25 步全跑
$body = @{
  case = (Get-Content 'docs\case_有为风.json' -Raw | ConvertFrom-Json)
  stop_after = 25; auto_phase1 = $true
} | ConvertTo-Json -Depth 20 -Compress
curl -X POST http://127.0.0.1:8800/api/phase2/register -H "Content-Type: application/json" -d $body
```

### 断点续跑（已有 busiId）
```powershell
$body = @{
  case = (Get-Content 'docs\case_有为风.json' -Raw | ConvertFrom-Json)
  busi_id = "2047122548757872642"; name_id = "2047094115971878913"
  start_from = 25; stop_after = 25; auto_phase1 = $false
} | ConvertTo-Json -Depth 20 -Compress
curl -X POST http://127.0.0.1:8800/api/phase2/register -H "Content-Type: application/json" -d $body
```

### 调试单步
```powershell
# 只到 BasicInfo save
curl ... -d '{"case": {...}, "stop_after": 15}'
# 从 step 16 续
curl ... -d '{"case": {...}, "start_from": 16, "stop_after": 25}'
```

---

## 十一、matters/operate 操作备忘

### 继续办理 (btnCode=108)
1. `POST matters/operate` → `{busiId, btnCode:"108", dealFlag:"before"}` → resultType=2
2. `POST matters/operate` → `{busiId, btnCode:"108", dealFlag:"operate"}` → resultType=0

### 删除办件 (btnCode=103)
1. `POST matters/operate` → `{busiId, btnCode:"103", dealFlag:"before"}` → "此操作将永久删除"
2. `POST matters/operate` → `{busiId, btnCode:"103", dealFlag:"operate"}` → "删除成功"
- ⚠️ `dealFlag` 第二步是 `"operate"` 不是 `"after"`！

---

## 十二、1151 B 线专有知识

### 组件差异（vs 4540）
- 1151 多: MemberPost, MemberPool, Rules, BankOpenInfo, MedicalInsured, Engraving, SocialInsured, GjjHandle
- 4540 多: PersonInfoRegGT（投资人信息）
- busiType: 1151→`02_4`（不是 02_1！）

### MemberPost A0002 根因
- BasicInfo save 用 4540 模板构建 1151 记录 → 服务端内部状态不一致 → pkAndMem 非空时 A0002
- 修复方向: 用 1151 原生 load 数据构建 BasicInfo save body

### ComplementInfo BenefitUsers 完整流程
1. 打开 benefit-users dialog → 等待 syr iframe
2. 连接 syr iframe CDP target
3. 选承诺免报(03) → handleClickNext() → POST dataAdd.do
4. 确认弹窗 → rePro.do → BenefitCallback
5. patch flowData.currCompUrl 从 "BenefitUsers" → "ComplementInfo"
6. fc.save() → resultType=0 ✅

### 成员角色代码
GD01=股东, DS01=董事, JS01=监事, CWFZR=财务负责人, FR01=法定代表人, LLY=联络员, WTDLR=委托代理人

---

## 十三、前端路径（2025-06 confirmed）

```
新 portal: /icpsp-web-pc/ (SPA入口, hash路由)
新 core:   /icpsp-web-pc/core.html#/flow/base?busiId=xxx&busiType=02_4&entType=1151&nameId=xxx
继续办理:  window.open("/core.html#/flow/base?fromProject=portal&busiId=xxx&...", "_blank")
establish 入口 URL 必须含 visaFree=true，否则 SPA 不初始化
```

---

## 十四、边界声明（不可协议化）

| 项 | 原因 |
|---|------|
| 电子签章 ElectronicDoc | 需真实 CA U-key 硬件 |
| SSO 首次扫码 | 政府强制二维码 |
| 真正云提交（status=90 之后） | 用户明确不点 |
| 跨案例通用性 | 仅 case_有为风.json 真实验证过 |

---

## 十五、文档索引（按重要性）

| 优先级 | 文件 | 用途 |
|--------|------|------|
| ⭐⭐⭐ | `docs/SESSION_CONTEXT.md` | **本文（上下文恢复入口）** |
| ⭐⭐⭐ | `docs/协议化登记_资产与框架总览.md` | 顶层资产总览 |
| ⭐⭐⭐ | `docs/API调用手册_Phase1_Phase2.md` | API 一站式使用说明 |
| ⭐⭐⭐ | `docs/Phase2_云提交停点达标_20260424.md` | A 线达标纪要 |
| ⭐⭐ | `docs/Phase2_纯协议25步固化_20260424.md` | 25 步驱动器详细 |
| ⭐⭐ | `docs/Phase2_STATUS.md` | 第一日晚间续传指南 |
| ⭐⭐ | `docs/Phase2_1151_component_schema.md` | 1151 组件差异矩阵 |
| ⭐⭐ | `docs/突破D0022越权_协议层字段合同方法论_20260422.md` | D0022 三层洋葱 |
| ⭐ | `docs/Phase2_阶段总结_20260423.md` | 第一日 17 步突破 |
| ⭐ | `docs/Phase2枚举字段字典_20260424.md` | 业务语言→编码 |
| ⭐ | `docs/Phase2_开发记录.md` | 第一日 Phase 2 开发过程 |
| ⭐ | `docs/Phase2_1151_工作交接_20260423.md` | B 线交接 |
| ⭐ | `docs/SSO自动登录技术经验.md` | 登录技术 |
| ⭐ | `docs/实网开发操作纪律_单步与风控.md` | 逆向纪律 |

---

## 十六、核心教训

1. **"永远先读已有的 MD，再开始写新代码。"** — 花 1 小时打新 busiId 的 A0002，回头一看昨天 busiId 早已 status=90
2. **样本即真理** — 遇到 A0002 不要猜，diff mitm 实录逐字段排查
3. **两个 signInfo 魔数按域取** — Phase 1 ≠ Phase 2
4. **cerno 小写** — 一个字符大小写差异导致半天卡壳
5. **session 域名无端口** — cookie 过滤要用 `Network.getAllCookies`
6. **断点续传优于从头打通** — 已有 busiId 直接跳到断点步

---

_生成时间：2026-04-24 20:00 by Cascade_
_工作区：D:\UFO\政务平台_
