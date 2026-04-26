# 第一阶段名称登记服务（phase1_service）

> 基于 2026-04-22 D0022 越权突破成果，把"广西政务平台·名称登记 Phase 1"的**协议链路**封装成：
> 1. **全量字典普查** → 本地化所有可选项
> 2. **FastAPI 内部服务** → 业务系统即可调用拿 `busiId`

---

## 一、目录总览

```
phase1_service/
  README.md            ← 本文档
  PROGRESS.md          ← 普查与 API 交付进度
  requirements.txt     ← 独立依赖（FastAPI + uvicorn + httpx + sqlite3）

  api/                 ← FastAPI 内部服务
    main.py            ← uvicorn 入口
    routers/
      registration.py  ← POST /api/phase1/register  → busiId
      dictionaries.py  ← GET  /api/phase1/dict/*    → 本地字典
      business_scope.py← GET  /api/phase1/scope?kw= → 经营范围
    core/
      driver_adapter.py← 对接 system/phase1_protocol_driver.py
      rate_limiter.py  ← 令牌桶（防 D0029）
      auth_manager.py  ← Authorization token 存取与刷新
    schemas/
      case.py          ← 请求体 schema
      response.py      ← 响应体 schema

  census/              ← 全量字典普查
    run_census.py      ← 主脚本：断点续跑 + 守护节奏 + D0029 熔断
    census_plan.json   ← 按 Tier A/B/C/D 分级的接口清单
    registry/
      tier_a.py        ← Tier A 无参数字典（一次完事）
      tier_b.py        ← Tier B 遍历 entType
      tier_c.py        ← Tier C entType × 区划
      tier_d.py        ← Tier D 经营范围（queryIndustryFeatAndDes 按 hyPecul 穷举）

  data/                ← 普查产物（JSON + SQLite）
    dictionaries/
      ent_types.json              ← 全部 entType
      industries/{entType}.json   ← 每种 entType 的行业码全量
      business_scopes/{entType}.json ★ 经营范围（按 hyPecul 分组）
      organizes/{entType}.json    ← 组织形式
      regions/{province}.json     ← 省级下钻
      name_prefixes/{dist}.json   ← 区县名称前缀
      sys_params.json             ← 系统参数
      code_lists/{key}.json       ← 通用码字典
    cache/                        ← 普查中间状态（可中断）
    dict_v2.sqlite → ln ../../dashboard/data/records/dict_v2.sqlite

  tests/
    test_census_offline.py        ← 普查脚本离线单测（不连网）
    test_api.py                   ← FastAPI 端到端测试
```

---

## 二、分层清单（第一阶段 27 个接口）

### Tier A · 无参数字典（≈10 个接口，跑 1 轮即可）

- `queryNameEntType?type=1`
- `queryNameEntType?type=2`
- `queryRegcodeAndStreet`
- `queryCodeList?key=CODE_MOKINDCODE`
- `queryCodeList?key=CODE_CERTYPECODE`
- `getAllSysParam`
- `getSerialTypeCode`
- `getRentalHouseCode`
- `selectBusinessModules`
- `sysConfig/getSysConfig?key=noIndSpeTips`

### Tier B · entType 维度（~20 种 entType × 2 busiType）

- `getAllIndustryTypeCode?entType={X}&busiType={Y}&range=1`（行业码全量，每条 ~50KB）
- `getOrganizeTypeCodeByEntTypeCircle?entType={X}&busType={Y}`
- `queryNameEntTypeCfgByEntType?entType={X}`

### Tier C · entType × 区划

- `queryNamePrefix?distCode={X}&entType={Y}`
- `listOrgan?areaCode={X}&distCode={X}&busType={Y}&entType={Y}`

### Tier D · 经营范围（★ 用户重点强调）

- `queryIndustryFeatAndDes?busType={Y}&entType={X}&hyPecul={KEYWORD}`  
  **依赖**：先从 Tier B `getAllIndustryTypeCode` 提取所有唯一的行业特征关键词集合。

### Tier E · 会话敏感（不做普查，仅 API 调用）

