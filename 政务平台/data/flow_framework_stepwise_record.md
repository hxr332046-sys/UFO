# 设立登记入口框架分步普查记录

更新时间: 2026-04-14

## 目标

从 `portal 全部服务` 页面起步，不走直达路由，逐步确认每一层页面框架与跳转链路。

## 步骤结果

1. **全部服务页**
   - URL: `portal.html#/index/page?fromProject=core&fromPage=%2Fflow%2Fbase%2Fname-check-info`
   - 组件特征: `index`、`layout`、`header-comp`
   - 关键卡片: `设立登记`、`变更（备案）登记`、`普通注销登记` 等
   - 记录文件: `flow_stepwise_survey.json`

2. **企业专区页（enterprise-zone）**
   - URL: `portal.html#/index/enterprise/enterprise-zone`
   - 组件特征: `enterprise-zone`
   - 可见按钮: `开始办理`（2个）
   - 通过点击 `开始办理` 成功进入下一步
   - 记录文件: `entry_to_guide_survey.json`

3. **without-name 页**
   - URL: `#/index/without-name?entType=1100`
   - 组件特征: `without-name`
   - 调用组件方法: `toNotName()`
   - 结果: 成功进入 `establish`
   - 记录文件: `without_name_step_survey.json`

4. **establish 页**
   - URL: `#/index/enterprise/establish?busiType=02&entType=1100`
   - 组件特征: `establish`
   - 可见按钮: `下一步`
   - 操作: 设置企业类型并执行 `nextBtn()`
   - 结果: 成功进入 `#/flow/base/basic-info`
   - 记录文件: `establish_step_survey.json`

5. **basic-info 页（目标页）**
   - URL: `#/flow/base/basic-info`
   - 组件特征: `flow-control`、`tne-dialog`
   - 说明: 到达后可进入填表/保存测试

## 当前确认的完整入口链路

`全部服务(index/page)` → `企业专区(enterprise-zone)` → `开始办理` → `without-name` → `toNotName()` → `establish` → `nextBtn()` → `flow/base/basic-info`

## 与历史记录对比

- 历史文档已记录核心后半段链路（`without-name -> establish -> basic-info`）。
- 本次补齐了前半段的实测框架确认（`index/page -> enterprise-zone -> 开始办理`）。

## 02_4 链路执行归档（2026-04-14）

按以下 3 个页面完成了逐步执行并留痕：

1. `portal.html#/index/enterprise/enterprise-zone?...&busiType=02_4&merge=Y`
   - 识别并点击 `开始办理`：成功

2. `name-register.html#/namenotice/declaration-instructions?...&entType=1100&busiType=02_4`
   - 识别并点击 `我已阅读并同意`：成功

3. `name-register.html#/guide/base?busiType=02_4&entType=1100&marPrId=&marUniscId=`
   - 识别并点击 `下一步`：成功
   - 点击后出现 `确定` 弹窗按钮（说明进入下一阶段前的确认分支）

执行证据文件：

- `operation_framework_02_4.md`
- `operation_framework_02_4.json`
- `framework_execution_record_02_4.json`
