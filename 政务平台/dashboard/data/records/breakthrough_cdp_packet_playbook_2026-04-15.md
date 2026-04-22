# 突破技术沉淀：从空转到可判定业务阻断（2026-04-15）

## 结论先行

- 本次有效突破路径是：**CDP + 数据包（API 回包）主导**，不是“模拟点击主导”。
- 点击只用于拿到会话入口或触发一次前端动作；真正决定是否打通的是：
  - 能否拿到可用上下文（`busiId/nameId/itemId/flowData`）
  - 后端接口真实返回码（而非页面文案）
- 通过该路径，阻断从“模糊空转”收敛为明确业务码：
  - `A0002`（服务端异常，泛化阻断）
  - `GS52010400B0017`（名称保留期限超期，旧 `nameId` 失效）
  - `GS52011001A0015`（企名宝服务不可用）

## 为什么之前会空转

- 仅靠页面层“点下一步/保存并下一步”，经常无法判断是：
  - 前端组件态没同步
  - 还是后端上下文缺失
- 页面文案统一显示“服务端异常”，无法定位真实阻断层。
- 一旦没有拿到接口真实回包，调参和重试会变成盲打。

## 这次有效的技术路线

1. **锁定活跃会话上下文**
   - 从 `my-space` 的“继续办理”抓到后端 `route` 回包。
   - 从回包中提取 `busiId/busiType/entType/marPrId/marUniscId`，强制落到可用 `core` 会话。

2. **CDP 注入 + 单次 API 调用**
   - 在同一活跃 `core` 会话中，直接调用：
     - `flow.getLocationInfo`
     - `flow.loadBusinessDataInfo`
     - `NameCheckInfo.operationBusinessDataInfo`
   - 同时挂 `XMLHttpRequest` 采集请求体和响应体（一次一枪，避免轰炸）。

3. **以响应码驱动分支，不以页面文案驱动**
   - `operationBusinessDataInfo` + `nameId=null` -> `A0002`
   - `operationBusinessDataInfo` + 旧 `nameId` -> `GS52010400B0017`
   - 由此确认：**不是点击问题，是 `nameId` 新鲜度问题**。

## 关键证据文件

- `one_shot_continue_click_capture.json`  
  证明“继续办理”动作已触发后台，并回传可用 `route`。
- `one_shot_getlocation_from_live_core.json`  
  证明在活跃 `core` 会话中，`4540` 的 `getLocationInfo/loadBusinessDataInfo` 可 `00000`。
- `one_shot_jump_namecheck_and_operate.json`  
  证明 `NameCheckInfo.operationBusinessDataInfo` 在 `nameId=null` 时返回 `A0002`。
- `one_shot_operate_with_old_nameid_from_live_core.json`  
  证明旧 `nameId` 返回 `GS52010400B0017`（保留期限超期）。
- `one_shot_probe_qmb_and_nameid.json`  
  证明企名宝链路当前不可用，无法铸造新 `nameId`。

## 标准打法（后续复用）

1. 先抓“继续办理”返回的 `route`，抢回可用会话。
2. 进 `core` 后先测 `getLocationInfo/loadBusinessDataInfo` 是否 `00000`。
3. 再打 `operationBusinessDataInfo`，以返回码决定分支。
4. 仅在拿到新 `nameId` 后串联：
   - `operationBusinessDataInfo -> nameCheckRepeat -> flowSave`
5. 全程单次调用、短间隔，不做高频死循环。

## 关于“到底是 CDP+包 还是 模拟点击”

- **主链路：CDP + 数据包。**
- **点击：辅助。** 仅用于获得会话入口（例如“继续办理”）或触发一次 UI 事件。
- 真正的突破是“把问题从 UI 层搬到接口层并拿到可判定业务码”。

