# Phase 2 开发记录（2026-04-23）

> 案例：广西有为风有限公司（个人独资 4540，busiId=`2046982359353524224`）  
> 目标：Phase 1（名称登记拿 busiId）→ Phase 2（补充信息+股东+提交+进入 establish+云帮办选择停点）  
> 方式：纯 HTTP 协议流（继承 Phase 1 突破的方法）

---

## 一、Phase 2 路径发现

### 关键洞察

**个人独资 (4540) 的 Phase 2 远比预想简单 — 12 个 API 即可完成**。

通过分析 `_archive/records/mitm_ufo_flows.jsonl`（29MB，1791 条流量，历史 mitm 抓包）筛选出 Phase 2 的实际 API，证明：

- **Phase 1 + Phase 2a** 都在 **name-register** 应用内（busiType=01）：
  1. `name/loadCurrentLocationInfo`
  2. `NameSupplement/loadBusinessDataInfo`
  3. `NameShareholder/loadBusinessInfoList`
  4. `NameShareholder/loadBusinessDataInfo`
  5. `NameShareholder/operationBusinessDataInfo` (RSA 加密)
  6. `NameShareholder/loadBusinessInfoList` (刷新)
  7. `NameSupplement/operationBusinessDataInfo` (AES 加密)
  8. `name/submit` (正式提交)
  9. `NameSuccess/loadBusinessDataInfo`

- **Phase 2b** 跳到 **establish** 应用（busiType=02）:
  10. `matters/operate` btnCode=101 dealFlag=before
  11. `matters/operate` btnCode=101 dealFlag=operate
  12. `establish/loadCurrentLocationInfo`
  13. `establish/component/YbbSelect/loadBusinessDataInfo` ← **停点**

### matters/operate btnCode 词典

| btnCode | 含义 |
|---|---|
| 101 | 继续办理 / 进入设立登记 ← 我们用这个 |
| 103 | 删除办件（危险） |
| 109 | 作废名称（危险） |

---

## 二、加密破解

### 发现

前端 JS (`name-register~002699c4.js`) 中的关键加密函数：

```javascript
// RSA 用于身份证号、手机号
encrypt(e) {
    t = getSysConfigByCode("numberEncryptPublicKey");
    return new JSEncrypt.setPublicKey(t).encrypt(e);  // PKCS1v15 + Base64
}

// AES 用于经营范围等大块数据
aesEncrypt(e) {
    t = getSysConfigByCode("aesKey");  // UTF-8
    key = iv = CryptoJS.enc.Utf8.parse(t);
    return AES.encrypt(e, key, {mode: CBC, iv, padding: Pkcs7})
           .ciphertext.toString().toUpperCase();  // hex 大写
}
```

### 密钥位置

密钥通过 **登录态调用** 可拿到：

```
GET /icpsp-api/v4/pc/common/configdata/sysParam/getAllSysParam
→ 返回 957 条系统参数
```

关键参数：

| key | value |
|---|---|
| `aesKey` | `topneticpsp12345` (16 字符) |
| `numberEncryptPublicKey` | RSA-1024 公钥 PEM Base64 |
| `isOpenEncryptAndDecrypt` | `N` |
| `gsHcpPublicKey` | 另一套公钥（备用） |
| `normAddressAespswd` | 标准地址 AES 密钥 |

### Python 实现

见 `@/g:/UFO/政务平台/system/icpsp_crypto.py:1-123`:

- `aes_encrypt(plaintext)` — AES-128-CBC, key=iv=UTF8(aesKey), PKCS7, hex 大写
- `rsa_encrypt(plaintext)` — RSA PKCS1v15, Base64

**自测通过**：
- AES round-trip OK
- RSA 输出长度 172 字符（匹配 mitm 样本）

---

## 三、session cookies 持久化

### 问题

Phase 2 API (如 `name/loadCurrentLocationInfo`) 需要 9087 的 **SESSION cookie**（Authorization 单独不够）。

### 解决

升级 `@/g:/UFO/政务平台/system/icpsp_api_client.py:158-187` 在 `ICPSPClient.__init__()` 中自动加载 `packet_lab/out/http_session_cookies.pkl`。

