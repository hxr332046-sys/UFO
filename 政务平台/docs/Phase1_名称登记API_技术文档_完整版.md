# Phase 1 名称登记 API — 完整技术文档

> 版本 1.0 | 2026-04-22 | 基于广西经营主体登记平台实网逆向

---

## 一、系统总览

### 1.1 架构设计

```
  ┌──────────────┐     ┌──────────────────────┐     ┌───────────────┐
  │  LLM / CLI   │────→│  Phase1 Service API  │────→│  ICPSP 实网   │
  │  (调用方)     │←────│  (FastAPI :8800)      │←────│  (:9087)      │
  └──────────────┘     └──────────────────────┘     └───────────────┘
                              │
                              ▼
                       ┌──────────────┐
                       │  本地字典缓存  │
                       │  (JSON 文件)  │
                       └──────────────┘
```

**核心理念：Browser Distillation（浏览器蒸馏）**
- 浏览器只保留登录态获取（Authorization 32-hex 令牌）
- 所有业务逻辑全部搬到 Python 纯协议驱动
- 完全不依赖 CDP / Vue / Selenium / Puppeteer

### 1.2 目录结构

```
phase1_service/
├── api/
│   ├── main.py                    # FastAPI 入口
│   ├── core/
│   │   ├── auth_manager.py        # Authorization 管理
│   │   ├── banned_words_loader.py # 禁用词加载器（500+ 词）
│   │   ├── errors.py              # Phase1Error 枚举（12 种）
│   │   ├── idempotency.py         # 幂等缓存（30min TTL）
│   │   ├── rsa_encrypt.py         # RSA PKCS#1 v1.5 加密
│   │   └── supplement_driver.py   # NameSupplement 协议构造
│   ├── routers/
│   │   ├── registration.py        # POST /register
│   │   ├── supplement.py          # POST /supplement
│   │   ├── precheck.py            # POST /precheck_name
│   │   ├── dictionaries.py        # GET /dict/*
│   │   ├── business_scope.py      # GET /scope
│   │   └── auth.py                # GET /auth/status
│   └── schemas/
│       ├── case.py                # Phase1Case, RegisterRequest
│       └── response.py           # RegisterResponse, StepReport
├── cli.py                         # CLI 入口（LLM 命令行模式）
├── data/
│   ├── banned_words.json          # 禁用词库（8 类 500+ 词）
│   └── dictionaries/              # 本地字典缓存（8.17 MB）
│       ├── ent_types_type1.json   # 企业类型（11 种）
│       ├── industries/            # 行业码（10 种 entType × 1765 码）
│       ├── organizes/             # 组织形式（10 种 entType）
│       ├── regions/               # 行政区划树（广西全区划）
│       ├── business_scopes/       # 经营范围（36,349+ 条）
│       └── sys_params.json        # 系统参数（含 RSA 公钥）
└── PROGRESS.md                    # 进度追踪
```

---

## 二、API 端点详情（10 个）

### 2.1 POST /api/phase1/register — 名称检查（7 步协议链）

**功能**：执行完整的名称登记 Step 1，成功返回 busiId

**请求体**：
```json
{
  "case": {
    "name_mark": "李陈梦",
    "phase1_name_pre": "广西容县",
    "phase1_industry_code": "6513",
    "phase1_industry_name": "应用软件开发",
    "phase1_industry_special": "软件开发",
    "phase1_organize": "中心（个人独资）",
    "phase1_dist_codes": ["450000", "450900", "450921"],
    "entType_default": "4540"
  },
  "authorization": "5d9a882049314cee8819bbbb5d1e3759"
}
```

**7 步协议链详解**：

| 步骤 | API 路径 | 功能 | 关键字段 |
|------|---------|------|---------|
| 1 | `checkEstablishName` | 校验企业类型+区划可用性 | `entType, distCode, distCodeArr` |
| 2 | `loadCurrentLocationInfo` | 初始化 busiId 和会话 | `flowData={busiType,entType}`, `linkData={token:""}` |
| 3 | `NameCheckInfo/loadBusinessDataInfo` | 加载名称检查表单 | 必须含 `itemId: ""` |
| 4 | `bannedLexiconCalibration` | 远端禁限词校验 | `name=fullName` |
| 5 | `NameCheckInfo/operationBusinessDataInfo#first` | 首次保存（获取字段绑定） | `signInfo=-252238669` |
| 6 | `NameCheckInfo/nameCheckRepeat` | 名称查重 | 返回 `checkResult[]`, `checkState` |
| 7 | `NameCheckInfo/operationBusinessDataInfo#second` | 二次保存（附查重结果→拿busiId） | `afterNameCheckSign:"Y"` + `nameCheckDTO` |

