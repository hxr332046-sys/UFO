# 全流程普查计划 — 从名称登记到云提交停点

**日期**: 2026-04-23 21:50
**目标**: 重新创建 4540 个人独资企业，从 Phase 1 跑到 PreElectronicDoc（云提交停点）
**案例**: `docs/case_有为风.json` — 有为风（广西容县）软件开发中心（个人独资）
**投资人**: 黄永裕 450921198812051251

---

## 阶段一：环境准备

| # | 步骤 | 工具 | 验证 |
|---|------|------|------|
| 1.1 | 检查 Edge CDP 9225 是否运行 | HTTP GET localhost:9225/json | 返回 tab 列表 |
| 1.2 | 检查登录状态 | portal_ufo.py --check 或 CDP 读 Authorization | token 有效 |
| 1.3 | 如未登录，执行 QR 扫码登录 | login_qrcode.py | 拿到 32-hex token |
| 1.4 | 验证资产文件存在 | 检查 id_front/id_back/lease_contract 路径 | 全部存在 |

## 阶段二：Phase 1 名称登记（纯协议）

| # | 步骤 | API | 验证 |
|---|------|-----|------|
| 2.1 | checkEstablishName | 校验 entType=4540 + distCode=450921 | resultType=0 |
| 2.2 | loadCurrentLocationInfo | 初始化会话 | 返回 flowData |
| 2.3 | NameCheckInfo/loadBusinessDataInfo | 加载名称检查表单 | 返回表单字段 |
| 2.4 | bannedLexiconCalibration | 禁限词校验 | 通过 |
| 2.5 | NameCheckInfo/operationBusinessDataInfo#1 | 首次保存 | resultType=0 |
| 2.6 | NameCheckInfo/nameCheckRepeat | 名称查重 | checkResult |
| 2.7 | NameCheckInfo/operationBusinessDataInfo#2 | 二次保存 → **拿 busiId** | busiId 非空 |
| 2.8 | NameSupplement/loadBusinessDataInfo | 加载补充页 | OK |
| 2.9 | NameShareholder/operationBusinessDataInfo | 保存投资人(RSA) | resultType=0 |
| 2.10 | NameSupplement/operationBusinessDataInfo | 保存补充(AES) | resultType=0 |
| 2.11 | name/submit | 正式提交 | status 10→51 |
| 2.12 | NameSuccess/loadBusinessDataInfo | 拿 nameId | nameId 非空 |

**产出**: busiId + nameId

## 阶段三：Phase 2 进入设立登记

| # | 步骤 | API | 验证 |
|---|------|-----|------|
| 3.1 | matters/operate btnCode=108 (before) | 预判 | 操作成功 |
| 3.2 | matters/operate btnCode=108 (operate) | 进入设立 | 返回 route busiType=02_4 |
| 3.3 | establish/loadCurrentLocationInfo | Session 切到设立态 | processVo |
| 3.4 | BasicInfo/loadBusinessDataInfo | 加载基本信息 | 表单字段 |

## 阶段四：Phase 2 组件逐一推进

| # | 组件 | 做法 | 风险 |
|---|------|------|------|
| 4.1 | **BasicInfo** | save (创建设立 busiId) | entPhone RSA 加密 |
| 4.2 | Residence/OpManyAddress/ManyCert | load 字典 | 并发 |
| 4.3 | **MemberPost** | save 成员架构 (cerNo RSA) | 身份证 UUID 必需 |
| 4.4 | **MemberInfo** | save 投资人详情 | 政治面貌/代理机构/照片 |
| 4.5 | **MemberPool** | fc.save(null,false) 推进 | 绕过5年验证 |
| 4.6 | **ComplementInfo** | save 非公党建 + 自动推进 | 4540无受益所有人 |
| 4.7 | **TaxInvoice** | save 空body 自动推进 | 低 |
| 4.8 | **SlUploadMaterial** | upload→special(cerno小写)→save | cerno 大小写 |
| 4.9 | **BusinessLicenceWay** | save 自动推进 | 低 |
| 4.10 | **YbbSelect** | save isSelectYbb=0 | 低 |
| 4.11 | **PreElectronicDoc** | save → **到达停点** | 🎯 |

## 阶段五：验证与记录

| # | 步骤 | 说明 |
|---|------|------|
| 5.1 | 确认页面到达 PreSubmitSuccess / 云提交文案 | URL + 页面文本 |
| 5.2 | 记录全过程每步的 resultType/msg | JSON 输出 |
| 5.3 | 记录遇到的所有错误和提示 | 用于完善协议库 |
| 5.4 | 不点击"云提交"按钮 | ⛔ 停下 |

---

## 执行方式

优先使用已有的端到端脚本 `run_case_rongxian_to_yun_submit.py`（调用 `packet_chain_portal_from_start.py`），它封装了 Phase 1 + Phase 2 全链路。如果该脚本遇到问题，回退到单步协议化脚本逐步推进。

## 关键铁律

1. **signInfo**: 不是固定值，每次从 loadBusinessDataInfo 响应提取
2. **cerno 小写**: SlUploadMaterial 的 special API 字段名必须小写
3. **单步执行**: 实网环境，禁止死循环和并发请求
4. **前端自动推进**: save resultType=0 后前端自动 load 下一组件
5. **fc.save(null,false)**: MemberPool 需要绕过表单验证直接推进