扫码登录 (`login_qrcode_pure_http.py --login`) 会自动保存 5 个 cookies：
- `SESSIONFORTYRZ` (tyrz 域)
- `lastAuthType=ZWFW_GUANGXI` (TopIP)
- `SESSION` (TopIP 路径)
- `SESSION` (icpsp-api 路径) ← **Phase 2 必需**
- `lastAuthType=ENT_SERVICE` (icpsp-api)

---

## 四、实测进展

### 当前成果（2026-04-23 凌晨 → 下午）

| 步骤 | API | 状态 | 备注 |
|---|---|---|---|
| 1 | name/loadCurrentLocationInfo | ✅ OK | 178ms |
| 2 | NameSupplement/loadBusinessDataInfo | ✅ OK | 334ms |
| 3 | NameShareholder/loadBusinessInfoList | ✅ OK | 110ms |
| 4 | NameShareholder/loadBusinessDataInfo | ✅ OK | 104ms |
| 5 | NameShareholder/operationBusinessDataInfo | ✅ OK (RSA) | 282ms — 投资人保存成功 |
| 6 | NameShareholder/loadBusinessInfoList | ✅ OK | 112ms |
| 7 | NameSupplement/operationBusinessDataInfo | ✅ **rt=0** (AES) | 经营范围字典对齐后完美通过 |
| 8 | name/submit | ✅ OK | 2310ms — status 10→51 |
| 9 | NameSuccess/loadBusinessDataInfo | ✅ OK | 244ms — 捕获 `nameId=2047094115971878913` |
| matters/search | GET（不是 POST）| ✅ | 空 body + URL 参数 |
| btnCode 字典 | 101=继续名称, 108=进设立 | ✅ | 通过遍历 btnCode 发现 |
| 10-13 | 进设立登记 | ⚠️ 瓶颈 | 见下 |

### 步骤 7 详情（已解决）

原问题：AES 加密 body 返回 `rt=1 警告: 你选择的经营范围中【软件开发】已发生变化或禁止使用`。

**解决**：调用 `GET /icpsp-api/v4/pc/common/busiterm/getThirdleveLBusitermList?keyWord=软件&indusTypeCode=6513` 查到字典里 `软件开发` 的真实 id：

```json
{
  "id": "I3006",
  "stateCo": "1",          // 不是 "3"
  "name": "软件开发",
  "pid": "65",
  "minIndusTypeCode": "6511;6512;6513",
  "midIndusTypeCode": "651;651;651",
  "isMainIndustry": "1",
  "category": "I",
  "indusTypeCode": "6511;6512;6513",
  "indusTypeName": "软件开发",
  "additionalValue": ""
}
```

用字典里原样的 id 和 stateCo 之后，step 7 返回 **rt=0 完美通过**，step 8 `name/submit` 也随即通过。

关键领悟：
- ✅ 加密流程完全正常
- ✅ 服务端对 `businessArea/busiAreaData/busiAreaName/busiAreaCode` 做严格字典校验
- ✅ `rt=1` 警告会导致事务**部分回滚**（字典失配字段），其他字段（如 `registerCapital, isPromiseLetterFlag`）会正常落库，但 submit 时会 D0018 失败

### 当前瓶颈：step 10-13 进入设立登记

name/submit 后 busi_id=`2046982359353524224` 状态变为 `status=51, busiType=01`。

通过遍历 `matters/operate` 的 btnCode 发现：

| btnCode | dealFlag=before msg | route busiType | 含义 |
|---|---|---|---|
| 101/102/105 | 操作成功 | `01_4` | 继续办理名称登记 |
| **108** | 操作成功 | **`02_4`** | **进入设立登记** ← 目标 |
| 109 | "作废后名称将被释放..." | — | 作废名称 |
| 103 | "此操作将永久删除..." | — | 删除 |
| 110/111 | GS52010310B0001 | — | 无权 |

**btnCode=108 的 route 参数：**
```json
{
  "project": "core",
  "path": "/flow/base",
  "params": {
    "busiType": "02_4",
    "entType": "4540",
    "nameId": "2047094115971878913",
    "visaFree": "true"
  },
  "target": "_blank"
}
```

