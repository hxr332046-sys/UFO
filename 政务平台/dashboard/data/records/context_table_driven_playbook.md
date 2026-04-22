# 上下文保持与表格驱动作战手册（02_4 / 4540）

## 目标

- 把“空转点击”改成“上下文可追踪、动作可判定、失败可恢复”的执行体系。
- 让 `guide/base -> name-check-info -> ... -> 云帮办流程模式选择` 每一步都有明确判定标准。

## 核心原则

- 先判态再动作：每一步先读状态签名（hash + errors + textHint）。
- 一态一策：同一个状态签名下，不重复执行同一个动作。
- 以业务码为准：优先看接口返回码，不以页面文案作为最终判断。
- 上下文优先：`busiId/nameId/itemId` 缺失时，禁止盲目推进下一页。

## 表1：流程状态表（State Table）

| step_code | route/hash | enter_guard | exit_guard | next_step |
|---|---|---|---|---|
| S00_GUIDE_BASE | `#/guide/base` | 页面可见“市场主体类型/是否申请名称/所在地” | 成功拿到 route 或跳转 core | S10_NAMECHECK |
| S10_NAMECHECK | `#/flow/base/name-check-info` | name-check 页面加载完成 | 无校验错误且提交后进入下一步组件 | S20_BASIC_INFO |
| S20_BASIC_INFO | `#/flow/base/basic-info` | 基本信息表单可见 | 提交成功并路由进入成员/下一节点 | S30_MEMBER_OR_NEXT |
| S30_MEMBER_OR_NEXT | `#/flow/base/member-post` 等 | 成员/岗位区域可见 | 保存并下一步成功 | S40_YUNBANGBAN |
| S40_YUNBANGBAN | 包含“云帮办流程模式选择” | 页面出现目标文案 | 达成 | DONE |

## 表2：上下文字段表（Context Field Table）

| field | source | required_at_step | validate_rule | 备注 |
|---|---|---|---|---|
| `busiId` | route/API | S10+ | 非空字符串 | 缺失则大概率 `A0002` |
| `nameId` | name-service/API | S10+ | 非空且未过期 | 过期常见 `GS52010400B0017` |
| `itemId` | route/API | S10+ | 非空优先 | 某些 flowSave/next 分支依赖 |
| `entType` | query + vm | S00+ | `4540` | 丢失会触发“企业类型不能为空” |
| `busiType` | route/query | S00+ | 与链路一致 | 与实例上下文一致性要求高 |
| `distCode` | UI选择/VM | S10 | 行政区划编码有效 | 必须与名称前缀一致 |
| `streetCode` | UI选择/VM | S00/S10 | 街道编码有效 | 常作为必填联动 |
| `namePre` | UI | S10 | 非空 | 行政区划前缀 |
| `nameMark` | UI | S10 | 非空且合法 | 可能触发禁限用词检查 |
| `industry`/`industrySpecial` | UI建议项 | S10 | 非空 | 常见“主营行业不能为空” |
| `organize`/`organizeName` | UI组件 + VM | S10 | 非空且组件态一致 | 只写 code 不一定过 |
| `isCheckBox` | UI勾选 | S10 | `Y` | 名称须知勾选 |
| `declarationMode` | VM | S10 | `Y` | 与勾选状态联动 |

## 表3：错误码策略表（Error Code Decision Table）

| code | layer | meaning | action | cooldown |
|---|---|---|---|---|
| `A0002` | backend | 服务端异常/上下文不完整 | 立即转“补上下文”流程，检查 `busiId/nameId/itemId` | 5-10 分钟后单次重试 |
| `GS52010400B0017` | backend | 名称保留期限超期 | 放弃旧 `nameId`，转“新 nameId 获取” | 视服务恢复后再试 |
| `GS52011001A0015` | 3rd(企名宝) | 企名宝不可用 | 停止高频动作，仅做可用性探测 | 10+ 分钟 |
| `C0400` | backend | 参数缺失/非法 | 按字段表回填必填项，单次复试 | 立即一次 |
| `D0020` | backend | 越权访问 | 回到合法 route 上下文重建实例 | 5 分钟 |

## 表4：动作策略表（Action Policy Table）

| state_signature (示例) | allowed_actions | forbidden_repeat | success_signal |
|---|---|---|---|
| `#/flow/base/name-check-info + 错误:请选择组织形式` | `fix_org` -> `submit_once` -> `chain_submit` | 同签名重复 `submit_once` | 组织形式错误消失且产生有效请求 |
| `#/flow/base/name-check-info + 文案:主营行业不能为空` | `fix_industry` -> `submit_once` | 同签名重复 `fix_industry` | 行业错误消失 |
| `#/flow/base/name-check-info + 无错误但不跳转` | `capture_network` -> `chain_submit` -> `rebind_context` | 连续点击保存并下一步 | 出现 `/icpsp-api/` 请求且返回成功 |
| `#/guide/base` | `ensure_type` -> `ensure_name_mode` -> `next_once` | 连续多次 `next_once` | 路由切到 core |

## 最小执行循环（人工可控）

1. 截图 + 读取状态签名。  
2. 查“动作策略表”选一个未执行动作。  
3. 执行动作后等待约 5 秒。  
4. 再截图 + 对比状态签名。  
5. 若未变化，换动作，不重复。  
6. 若出现业务码，按“错误码策略表”分支处理。  

## 落地建议（直接用于当前仓库）

- 把“状态签名 + 动作历史 + 截图路径 + 返回码”统一写入同一 JSON 记录。
- 每轮只允许 1 次“提交型动作”（如 `save_next/flowSave/nameCheckRepeat`）。
- 遇到外部服务异常（如企名宝）时，切到“探测模式”，不要继续推进主链路。

