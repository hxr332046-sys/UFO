# 广西经营主体登记 API 调用手册

> **项目**：`@/UFO/政务平台`
> **目标**：Phase 1（名称登记 7 步）+ Phase 2（设立登记 25 步）纯 HTTP API 使用指南
> **适用**：后端集成、命令行调用、自动化脚本
> **更新**：2026-04-24

---

## 一、启动服务

### 1.1 本地启动 FastAPI

```powershell
# 监听 127.0.0.1:8800
.\.venv-portal\Scripts\python.exe -m uvicorn phase1_service.api.main:app --host 127.0.0.1 --port 8800
```

### 1.2 启动浏览器（用于 CDP session 同步）

```powershell
# Edge 稳定版，独立 profile，CDP 9225 端口
Start-Process "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" -ArgumentList @(
  "--remote-debugging-port=9225",
  "--remote-allow-origins=*",
  "--user-data-dir=C:\Temp\EdgeCDP9225",
  "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"
)
# 在窗口里扫二维码登录（大概 30 秒）
```

---

## 二、API 端点速查（27 个）

| 路由 | 方法 | 用途 |
|------|------|------|
| `/healthz` | GET | 健康检查 |
| `/` | GET | 服务入口（API 清单） |
| **认证** | | |
| `/api/auth/status` | GET | Authorization 是否有效（`probe=true` 实打一次接口验证） |
| `/api/auth/keepalive` | POST | Token 保活 ping |
| `/api/auth/token/refresh` | POST | 静默续期（2 秒，不扫码） |
| `/api/auth/token/ensure` | POST | 智能获取：existing → refresh → qr_needed |
| `/api/auth/qr/start` | POST | 生成二维码（返回 base64 + sid） |
| `/api/auth/qr/status?sid=X` | GET | 轮询扫码状态（扫完自动拿 token） |
| **Phase 1 核名** | | |
| `/api/phase1/register` | POST | 7 步协议链拿 busiId |
| `/api/phase1/precheck_name` | POST | 核名预检（不保存） |
| `/api/phase1/supplement` | POST | 信息补充 + 股东 + submit |
| **Phase 2 设立** | | |
| `/api/phase2/register` | POST | 25 步全链路（到云提交停点） |
| `/api/phase2/session/recover` | POST | 浏览器 → Python session 同步 |
| `/api/phase2/cache/stats` | GET | 幂等缓存统计 |
| `/api/phase2/progress?busi_id=X&name_id=Y` | GET | 查询办件当前 establish 位置 |
| **办件管理** | | |
| `/api/matters/list?search&page&size&state` | GET | 我的办件列表 |
| `/api/matters/detail?busi_id=X&name_id=Y` | GET | 办件详情 + establish 位置 |
| **字典** | | |
| `/api/phase1/dict/ent-types?level=1` | GET | 企业类型 |
| `/api/phase1/dict/industries/{entType}?busiType=01` | GET | 行业 |
| `/api/phase1/dict/organizes/{entType}?busiType=01` | GET | 组织形式 |
| `/api/phase1/dict/regions` | GET | 行政区划 |
| `/api/phase1/dict/name-prefixes/{distCode}/{entType}` | GET | 字号前缀 |
| `/api/phase1/scope?entType=&busiType=` | GET | 经营范围（本地 census） |
| `/api/phase1/scope/search?keyword=&industry_code=&limit=` | GET | **经营范围实时搜索（平台最新字典）** |
| **系统参数** | | |
| `/api/system/sysparam/snapshot?keys=&mask_keys=` | GET | **本地 sysParam 快照（aesKey / RSA 公钥等）** |
| `/api/system/sysparam/key/{key}` | GET | **按 key 查单条** |
| `/api/system/sysparam/refresh` | POST | **实时刷新本地快照（调上游 getAllSysParam）** |
| **调试辅助** | | |
| `/api/debug/mitm/samples?api_pattern=&opeType=&code=&limit=` | GET | **mitm 样本列表** |
| `/api/debug/mitm/latest?api_pattern=&only_success=` | GET | **最新一条 mitm 样本（完整 req+resp）** |
| `/api/debug/mitm/stats` | GET | **mitm 抓包概览（总数 / methods / top codes / top APIs）** |