**关键：route 里 `没有 busiId`！** 说明前端打开新 tab 到 `/flow/base?busiType=02_4&nameId=...&visaFree=true`，由前端路由初始化时调 **未知 API** 来创建新的设立 busiId。

### 进一步分析（前端 JS 反汇）

下载了 `core/js/base~21833f8f.js`（flow/base 路由 component）和 `core~40cc254d.js`（flow API 封装）。

**核心发现：**

1. **URL 前缀映射表** (`core~40cc254d.js` → `ae56.b`)：
```js
a = {"01": "register/name", "02": "register/establish", "03": "alt/altregister", ...}
```

2. **`getLocationInfo` 实现**：
```js
t.linkData.token = u();  // u() = sessionStorage.userinfo.user.id || ""
n = {
    url: "/" + s(t.flowData.busiType) + "/loadCurrentLocationInfo",
    method: "post",
    data: t
};
```

3. **`flow/base` 路由 `load()` 函数**：从 URL query 读出 `busiType/busiId/nameId/visaFree/extraDto` 等，组装 `params`，然后：
```js
var w = f ? "continueFlag" : this.$localStore.get("continueFlag") || "";
this.params.linkData.continueFlag = w;  // visaFree=true → "continueFlag"
```
然后调 `initData()` → `$api.flow.getLocationInfo(params)`。

**意味着：`btnCode=108` 跳转的 `/flow/base?visaFree=true&nameId=X` 实际上就是调用**：
```http
POST /icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo
{
  "flowData": {"busiType":"02_4","entType":"4540","busiId":null,"nameId":"X","fromType":null,"marPrId":null,"secondId":null,"vipChannel":null},
  "linkData": {"continueFlag":"continueFlag","token":"<user.id>"}
}
```

**但我们已经测过这个 body 组合** —— 返回 A0002 失败。

### 遗留瓶颈

测试过程中 **9087 SESSION + SSO 链全部过期**，所有接口返回 `GS52010103E0302 用户认证失败`。`refresh_token` 报告 `SESSIONFORTYRZ 已过期，需重新扫码`。

**假设：** 服务端对 `register/establish/*` 接口有**额外授权检查** — 可能要求当前 Session 已经经过 `portal → matters/operate(108) → core.html` 的完整跳转链，而不是协议级直连。Phase 1 用 `session_bootstrap_cdp` 经由真实浏览器走一遍 guide/base 来 "激活" 这类接口，也暗示了同样的机制。

### 下一步方向

- **恢复 session**：用户扫码重新登录（`system\login_qrcode_pure_http.py full_login`）。
- **session 活着的时候继续实验**：需要保持 session 活跃状态下测试"btnCode=108 → establish"的协议路径，或 CDP bootstrap 让浏览器走一遍后立即切回协议层。
- **Phase 2 前 9 步已 PROVEN**：加密、字典、session、全流程，可复用到任何新案件。

### 🎯 2026-04-23 中午突破：通过 CDP + 真实浏览器 + mitmproxy 抓到创建 busiId 的关键 API！

**操作流程：** 启动专用 Edge Dev（CDP port 9225 + mitm 代理 8080 + 独立 user-data-dir），重新扫码登录 → 在浏览器手动点击"有为风 → 进入设立登记"→ 进入 BasicInfo 页 → 填三个必填字段（出资方式/从业人数/联系电话）→ 点"保存至下一步"。

**mitm 抓到的完整协议链：**