`checkEstablishName`、`loadCurrentLocationInfo`、`loadBusinessDataInfo`、`bannedLexiconCalibration`、`operationBusinessDataInfo`、`nameCheckRepeat`、`checkGreenChannel`

---

## 三、守护节奏（防 D0029 限流）

- **请求间隔**：默认 2.0 秒（可配置）
- **熔断**：连续 2 次 `D0029` 即暂停 10 分钟
- **断点续跑**：`data/cache/census_state.json` 记录每个请求的完成状态
- **预估耗时**：Tier A+B+C ≈ 2~3 小时；Tier D 视 hyPecul 关键词数量

---

## 四、API 对外合同

### POST `/api/phase1/register`

请求：
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
  "authorization": "<32-hex ICPSP token>"
}
```

响应：
```json
{
  "success": true,
  "busiId": "2046839649770536960",
  "hit_count": 6,
  "checkState": 4,
  "similar_names": [...],
  "steps": [...],
  "latency_ms": 1870
}
```

### POST `/api/phase2/register` ★ 新增

封装 `system/phase2_protocol_driver.py` 的 15 步流程（默认 stop_after=14）。

**请求**：
```json
{
  "case": { ... case_*.json 的完整内容 ... },
  "authorization": "<32-hex token，可选>",
  "busi_id": "2047369185264271360",
  "name_id": "2047368861596590082",
  "start_from": 1,
  "stop_after": 14,
  "auto_phase1": false
}
```

字段说明：
- `case`：Phase 2 案件字段。可直接传 `docs/case_有为风.json` 的完整 JSON（含 `person` / `entType_default` / `phase1_dist_codes` 等）
- `busi_id`：Phase 1 拿到的 busiId。留空则自动读 `dashboard/data/records/phase1_protocol_driver_latest.json`
- `name_id`：已有 nameId 则传入（跳过 step 9）。首次跑省略
- `start_from` / `stop_after`：断点续跑窗口（1-15），默认 `1→14`（step 15 BasicInfo save 当前存在 A0002 风险，不纳入默认链路）
- `auto_phase1=true`：缺 `busi_id` 时自动先跑 Phase 1（需 case 含 Phase 1 字段）

**响应**：
```json
{
  "success": true,
  "busiId": "2047369185264271360",
  "nameId": "2047368861596590082",
  "establish_busiId": null,
  "basicinfo_signInfo": "-1506709975",
  "stopped_at_step": 14,
  "steps": [ { "i": 1, "name": "...", "ok": true, "code": "00000", ... }, ... ],
  "latency_ms": 42300,
  "reason": null,
  "phase1_executed": false
}
```

**错误分类**（返回 HTTP 200 带 `reason`）：
- `session_expired`：Authorization 或 session cookie 失效 → 重新登录
- `rate_limit`：D0029 触发 → 等待几分钟
- `stepN_failed`：具体步骤业务拒绝
- `phase1_failed`：`auto_phase1=true` 时 Phase 1 拿不到 busiId

### GET `/api/phase1/dict/ent-types`

返回所有企业类型（Tier A）。

### GET `/api/phase1/dict/industries/{entType}`

返回指定 entType 的行业码全量。

### GET `/api/phase1/scope?entType={X}&keyword={KW}`

★ 根据 `entType` + 关键词返回经营范围建议（来自 Tier D 本地缓存）。

---

## 五、运行

```bash
# 安装依赖
pip install -r phase1_service/requirements.txt

# 全量普查（耗时 2-3 小时）
python phase1_service/census/run_census.py --all

# 只跑某个 Tier
python phase1_service/census/run_census.py --tier A
python phase1_service/census/run_census.py --tier D --resume

# 启动 API
uvicorn phase1_service.api.main:app --host 0.0.0.0 --port 8800
```

---

## 六、与仓库其他部分的关系

- 依赖：`system/phase1_protocol_driver.py`（Phase 1 七步协议驱动器）
- 依赖：`system/icpsp_api_client.py`（HTTP 客户端 + 浏览器指纹头）
- 依赖：`docs/突破D0022越权_协议层字段合同方法论_20260422.md`（方法论）
- 复用：`dashboard/data/records/dict_v2.sqlite`（已有字典底座，软链进来）

---

_整理于 2026-04-22  Cascade_
