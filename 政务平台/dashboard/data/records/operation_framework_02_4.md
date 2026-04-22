# 02_4 链路操作框架

## 页面与操作清单

### 1. `https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone?fromProject=portal&fromPage=%2Findex%2Fpage&busiType=02_4&merge=Y`
- 当前哈希: `#/index/enterprise/enterprise-zone?fromProject=portal&fromPage=%2Findex%2Fpage&busiType=02_4&merge=Y`
- 关键动作按钮:
  - 开始办理

### 2. `https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/namenotice/declaration-instructions?fromProject=portal&fromPage=%2Findex%2Fenterprise%2Fenterprise-zone&entType=1100&busiType=02_4`
- 当前哈希: `#/namenotice/declaration-instructions?fromProject=portal&fromPage=%2Findex%2Fenterprise%2Fenterprise-zone&entType=1100&busiType=02_4`
- 关键动作按钮:
  - 我不同意 我已阅读并同意
  - 我不同意
  - 我已阅读并同意

### 3. `https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=1100&marPrId=&marUniscId=`
- 当前哈希: `#/guide/base?busiType=02_4&entType=1100&marPrId=&marUniscId=`
- 关键动作按钮:
  - 下一步

## 建议执行顺序
- 入口页 `enterprise-zone`：关闭提示弹窗 -> 点击“开始办理”
- 说明页 `declaration-instructions`：等待“我已阅读并同意”按钮可点 -> 点击同意/下一步
- 指引页 `guide/base`：选择主体类型、名称是否已申报、所在地区 -> 点击“下一步”
- 进入名称申报成功页后：点击“继续办理设立登记”进入信息填报
- 信息填报页优先处理剩余必填空项，再执行“保存并下一步”