| ts | API | body.busiId | resp.busiId | 意义 |
|---|---|---|---|---|
| 1776906394632 | `matters/operate btnCode=108 dealFlag=before` | name_busi_id | - | 预判 |
| 1776906394755 | `matters/operate btnCode=108 dealFlag=operate` | name_busi_id | - | 正式触发进入设立 |
| 1776906395455 | `register/establish/loadCurrentLocationInfo` | — | null | session 切到设立态 |
| 1776906396167 | `register/establish/component/BasicInfo/loadBusinessDataInfo` | null | null | 读 BasicInfo 页 |
| 1776906396493 | `register/establish/component/Residence/freeBusinessAreaList` | — | — | 地址字典 |
| 1776906396523 | `register/establish/component/Residence/isFreeBusinessArea` | — | — | 地址校验 |
| 1776906396638 | `register/establish/component/ManyCertRegistration/loadBusinessInfoList` | null | null | 多证合一 |
| 1776906396640 | `register/establish/component/OpManyAddress/loadBusinessInfoList` | null | null | 多地址 |
| 1776907003557 | **`BasicInfo/operationBusinessDataInfo` (第1次)** | null | null | 失败警告 |
| **1776907006014** | **`BasicInfo/operationBusinessDataInfo` (第2次)** | null | **2047122548757872642** | **✅ 创建设立 busiId！** |
| 1776907006520 | `MemberPost/loadBusinessDataInfo` | 新 busiId | 新 busiId | 进入第二组件 |

**结论：设立 busiId 由 `BasicInfo/operationBusinessDataInfo` (第一次成功 save) 创建！**

所有字段见 `dashboard/data/records/phase2_establish_info.json`。

关键字段：
- `entPhone`：RSA 加密（同 Phase 1 身份证算法）
- `busiAreaData`：URL 编码的 JSON（含 I3006 软件开发条目）
- `entDomicileDto`：完整地址结构体
- `flowData.busiId: null` 但 `nameId: <已知>` → 服务端据此判定"初次保存，分配新 busiId"
- `linkData.busiCompUrlPaths: "%5B%5D"` (空数组 URL 编码)
- `signInfo: "-1607173598"` (和 Phase 1 同一签名值)
- `itemId: ""` (空字符串)

### 🎯 2026-04-23 下午突破：MemberPost 组件协议化成功 + CDP 交互关键点

**成就：** 完整拿到从 portal "继续办理" → 打开 core.html 新 tab → MemberPost save 的全链路突破，MemberPost save 已协议化（pure HTTP）。

**关键技术突破点：**

1. **CDP Input.dispatchMouseEvent 绕过 popup blocker**：`window.open` 被 Edge 拦截，`location.href`/`Page.navigate` 被 Vue router 回退到 portal。但**真实鼠标坐标点击**"继续办理"按钮 → 浏览器接受为"用户行为"，合法 `window.open` 打开 core.html 新 tab（`core.html#/flow/base/member-post`）。

2. **DOM.setFileInputFiles 上传身份证**：
   - 必须先 `DOM.getDocument(depth=-1, pierce=true)` 初始化前端节点 tree
   - `Runtime.evaluate "document.querySelectorAll('input[type=file]')[idx]"` 取 objectId
   - `DOM.requestNode(objectId)` → nodeId
   - `DOM.setFileInputFiles(nodeId, files=[绝对路径])` 上传
   - 再 `Runtime.evaluate` 触发 `input.dispatchEvent(new Event('change', {bubbles: true}))` 让 Element UI 识别文件

3. **清除 MessageBox 遮罩**：Element UI MessageBox 的 `.v-modal` 遮罩会阻止后续点击。用 `document.querySelectorAll('.el-message-box, .v-modal, .el-message-box__wrapper').forEach(el=>el.remove())` 强删。

4. **MemberPost 组件 save 的 isAgree 字段**：MemberPost VM 有 `isAgree: false` data，对应"我已阅读并同意"。不是 DOM checkbox（前端没渲染），需通过 Vue 直接 `vm.isAgree = true`。

5. **pkAndMem postCode 数组/字符串统一**：服务端 save body 里 postCode **是字符串**（"FR05,WTDLR,LLY,CWFZR" 逗号分隔），不是数组。但 Vue 组件内部状态可能是数组。修改时注意类型。

6. **添加角色成员**：设立为个人独资，黄永裕同时担任 FR05（投资人）、WTDLR（委托代理人）、LLY（联络员）、CWFZR（财务负责人）。`pkAndMem` 需为**每个角色**都添加该成员对象的副本（深拷贝），每个副本的 postCode 字段相同，包含全部角色代码。

