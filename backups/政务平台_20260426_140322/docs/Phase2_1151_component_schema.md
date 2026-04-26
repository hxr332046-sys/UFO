# Phase 2 组件架构 — 1151 有限责任公司（自然人独资）

> 来源: 实时设立流程 + 已完成记录 id=824177927
> 提取时间: 2026-06-21
> busiType=02, entType=1151, ywlbSign=4

## 一、实时设立流程组件列表（SPA 侧栏验证）

从 core.html `#/flow/base/basic-info` SPA 侧栏提取，共 14 个 fill 组件：

| # | compUrl | SPA 显示名称 | 来源 |
|---|---------|------------|------|
| 1 | **BasicInfo** | 基本信息 | loadCurrentLocationInfo |
| 2 | **MemberPost** | 成员架构 | loadCurrentLocationInfo |
| 3 | **MemberPool** | 成员信息 | loadCurrentLocationInfo |
| 4 | **ComplementInfo** | 补充信息 | BasicInfo save 后动态出现 |
| 5 | **Rules** | 章程 | BasicInfo save 后动态出现 |
| 6 | **BankOpenInfo** | 银行开户 | loadCurrentLocationInfo |
| 7 | **MedicalInsured** | 医保登记 | loadCurrentLocationInfo |
| 8 | **Engraving** | 刻制印章 | loadCurrentLocationInfo |
| 9 | **TaxInvoice** | 税务信息填报 | BasicInfo save 后动态出现 |
| 10 | **SocialInsured** | 社保信息 | loadCurrentLocationInfo |
| 11 | **GjjHandle** | 公积金 | loadCurrentLocationInfo |
| 12 | **SlUploadMaterial** | 材料补充 | loadCurrentLocationInfo |
| 13 | **BusinessLicenceWay** | 营业执照领取 | BasicInfo save 后动态出现 |
| 14 | **YbbSelect** | 云帮办流程模式选择 | BasicInfo save 后动态出现 |

processVo 步骤：nameshow → fill → confirm → preTrial → signature → audit → notification → busiLicense

## 二、processVo.stepList（loadCurrentLocationInfo 返回）

| step | stepName | compList |
|------|----------|----------|
| nameshow | 名称信息展示 | NameInfoDisplay |
| fill | 填报 | BasicInfo, MemberPost, MemberPool, BankOpenInfo, MedicalInsured, Engraving, SocialInsured, GjjHandle, SlUploadMaterial |
| confirm | 信息确认 | (empty) |
| preTrial | 信息预审 | (empty) |
| signature | 电子签章 | (empty) |
| audit | 信息审核 | (empty) |
| notification | 告知书 | (empty) |
| busiLicense | 营业执照 | (empty) |

## 三、已完成记录 processVo（id=824177927）

| step | compList |
|------|----------|
| nameshow | NameInfoDisplay |
| fill | BasicInfo, MemberPost, MemberPool, ComplementInfo, Rules, MedicalInsured, TaxInvoice, YjsRegPrePack, SlUploadMaterial, BusinessLicenceWay, YbbSelect |
| sign | ElectronicDoc |
| submit | SubmitSuccess |
| notice | RegNotification |
| licence | RegBusiLicence |

## 四、关键 API 协议发现

### 4.1 flowData 模板（设立流程）
```json
{
  "busiId": null,          // 首次 save 前为 null，save 后服务端分配
  "entType": "1151",
  "busiType": "02",        // 注意：不是 "02_1"！
  "ywlbSign": "4",         // 名称入口用 "4"
  "nameId": "<nameId>",
  "currCompUrl": "<component>",
  "status": "10"
}
```

### 4.2 linkData 模板
```json
{
  "compUrl": "<component>",
  "opeType": "save",       // save 时需要
  "compUrlPaths": ["BasicInfo", ...],
  "busiCompUrlPaths": "%5B%5D",
  "token": "",
  "continueFlag": "continueFlag"  // save 时用 "continueFlag"，load 时用 ""
}
```

### 4.3 signInfo
- **非固定值**！BasicInfo save 时为 `"173417945"`
- 从 loadBusinessDataInfo 响应的 `busiData.signInfo` 获取
- 每次 save 后更新