**成功响应**：
```json
{
  "success": true,
  "busi_id": "2046839649770536960",
  "steps": [
    {"name": "step1_checkEstablishName", "ok": true, "code": "00000", "duration_ms": 420},
    {"name": "step2_loadCurrentLocationInfo", "ok": true, "code": "00000", "duration_ms": 380},
    {"name": "step3_loadBusinessDataInfo", "ok": true, "code": "00000", "duration_ms": 320},
    {"name": "step4_bannedLexiconCalibration", "ok": true, "code": "00000", "duration_ms": 250},
    {"name": "step5_operationBDI_first", "ok": true, "code": "00000", "duration_ms": 480},
    {"name": "step6_nameCheckRepeat", "ok": true, "code": "00000", "duration_ms": 3200},
    {"name": "step7_operationBDI_second", "ok": true, "code": "00000", "duration_ms": 520}
  ],
  "similar_names": [
    {"entName": "容县李陈梦食品店", "status": "存续", "regionName": "容县"}
  ],
  "hit_count": 6,
  "check_state": 4,
  "error_code": null,
  "reason": null,
  "cached": false,
  "latency_ms": 7800
}
```

**失败响应**：
```json
{
  "success": false,
  "busi_id": null,
  "error_code": "name_restricted",
  "reason": "字号'美美的'含驰名商标'美的'",
  "reason_detail": "bannedLexiconCalibration: resultType=2",
  "steps": [...],
  "cached": false,
  "latency_ms": 1200
}
```

### 2.2 POST /api/phase1/supplement — 信息补充 + 提交（Step 2+3）

**前置条件**：`busi_id`（来自 register 成功返回）

**请求体**：
```json
{
  "busi_id": "2046839649770536960",
  "ent_name": "李陈梦（广西容县）软件开发中心（个人独资）",
  "ent_type": "4540",
  "dist_code": "450921",
  "dist_codes": ["450000", "450900", "450921"],
  "address": "广西壮族自治区玉林市容县",
  "industry_code": "6513",
  "industry_name": "应用软件开发",
  "busi_area_items": [
    {
      "id": "I3006",
      "name": "软件开发",
      "stateCo": "3",
      "pid": "65",
      "minIndusTypeCode": "6511;6512;6513",
      "isMainIndustry": "1",
      "category": "I"
    }
  ],
  "busi_area_code": "I3006",
  "busi_area_name": "软件开发",
  "gen_busi_area": "软件开发",
  "org_id": "145090000000000046",
  "org_name": "容西市监所",
  "register_capital": "5",
  "agent": {
    "name": "黄永裕",
    "cert_type": "10",
    "cert_no": "450921198812051251",
    "mobile": "18977514335"
  },
  "auto_submit": true
}
```

**协议链**：

| 步骤 | API | 功能 | 关键 |
|------|-----|------|------|
| 8 | `NameSupplement/operationBusinessDataInfo` | 保存信息补充 | RSA 加密经营范围和身份信息 |
| 9 | `/name/submit` | 正式提交 | status 10→20 |
| 10 | `NameSuccess/loadBusinessDataInfo` | 验证成功 | status 20→51, 分配 nameId |

**RSA 加密字段**：
- `busiAreaName` — 经营范围名称
- `businessArea` — 经营范围文本
- `busiAreaData` — 经营范围条目 JSON
- `agent.certificateNo` — 身份证号
- `agent.mobile` — 手机号

公钥来源：`sys_params.json → numberEncryptPublicKey`（RSA 1024-bit PKCS#1 v1.5）

### 2.3 POST /api/phase1/precheck_name — 名字预检

**功能**：0ms 本地禁用词检查 + 可选远程校验

```json
// 请求
{"name_mark": "美美的", "remote": false}

// 响应
{
  "name_mark": "美美的",
  "verdict": "restricted",
  "local_matched": ["美的"],
  "local_category": "restricted",
  "remote_checked": false,
  "latency_ms": 0
}
```

**判定等级**：
- `ok` — 通过
- `restricted` — 含限制词（不短路，但建议换）
- `prohibited` — 含禁止词（短路拒绝）
- `region_name` — 含地名冲突

### 2.4 GET /api/phase1/auth/status — 认证状态

```json
{"valid": true, "token_preview": "5d9a8820...", "remote_ok": null}
```

### 2.5-2.9 字典端点

