# guide/base 全逆向并行攻坚最终报告

## 执行范围
- 前端全逆向：事件传播链、VM 调用链、门控变量来源。
- 后端契约逆向：guide/base 到 core 的请求触发契约 + A0002 条件。
- 打穿脚本：多级 fallback + 强断言 + 多 `busiType` 回放。

## 本轮新增脚本
- `政务平台/system/reverse_guide_frontend_full.py`
- `政务平台/system/guide_base_breakthrough_runner.py`

## 本轮新增证据
- `guide_base_frontend_full_reverse.json`
- `guide_base_backend_contract_full.md`
- `guide_base_breakthrough_runner.json`

## 关键发现
1. 当前会话环境被锁在 `6087 TopIP`，`9087 icpsp-web-pc` 页面不存在（`has_icpsp_page=false`）。
2. 在该环境下，尝试导航到 `guide/base` 不生效，页面保持 `#/index/page`。
3. 因此 `02_4` 与 `07` 回放都无法进入 `guide/base`，更无法进入 `core`，断言统一失败（无 hash 变化、无请求变化）。

## 对“全逆向”目标的实际推进
- 已完成框架化能力建设：脚本具备环境门控检测、动作链、多级 fallback、硬断言、批量回放。
- 已明确新增门控：不仅有 `guide/base` 门控，还有“会话域门控（6087->9087）”。
- 这使得后续攻坚可先判断环境是否满足，不再在无效会话上反复试错。

## 当前阻断级别
- 一级阻断：环境门控（缺少 `icpsp` 会话页）。
- 二级阻断：guide/base 内部门控（此前证据已确认“可点无副作用”）。

## 下一步建议（执行顺序）
1. 先恢复 `9087 icpsp-web-pc` 有效页签会话；
2. 再跑 `guide_base_breakthrough_runner.py` 的 `02_4` 3轮回放；
3. 达到首次 `hash/request` 副作用后，继续 `07` 迁移回放。