### 4.4 BasicInfo save 请求体结构（2862 bytes，已捕获）
关键字段：
- `regOrg/regOrgName`: 登记机关
- `entPhone`: **RSA 加密** 后的手机号
- `busiAreaData`: **URL-encoded JSON** 经营范围数据
- `entDomicileDto`: 住所信息对象
- `businessArea`: 经营范围文本
- `signInfo`: 从 load 响应获取

### 4.5 会话安全机制
- busiId 绑定服务端会话，**非 token 级别**
- 必须按顺序调用：loadCurrentLocationInfo → load → save → 下一组件 load
- 跨会话直接调用 busiId 会返回 D0021
- SPA 内 fetch 也受此限制

### 4.6 进入设立流程路径
```
portal.html#/company/my-space/space-index
  → 点击"继续办理" → window.open
  → core.html#/flow/base?busiType=01_4&entType=1151
  → 名称成功页 → 点击"继续办理设立登记"
  → core.html#/flow/base/basic-info
```

## 五、与 4540 个人独资的差异

| 组件 | 1151 有限公司 | 4540 个人独资 | 差异说明 |
|------|--------------|--------------|----------|
| BasicInfo | ✅ | ✅ | 1151 多了设立方式、核算方式等字段 |
| **MemberPost** | ✅ | ❌ | 有限公司：董事/监事/高管组织架构 |
| **MemberPool** | ✅ | ❌ | 有限公司：成员信息列表 |
| PersonInfoRegGT | ❌ | ✅ | 个人独资：投资人信息 |
| ComplementInfo | ✅ | ✅ | 相同 |
| **Rules** | ✅ | ❌ | 有限公司：决议及章程 |
| **BankOpenInfo** | ✅ | ? | 银行开户 |
| **MedicalInsured** | ✅ | ❌ | 医保登记 |
| **Engraving** | ✅ | ? | 刻制印章 |
| TaxInvoice | ✅ | ✅ | 相同 |
| **SocialInsured** | ✅ | ? | 社保信息 |
| **GjjHandle** | ✅ | ? | 公积金 |
| SlUploadMaterial | ✅ | ✅ | 相同 |
| BusinessLicenceWay | ✅ | ✅ | 相同 |
| YbbSelect | ✅ | ✅ | 相同 |

## 六、成员数据模型（member-base-info-index form）

```
naturalFlag, name, nationalityCode, nationalityCodeName, cerType, cerNo,
encryptedCerNo, permitType, permitCode, postCode (角色数组),
comeNameFlag, fzSign, homeAddress, personImgDto{uuidzm, uuidfm},
pkAndMem, delPostCode, id, sexCode, nation, nationName, birthday,
certificateGrantor, signDateStart, signDate, effectiveFlagTim,
ocrFlag, isLoginInfo, invType
```

角色代码：GD01=股东, DS01=董事, JS01=监事, CWFZR=财务负责人, FR01=法定代表人, LLY=联络员, WTDLR=委托代理人

验证要求：**必须上传身份证正反面照片** (`personImgDto.uuidzm/uuidfm`)

## 七、当前状态

- 名称 "泽昕（广西容县）科技有限公司" 已通过 → 设立流程已进入
- 设立 busiId=2047225160991752194 (BasicInfo 保存后分配)
- nameId=2047218022607474690
- **BasicInfo 已保存成功** ✅
- **MemberPost 阻塞**：成员黄永裕需要上传身份证照片才能通过验证
- 剩余 12 个组件待测试

## 八、关键文件

| 文件 | 用途 |
|------|------|
| `dashboard/data/records/1151_establish_structure.json` | 完整 processVo 结构 |
| `dashboard/data/records/1151_basicinfo_operation_body.json` | BasicInfo save 请求体 |
| `dashboard/data/records/1151_establish_reload_intercept.json` | BasicInfo 加载时 24 个 API 请求 |
| `dashboard/data/records/1151_basicinfo_save_all.json` | BasicInfo save 后的 API 调用链 |
| `dashboard/data/records/1151_establish_chain_intercept.json` | 组件链 API 截获 |