| 端点 | 数据量 | 用途 |
|------|-------|------|
| `GET /dict/ent-types?level=1` | 11 种 | LLM 选企业类型 |
| `GET /dict/industries/{entType}` | 1,765 码 | LLM 选行业 |
| `GET /dict/organizes/{entType}` | ~20-50 种/类型 | LLM 选组织形式 |
| `GET /dict/regions` | 广西全区划树 | LLM 选区划 |
| `GET /scope?entType=&keyword=` | 36,349 条 | LLM 选经营范围 |

---

## 三、协议层关键约束（D0022/D0029 避坑）

### 3.1 必带浏览器指纹头组

```python
_BROWSER_LIKE_HEADERS = {
    "sec-ch-ua": '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "User-Agent": "Mozilla/5.0 ... Edg/131.0.0.0",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
```
**缺任何一个 → D0022**

### 3.2 signInfo 魔数

```python
signInfo = -252238669  # 固定值，4 份抓包样本全一致
```
**用 Java hashCode 动态算 → D0022**

### 3.3 body 精简约束

| 步骤 | 约束 | 违反后果 |
|------|------|---------|
| Step 2 loadCurrentLocationInfo | `flowData={busiId,busiType,entType}` + `linkData={token:""}` 仅此两项 | 多 extraDto/vipChannel → D0022 |
| Step 3 loadBusinessDataInfo | 必须含顶层 `itemId: ""` | 漏 itemId → 组件实例未绑定 |
| Step 7 operationBDI#second | 必须 `afterNameCheckSign:"Y"` + `nameCheckDTO={checkResult,checkState}` | 缺失 → resultType=2，不分配 busiId |

### 3.4 错误码词典

| 错误码 | 含义 | 处理策略 |
|--------|------|---------|
| `GS52010103E0302` | 未认证 | 重新获取 Authorization |
| `D0022` | 越权访问（body/头/signInfo） | 检查请求格式 |
| `D0029` | 操作频繁 | 等待 5-10 分钟冷却 |
| `A0002` | 参数异常 | 检查 busiAreaData 格式 |

### 3.5 步间节流

```python
time.sleep(0.9)  # 每步之间间隔 0.9s
# D0029 触发后：熔断 5 分钟
```

---

## 四、RSA 加密规范

### 4.1 公钥来源

```
sys_params.json → numberEncryptPublicKey
```

Base64 值：
```
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCCtpetpDjhSUCWiqJ1Np8ht5ayB0n3KeGLtcC4
ELBmIigcSjPtV6fdykkyDNnN+fePdZz9tB75jw/DBjiR0rv+B1hFvofEdkikviTvvVAW/mShsqI3
9vBZ2+C9lZKb17hWsypOYgnhkondkkSsKi2Vz0vGGacSE9oDJz+Xcoc1zwIDAQAB
```

### 4.2 加密方式

- 算法：RSA 1024-bit PKCS#1 v1.5
- 输入：UTF-8 明文
- 输出：HEX 大写字符串（256 字符 = 128 bytes）
- Python 实现：`pycryptodome` → `PKCS1_v1_5.new(key).encrypt(plaintext)`

### 4.3 需加密的字段

| 端点 | 字段 | 内容 |
|------|------|------|
| NameSupplement | `busiAreaName` | 经营范围名称文本 |
| NameSupplement | `businessArea` | 经营范围描述文本 |
| NameSupplement | `busiAreaData` | 经营范围条目 JSON 字符串 |
| NameSupplement | `agent.certificateNo` | 身份证号 |
| NameSupplement | `agent.mobile` | 手机号 |

---

## 五、错误处理与分类体系

### 5.1 Phase1Error 枚举（12 种）

```python
class Phase1Error(str, Enum):
    NAME_PROHIBITED    = "name_prohibited"     # 含禁止词
    NAME_RESTRICTED    = "name_restricted"     # 含限制词
    NAME_CONFLICT      = "name_conflict"       # 同名冲突过多
    NAME_PRECHECK_FAIL = "name_precheck_fail"  # 本地词库拦截
    AUTH_EXPIRED       = "auth_expired"        # Authorization 过期
    AUTH_MISSING       = "auth_missing"        # 未提供 Authorization
    RATE_LIMITED       = "rate_limited"        # D0029 操作频繁
    PRIVILEGE_DENIED   = "privilege_denied"    # D0022 越权
    STEP_FAILED        = "step_failed"         # 某步非 00000
    STEP7_NO_BUSI_ID   = "step7_no_busi_id"   # 7 步全过但无 busiId
    UPSTREAM_DOWN      = "upstream_down"       # 远端 5xx/超时
    INTERNAL_ERROR     = "internal_error"      # 本服务内部异常
```

