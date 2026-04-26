# 交付进度

## 总览

| 板块 | 状态 | 备注 |
|------|------|------|
| 目录骨架 | ✓ 完成 | 2026-04-22 14:50 |
| 普查清单 `census_plan.json` | ✓ 完成 | Tier A (12 个接口) / B / C / D 已定义 |
| `registry/_common.py` | ✓ 完成 | CensusState + PaceConfig + 统一 GET |
| `registry/tier_a.py` | ✓ 完成 |  |
| `registry/tier_b.py` | ✓ 完成 | 从 Tier A 提取 entType |
| `registry/tier_c.py` | ✓ 完成 | 从 Tier A regions 提取 distCode |
| `registry/tier_d.py`（经营范围）| ✓ 完成 | ★ 从 Tier B industries 提取 hyPecul 关键词 |
| `census/run_census.py` | ✓ 完成 | `--tier A/B/C/D/all` + `--resume` + `--dry_run` |
| `api/main.py` | ✓ 完成 | FastAPI + CORS |
| `api/routers/registration.py` | ✓ 完成 | POST /api/phase1/register |
| `api/routers/dictionaries.py` | ✓ 完成 | GET /api/phase1/dict/* (5 个) |
| `api/routers/business_scope.py` | ✓ 完成 | GET /api/phase1/scope |
| `api/core/rate_limiter.py` | ✓ 完成 | AsyncTokenBucket + D0029 熔断 |
| `api/core/auth_manager.py` | ✓ 完成 | 写 runtime_auth_headers.json |
| `api/core/driver_adapter.py` | ✓ 完成 | 线程池包裹 phase1_protocol_driver |
| `requirements.txt` | ✓ 完成 | fastapi / uvicorn / pydantic / requests / websocket-client |
| FastAPI 本地健康检查 | ✓ 通过 | http://127.0.0.1:8800/healthz = 200 |
| Swagger 文档 | ✓ 通过 | http://127.0.0.1:8800/docs |
| 实网普查 Tier A | ✓ 完成 | 12/12 全绿，耗时 35.3s |
| Tier B 全量 entType | ✓ 完成 | 10 entType × industries/organizes/cfg = 24/24 OK |
| 实网普查 Tier D Wave 1 | ✓ 完成 | 87 种子 × 2 entType × 01 = 174 请求，100% 命中 |
| 实网普查 Tier D Wave 2 | 🔄 运行中 | 717 新关键词 × 2 entType = 1434 请求 |
| FastAPI /scope 字段修正 | ✓ 完成 | 对齐真实字段 hyCode/hyTypeName/includes |
| register API 实网 E2E | ✓ 通过 | 4/4 案件全绿（详见下方） |
| 多案件通用性验证 | ✓ 通过 | 不同地区(容县/南宁/梧州/桂林) × 不同类型(4540/1100) |
| `api/routers/precheck.py` | ✓ 完成 | POST /precheck_name（本地 444 词 + 可选实网校验，12/12 通过） |
| `api/routers/auth.py` | ✓ 完成 | GET /auth/status（本地 + 可选 probe）|
| `api/core/errors.py` | ✓ 完成 | Phase1Error 枚举（12 种错误分类） |
| `api/core/idempotency.py` | ✓ 完成 | 内存 TTL 幂等缓存（同 case 30min 内不重复调） |
| `api/core/banned_words_loader.py` | ✓ 完成 | 本地禁用词库（500+ 词含驰名商标 70+） |
| `api/core/rsa_encrypt.py` | ✓ 完成 | RSA PKCS#1 v1.5 加密（numberEncryptPublicKey） |
| `api/core/supplement_driver.py` | ✓ 完成 | NameSupplement 协议构造（Step 8-10） |
| `api/routers/supplement.py` | ✓ 完成 | POST /supplement（信息补充 + 提交 + 验证） |
| `cli.py` | ✓ 完成 | CLI 入口（precheck/register/dict/scope/auth/schema） |
| `api/llm_function_schema.py` | ✓ 完成 | 8 个 OpenAI function calling tool 定义 |
| 全端点验证 | ✓ 通过 | 10/10 端点 OK（含 supplement） |
| API 覆盖审计 | ✓ 完成 | 12 张 UI 截图 vs API 逐项验证 |
| 完整技术文档 | ✓ 完成 | docs/Phase1_名称登记API_技术文档_完整版.md |

## Wave 1 产出统计（2026-04-22 15:30）

| 指标 | 数量 |
|------|------|
| Tier A 基础字典 | 12 个文件 / 247 KB |
| Seed 字典（dict_cache 移植） | 6 个文件 / 1.7 MB |
| Tier D 经营范围 | **36,349 条**（87×2 entType = 174 关键词，100% 命中） |
| 覆盖的 entType | `4540`（个独） + `1100`（有限公司） |
| 覆盖的 busiType | `01`（设立登记） |

## 可立即调用的 API 示例

```
GET  /api/phase1/scope?entType=4540&busiType=01&keyword=软件开发
  → 返回 19 条：基础软件开发/应用软件开发/支撑软件开发/游戏软件/信息系统集成 ...

GET  /api/phase1/scope?entType=4540&busiType=01&keyword=农业
  → 返回 300 条

GET  /api/phase1/dict/industries/4540
  → 1971 条个独可选行业码

POST /api/phase1/register
  { case: {...}, authorization: "<32-hex>" }
  → 执行 7 步协议链，返回新 busiId
```

## 依赖外部资产

- ✓ `system/phase1_protocol_driver.py`（可直接 import）
- ✓ `system/icpsp_api_client.py`
- ✓ `dashboard/data/records/dict_v2.sqlite`（已有 39k+ 条 query_cases）
- ✓ `dashboard/data/records/mitm_ufo_flows_backup_20260421_231343.jsonl`（离线真理源）

## E2E 多案件验证（2026-04-22）

| 案件 | 地区 | entType | name_mark | busiId | 结果 |
|------|------|---------|-----------|--------|------|
| 李陈梦-容县 | 450921 | 4540 | 李陈梦 | 2046858923746656256 | ✅ |
| 李陈梦-南宁青秀 | 450103 | 4540 | 李陈梦 | 2046861738166583296 | ✅ |
| 裕鑫-桂林七星 | 450305 | 1100 | 裕鑫 | 2046861450089201664 | ✅ |
| 裕鑫-梧州万秀 | 450403 | 1100 | 裕鑫 | 2046861834505551872 | ✅ |

**发现的名称限制规则**（resultType 语义）：
- `resultType=0`：名称完全通过 → 分配 busiId
- `resultType=1`：名称含**禁止**使用的内容（如地名"裕安"） → 不分配 busiId
- `resultType=2`：名称含**限制**使用的内容（如"联创"） → step7 加 `afterNameCheckSign="Y"` 后可能通过

## 已知坑

- `signInfo=-252238669` 是魔数（详见 `docs/突破D0022越权_协议层字段合同方法论_20260422.md`）
- `D0029` 冷却 5-10 分钟，普查节奏 2s/请求起步
- `queryIndustryFeatAndDes` 的 `hyPecul` 关键词需先从行业字典提取（有依赖顺序）
- **名字禁限用词**：地名（裕安/六安等）、某些商业词（联创/科技等）会被服务端拒绝，需提前检查