---

## 三、标准工作流

### 3.1 全新案例（Phase 1 + Phase 2 一条龙）

```powershell
# Step A: 扫码登录后同步 session
curl -X POST http://127.0.0.1:8800/api/phase2/session/recover

# Step B: 跑完整 25 步（自动先跑 Phase 1 + 完整 Phase 2）
$body = @{
  case = (Get-Content 'docs\case_有为风.json' -Raw | ConvertFrom-Json)
  stop_after = 25
  start_from = 1
  auto_phase1 = $true
} | ConvertTo-Json -Depth 20 -Compress

curl -X POST http://127.0.0.1:8800/api/phase2/register `
  -H "Content-Type: application/json" `
  -d $body
```

### 3.2 断点续跑（已有 busiId）

```powershell
# 从 step 25 开始（验证是否已到云提交停点）
$body = @{
  case = (Get-Content 'docs\case_有为风.json' -Raw | ConvertFrom-Json)
  busi_id = "2047122548757872642"
  name_id = "2047094115971878913"
  start_from = 25
  stop_after = 25
  auto_phase1 = $false
} | ConvertTo-Json -Depth 20 -Compress

curl -X POST http://127.0.0.1:8800/api/phase2/register `
  -H "Content-Type: application/json" `
  -d $body
```

### 3.3 只跑 Phase 1（只核名不推进）

```powershell
curl -X POST http://127.0.0.1:8800/api/phase1/register `
  -H "Content-Type: application/json" `
  -d (Get-Content 'docs\case_有为风.json' -Raw)
```

### 3.4 前端集成标准流（登录 → 列表 → 断点续跑）

```typescript
// ① 确保有 token（自动续期，失败返回需扫码标志）
let r = await fetch('/api/auth/token/ensure', {method: 'POST'}).then(r=>r.json())
if (!r.success && r.source === 'qr_needed') {
  // 调 /qr/start 拿二维码，前端 base64 展示，轮询 /qr/status
  const qr = await fetch('/api/auth/qr/start', {method: 'POST'}).then(r=>r.json())
  showQrImage('data:image/png;base64,' + qr.qr_image_base64)
  while (true) {
    await sleep(3000)
    const s = await fetch(`/api/auth/qr/status?sid=${qr.sid}`).then(r=>r.json())
    if (s.success) { console.log('got token', s.authorization); break }
    if (!s.pending) { alert(s.reason_detail); break }
  }
}

// ② 列出办件
const matters = await fetch('/api/matters/list?size=20').then(r=>r.json())
const target = matters.items[0]  // 用户选一个

// ③ 查进度
const prog = await fetch(`/api/phase2/progress?busi_id=${target.id}&name_id=${target.nameId}`).then(r=>r.json())
console.log('当前在', prog.currCompUrl, 'status=', prog.status)

// ④ 断点续跑
const body = {
  case: caseData,
  busi_id: target.id,
  name_id: target.nameId,
  start_from: decideStartFrom(prog.currCompUrl),
  stop_after: 25,
  auto_phase1: false,
}
const result = await fetch('/api/phase2/register', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(body),
}).then(r=>r.json())
```

---

## 四、Phase 2 25 步全景