### 5.2 幂等机制

- `IdempotencyCache(ttl=1800)` — 30 分钟内同 case 不重复处理
- Key = `{name_mark}_{dist_code}_{ent_type}`
- 命中缓存返回 `cached: true`

---

## 六、禁用词库详情

### 6.1 分类与数量

| 分类 | 数量 | 判定等级 | 示例 |
|------|------|---------|------|
| 历史被拒_禁止 | 4 | prohibited | 裕安、六安 |
| 历史被拒_限制 | 9 | restricted | 科技、国际、中华 |
| 地名_省级 | 34 | prohibited | 北京、广西、香港 |
| 地名_广西地级 | 14 | prohibited | 南宁、玉林 |
| 地名_易混地级市 | 30 | prohibited | 深圳、杭州 |
| 地名_广西县级 | 57 | prohibited | 容县、北流 |
| 禁用类_行业敏感 | 17 | prohibited | 银行、证券、政府 |
| 禁用类_法律限制 | 7 | prohibited | 烟草专卖、彩票 |
| 限制类_驰名商标_世界500强 | 48 | restricted | 华为、美的、苹果 |
| 限制类_国内知名品牌 | 29 | restricted | 海底捞、大疆、拼多多 |
| **regions 自动提取** | **~300** | **region_name** | 广西全区划裸词 |
| **合计** | **~550** | — | — |

### 6.2 分类规则

```python
# 分类名前缀自动归类
"禁止" / "禁用" / "地名" → prohibited（短路拒绝）
"限制"                   → restricted（警告但不短路）
其他                     → prohibited（保守策略）
```

---

## 七、LLM 集成指南

### 7.1 Function Calling Schema

```bash
# 导出 OpenAI 格式的 8 个 tool 定义
python -m phase1_service.cli schema > tools.json
```

工具列表：
1. `phase1_precheck_name` — 名字预检
2. `phase1_register` — 7 步注册
3. `phase1_dict_ent_types` — 企业类型
4. `phase1_dict_industries` — 行业码
5. `phase1_dict_organizes` — 组织形式
6. `phase1_dict_regions` — 区划
7. `phase1_scope` — 经营范围
8. `phase1_auth_status` — 认证状态

### 7.2 LLM 工作流示例

```
用户输入: "帮我注册一个个人独资的软件开发公司，在广西容县"

LLM 执行步骤:
  1. phase1_dict_ent_types()          → 选 4540（个人独资企业）
  2. phase1_dict_industries(4540)     → 选 6513（应用软件开发）
  3. phase1_dict_organizes(4540)      → 选 "中心（个人独资）"
  4. phase1_dict_regions()            → 选 450000/450900/450921
  5. phase1_precheck_name("XXX")      → 确认字号无禁用词
  6. phase1_register({case...})       → 获得 busiId
  7. phase1_scope(4540, "软件开发")   → 获取经营范围条目
  8. [future] phase1_supplement(...)  → 补充信息并提交

如果任何步骤失败，LLM 解析 error_code 并给用户建议：
  - name_restricted → "字号含驰名商标'XXX'，建议更换"
  - rate_limited    → "服务端限流，请等待 5 分钟后重试"
  - auth_expired    → "认证已过期，请重新登录"
```

### 7.3 CLI 用法

```bash
# 预检名字
python -m phase1_service.cli precheck 李陈梦

# 从 case 文件注册
python -m phase1_service.cli register --case docs/case_广西容县李陈梦.json

# 查字典
python -m phase1_service.cli dict ent-types
python -m phase1_service.cli dict industries --entType 4540
python -m phase1_service.cli dict organizes --entType 4540
python -m phase1_service.cli dict regions

# 查经营范围
python -m phase1_service.cli scope --entType 4540 --keyword 软件开发

# 检查认证
python -m phase1_service.cli auth --probe
```

---

## 八、已验证的实网里程碑

### 8.1 Phase 1 Step 1 — 名称检查

| 时间 | 事件 | busiId |
|------|------|--------|
| 2026-04-22 | 7 步协议链完全跑通 | `2046839649770536960` |
| 2026-04-22 | hit_count=6, checkState=4 | — |
| 2026-04-22 | 首次用纯 Python 拿到 busiId | — |

### 8.2 抓包样本

| 文件 | 内容 |
|------|------|
| `phase1_submit_chain_full.json` | 完整 NameCheckInfo + NameSupplement + submit + NameSuccess 链路抓包 |
| `phase1_steps_5_7_dump.json` | Step 5/6/7 请求体和响应体 |
| `phase1_all_requests.json` | 所有 Phase 1 HTTP 请求 |