**成功的协议化 MemberPost save body（模板+修改）：**

```json
{
  "entName": "有为风（广西容县）软件开发中心（个人独资）",
  "board": "0",
  "boardSup": "0",
  "pkAndMem": {
    "FR05":  [{...黄永裕, postCode: "FR05,WTDLR,CWFZR,LLY", cerNo: "<RSA>", ...}],
    "WTDLR": [{...同一人副本}],
    "CWFZR": [{...同一人副本}],
    "LLY":   [{...同一人副本}]
  },
  "flowData": {"busiId": "2047122548757872642", "entType": "4540", "busiType": "02", "currCompUrl": "MemberBaseInfo", "status": "10", ...},
  "linkData": {"compUrl": "MemberPost", "opeType": "save", "compUrlPaths": ["MemberPost"], "busiCompUrlPaths": "%5B%5D", "token": ""},
  "signInfo": "-1607173598",
  "itemId": ""
}
```

响应：`code=00000, resultType=0, linkDataCompUrl=MemberPost, currCompUrl→MemberBaseInfo`

**已协议化的完整链：**

| # | API | 作用 |
|---|---|---|
| 1 | `matters/operate btnCode=108` | 进入设立态，返回 route |
| 2 | `establish/loadCurrentLocationInfo` | Session 切到设立态 |
| 3 | `BasicInfo/operationBusinessDataInfo` | **创建 busiId** |
| 4-7 | Residence/OpManyAddress/ManyCert load | 字典并发查询 |
| 8 | **`MemberPost/operationBusinessDataInfo`** | **保存成员架构** |

**剩余协议化待完成：** MemberBaseInfo、MemberPool、PersonInfoRegGT、ChargeDepartment、Rules、ComplementInfo 等 20+ 组件。

---

## 五、踩坑记录

### 坑 1：session cookies 缺失 → 未认证

**现象**：Token 存活（`--check` OK），但调 Phase 2 接口返回 `GS52010103E0302 用户认证失败`。

**根因**：Phase 2 接口除 Authorization 外还校验 9087 SESSION cookie。旧版登录脚本未保存 cookies。

**解决**：重新扫码 + 升级 ICPSPClient 自动加载 `http_session_cookies.pkl`。

### 坑 2：A0002 服务端异常（step 7 首次）

**现象**：step7 第一次跑返回 `code=A0002, msg=服务端异常`。

**根因**：请求 body 缺 `isPromiseLetterFlag='1'` 字段，agent 对象只有 14 字段，样本有 24 字段。

**解决**：补齐 agent 的 `mobile`(RSA)、`keepStartDate`、`keepEndDate`、`modifyMaterial` 等字段 + 顶层 `isPromiseLetterFlag='1'`。

修复后响应变成 `code=00000, rt=1`（警告而非错误）。

### 坑 3：经营范围 id 失效

**现象**：rt=1 警告"【软件开发】已发生变化"。

**根因**：前端字典是从 API 动态加载，id `I3006` 可能在新字典中已替换。

**下一步**：从前端 JS runtime 或 API 拉最新的 businessItem 字典，或从服务端返回的旧 businessArea 加密值解密学习正确格式。

---

## 六、文件索引

| 文件 | 用途 |
|---|---|
| `system/phase2_protocol_driver.py` | Phase 2 主驱动器 |
| `system/icpsp_crypto.py` | RSA/AES 加密实现 |
| `system/icpsp_api_client.py` | HTTP client（已升级支持 session cookies） |
| `system/_phase2_recon.py` | Phase 2 API 侦查 |
| `system/_phase2_dump_samples.py` | 从 mitm 提取 Phase 2 样本 |
| `system/_phase2_extract_sysparam_keys.py` | 拉取系统参数（含 aesKey） |
| `system/_phase2_decrypt_server_resp.py` | 解密服务端返回的加密数据 |
| `dashboard/data/records/phase2_samples.json` | Phase 2 API 请求/响应样本 |
| `dashboard/data/records/phase2_protocol_driver_latest.json` | 最新运行结果 |
| `dashboard/data/records/sysparam_snapshot.json` | 957 条系统参数快照 |