| # | 步骤名 | 类型 | 说明 |
|---|--------|------|------|
| 1-9 | Phase 1 后半段 | load/save | NameSupplement → NameShareholder → name/submit → NameSuccess（带 Phase 1 前 7 步结果） |
| 10 | matters/operate [108, before] | save | establish 入口预判 |
| 11 | matters/operate [108, operate] | save | 正式切换到 establish domain |
| 12 | establish/loadCurrentLocationInfo | load | 定位到 establish 首页 |
| 13 | YbbSelect/loadBusinessDataInfo | load | 云帮办（optional，可 D0021） |
| 14 | BasicInfo/loadBusinessDataInfo | load | 读基本信息表模板 |
| **15** | **BasicInfo/operationBusinessDataInfo [save]** | save | **关键** — 创建 establish busiId |
| 16 | MemberPost/operationBusinessDataInfo [save] | save | 成员架构（board/boardSup/pkAndMem） |
| 17 | MemberPool/loadBusinessInfoList | load | 成员列表（optional） |
| 18 | MemberInfo/operationBusinessDataInfo [save] | save | 成员详情（politicsVisage + isOrgan + gdMemPartDto） |
| 19 | ComplementInfo/operationBusinessDataInfo [save] | save | 补充信息（空体推进） |
| 20 | TaxInvoice/operationBusinessDataInfo [save] | save | 税务（空体推进） |
| 21 | SlUploadMaterial [upload+bind+save] | 三步法 | 文件上传 → cerno 小写绑定 → 推进 |
| 22 | BusinessLicenceWay/operationBusinessDataInfo [save] | save | 领取方式（空体推进） |
| 23 | YbbSelect/operationBusinessDataInfo [save] | save | 云帮办选择 (isSelectYbb=0) |
| 24 | PreElectronicDoc/operationBusinessDataInfo [save] | save | 信息确认（空体推进） |
| **25** | **PreSubmitSuccess/loadBusinessDataInfo** | load | **云提交停点（本项目目标）** |

---

## 五、请求 / 响应 schema

### 5.1 Phase 2 请求体

```typescript
{
  "case": {
    // 公司基本信息
    "company_name_phase1_normalized": "有为风（广西容县）软件开发中心（个人独资）",
    "name_mark": "有为风",
    "entType_default": "4540",
    "busiType_default": "02_4",

    // 投资人
    "person": {
      "name": "黄永裕",
      "mobile": "18977514335",
      "id_no": "450921198812051251",
      "email": "344979990@qq.com"
    },

    // 地址
    "address_full": "广西壮族自治区玉林市容县容州镇车站西路富盛广场1幢3203号房",
    "phase1_dist_codes": ["450000", "450900", "450921"],

    // Phase 1 行业
    "phase1_industry_code": "6513",
    "phase1_industry_name": "应用软件开发",
    "phase1_industry_special": "软件开发",
    "phase1_organize": "中心（个人独资）",
    "phase1_name_pre": "广西容县",
    "phase1_check_name": "有为风（广西容县）软件开发中心（个人独资）",
    "phase1_main_business_desc": "软件开发",

    // Phase 2 业务字段（可选，有默认值）
    "property_use_mode": "租赁",           // 自有产权 / 租赁 / 借用
    "house_to_bus": "否",                  // 否 / 是
    "politics_visage": "群众",             // 群众 / 党员 / ...
    "phase2_invest_date": "2030-04-24",
    "phase2_invest_money_yuan": "100000",

    // 文件路径（Phase 2 step 21 用）
    "assets": {
      "property_cert": "G:\\YU\\资料\\住所证明.PDF",
      "lease_contract": "G:\\YU\\资料\\微信图片_20260411104217_91_17.jpg",
      "id_front": "G:\\YU\\资料\\身份证正面_副本.jpg",
      "id_back": "G:\\YU\\资料\\身份证正面.jpg"
    }
  },
  "authorization": null,                    // 留空用服务器已抓 token
  "busi_id": "2047122548757872642",         // 断点续跑传已有 busiId
  "name_id": "2047094115971878913",         // 断点续跑传已有 nameId
  "start_from": 1,                          // 1~25
  "stop_after": 25,                         // 1~25
  "auto_phase1": false                      // 缺 busi_id 时是否自动跑 Phase 1
}
```

### 5.2 响应体