---

## 九、经营范围数据格式

### 9.1 正确格式（searchList 原始格式）

```json
{
  "id": "I3006",
  "stateCo": "1",
  "name": "软件开发",
  "pid": "65",
  "minIndusTypeCode": "6511;6512;6513",
  "midIndusTypeCode": "651;651;651",
  "isMainIndustry": "0",
  "category": "I",
  "indusTypeCode": "6511;6512;6513",
  "indusTypeName": "软件开发"
}
```

### 9.2 错误格式（会导致 A0002）

```json
// ❌ 简化格式 → 服务端拒绝
{"name": "软件开发", "code": "I3006", "isMain": true}
```

**必须使用含 id/stateCo/pid/minIndusTypeCode 的完整格式。**

---

## 十、数据普查汇总

### 10.1 Tier A — 企业类型 + 字典

| entType | 名称 | industries | organizes | 状态 |
|---------|------|-----------|-----------|------|
| 1100 | 内资有限公司 | ✅ | ✅ | 完成 |
| 1110 | 有限责任公司（国有独资） | ✅ | ✅ | 完成 |
| 1120 | 有限责任公司（外商投资） | ✅ | ✅ | 完成 |
| 1130 | 有限责任公司（自然人投资） | ✅ | ✅ | 完成 |
| 1140 | 有限责任公司（国有控股） | ✅ | ✅ | 完成 |
| 1150 | 一人有限责任公司 | ✅ | ✅ | 完成 |
| 1190 | 其他有限责任公司 | ✅ | ✅ | 完成 |
| 4540 | 个人独资企业 | ✅ | ✅ | 完成 |
| 9100 | 农民专业合作社 | ✅ | ✅ | 完成 |
| 9600 | 个体工商户 | ✅ | ✅ | 完成 |

### 10.2 Tier D — 经营范围

| 数据集 | 文件数 | 条目数 | 状态 |
|--------|--------|--------|------|
| Wave 1（种子词） | 310 | ~18,000 | 完成 |
| Wave 2（717 关键词扩充） | 128/717 | ~18,000+ | 进行中 |
| **合计** | **620** | **36,349** | — |

---

## 十一、依赖与部署

### 11.1 Python 依赖

```
fastapi>=0.110
uvicorn>=0.28
pydantic>=2.6
requests>=2.31
pycryptodome>=3.20    # RSA 加密
```

### 11.2 启动命令

```bash
# 开发
uvicorn phase1_service.api.main:app --host 0.0.0.0 --port 8800 --reload

# 生产
uvicorn phase1_service.api.main:app --host 0.0.0.0 --port 8800 --workers 2
```

### 11.3 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| 无 | Authorization 通过请求体或 runtime_auth 文件自动获取 | — |

---

## 十二、完整业务组件链（compComb）

来自 `loadCurrentLocationInfo` 响应：

```
NameCheckInfo → NameSupplement → NameSuccess → NameEstablished →
NameElectronicDoc → NameInfoElectronicDoc → NameNotification → NameRegBusiLicence
```

| 组件 | 中文名 | Phase | API 覆盖 |
|------|--------|-------|---------|
| NameCheckInfo | 名称检查 | 1-Step1 | ✅ register |
| NameSupplement | 信息补充 | 1-Step2 | ✅ supplement |
| NameSuccess | 申报完成 | 1-Step3 | ✅ supplement (auto_submit) |
| NameEstablished | 设立登记 | 2 | ❌ 待实现 |
| NameElectronicDoc | 电子签章 | 2 | ❌ 待实现 |
| NameInfoElectronicDoc | 信息确认 | 2 | ❌ 待实现 |
| NameNotification | 告知书 | 2 | ❌ 待实现 |
| NameRegBusiLicence | 营业执照 | 2 | ❌ 待实现 |

**Phase 1（名称登记）= NameCheckInfo + NameSupplement + NameSuccess — 已全部实现。**
**Phase 2（设立登记→云提交停点）= NameEstablished 起 — 下一阶段。**

---

## 十三、状态机

```
status=10 (草稿)
    │
    ├── register 成功 → busiId 分配，仍 status=10
    │
    ├── supplement 保存 → 信息补充完成，仍 status=10
    │
    ├── submit → status=20 (已提交)
    │
    └── NameSuccess/load → status=51 (审核中), nameId 分配
```

---

*文档结束。完整源码见 `phase1_service/` 目录。*
