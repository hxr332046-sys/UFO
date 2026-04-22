# guide/base -> core 后端契约全量逆向

## 1) 契约入口分层
- `guide/base` 层：应触发“下一步/保存类”请求，最小可观测副作用为：
  - hash 变化，或
  - `/icpsp-api/` 请求计数增加
- `core/member-post` 层：可触发 `operationBusinessDataInfo`，但上下文不完整时返回 `A0002`。

## 2) 已观测接口与约束
- `POST /icpsp-api/v4/pc/register/establish/component/MemberPost/operationBusinessDataInfo`
  - 证据：`retry_member_save_with_resp_capture_02_4.json`
  - 回包：`{"code":"A0002","msg":"服务端异常"}`
  - 特征：请求体里 `pkAndMem[*].linkData.*` 多字段为 `null`。

## 3) 最小上下文字段集合（从失败样本反推）
- `flowData`（非空业务上下文）
- `linkData.token`
- `linkData.compUrl`
- `linkData.busiCompUrlPaths`
- `itemId`

说明：`itemId` 存在不代表可通过；若 `linkData` 与 `flowData` 为空，依然可能 `A0002`。

## 4) A0002 触发条件图（逆向结论）
1. 请求已发出；
2. 业务上下文字段缺失（尤其 `linkData`/`flowData`）；
3. 服务端返回 `A0002`。

与之对照：
- 在 `guide/base` 阻断态下，请求根本不发出（属于更前置门控失败）。

## 5) 当前会话前置条件新增
- 当前 CDP 目标仅有 `6087 TopIP` 页面，缺少 `9087 icpsp` 页面上下文。
- 这会导致 guide/base 逆向脚本无法进入真实表单页面，属于“环境门控”。

## 6) 对框架的契约要求
- 先校验会话路由域（是否存在 `icpsp-web-pc` 页签）；
- 不满足则立即停机并归档 `environment_blocked`；
- 满足后才执行 guide/base 动作与断言链。