```typescript
{
  "success": true,
  "busiId": "2047122548757872642",
  "nameId": "2047094115971878913",
  "establish_busiId": null,                 // step 15 save 成功时会有值
  "basicinfo_signInfo": null,               // step 14 load 捕获的动态 signInfo
  "stopped_at_step": 25,
  "steps": [
    {
      "i": 25,
      "name": "establish/PreSubmitSuccess/loadBusinessDataInfo [终点]",
      "ok": true,
      "code": "00000",
      "resultType": "0",
      "msg": "操作成功",
      "duration_ms": 230,
      "busiData_preview": "{...flowData.currCompUrl: PreSubmitSuccess, status: 90...}"
    }
  ],
  "latency_ms": 4419,
  "reason": null,
  "reason_detail": null,
  "phase1_executed": false,
  "phase1_busiId": null,
  "phase1_reason": null
}
```

---

## 六、常见错误码

| code | 含义 | 解法 |
|------|------|------|
| `00000` | 操作成功 | — |
| `GS52010103E0302` | session 过期 | `POST /api/phase2/session/recover` |
| `D0018` | 业务状态已变化 | 刷新/读新位置；通常步骤已完成过 |
| `D0019` | 越权访问 | linkData 路径错误，检查 compUrlPaths/busiCompUrlPaths |
| `D0021` | 越权（上下文错误） | step 13 的 YbbSelect 返回这个是正常，optional 跳过 |
| `D0022` | 越权（三层洋溪） | 检查 headers / body / signInfo |
| `D0029` | 操作频繁 | 等 5-10 分钟，不要重试 |
| `A0002` | 服务端异常 | 检查字段大小写、JSON 结构、见 MD 铁律 |
| `D0010` | 当前表单无需填写 | PreSubmitSuccess load 的正常状态 |

---

## 七、断点续传指南

### 查找当前断点

```powershell
# 读最近一次 Phase 1 产物
Get-Content 'dashboard\data\records\phase1_protocol_driver_latest.json' -Encoding UTF8

# 读最近一次 Phase 2 产物
Get-Content 'dashboard\data\records\phase2_protocol_driver_latest.json' -Encoding UTF8
```

### start_from 参考

| 场景 | start_from | auto_phase1 |
|------|-----------|-------------|
| 全新案例、自动 Phase 1 | 1 | true |
| 全新案例、已手动 Phase 1 | 1 | false |
| Phase 1 已完成，跳到 establish | 10 | false |
| BasicInfo 已 save 过，进成员 | 16 | false |
| 成员已完成，进后段 | 19 | false |
| 只验证已到云提交停点 | 25 | false |

---

## 八、排错三板斧

### 8.1 session 问题

```powershell
# 诊断：调用 getUserInfo 验证 Authorization 是否有效
.\.venv-portal\Scripts\python.exe -c "
import sys; sys.path.insert(0, r'G:\UFO\政务平台\system')
from icpsp_api_client import ICPSPClient
c = ICPSPClient()
print(c.get_json('/icpsp-api/v4/pc/manager/usermanager/getUserInfo'))
"

# 解决：重新扫码 + 同步
curl -X POST http://127.0.0.1:8800/api/phase2/session/recover
```

### 8.2 A0002 服务端异常

1. 查 `@/UFO/政务平台/docs/Phase2_云提交停点达标_20260424.md` 第 4 节"铁律"
2. 对比 body 和 mitm 样本 `@/UFO/政务平台/dashboard/data/records/establish_save_samples/`
3. 字段大小写逐字符核对

### 8.3 D0029 频控

**等 5-10 分钟**。同一 session 内禁止并发或快速连发写接口。

---

## 九、相关文档

| 入口 | 说明 |
|------|------|
| `@/UFO/政务平台/docs/协议化登记_资产与框架总览.md` | 顶层资产总览 |
| `@/UFO/政务平台/docs/Phase2_云提交停点达标_20260424.md` | 最新达标纪要（本阶段） |
| `@/UFO/政务平台/docs/Phase2_纯协议25步固化_20260424.md` | 25 步驱动器详细 |
| `@/UFO/政务平台/docs/Phase2_阶段总结_20260423.md` | 第一日突破 |
| `@/UFO/政务平台/docs/Phase2枚举字段字典_20260424.md` | 业务语言 → 编码 |

---

_更新：2026-04-24_
