# 政务平台认证机制分析

## 一、认证方式

**纯 Token 认证，无 Cookie 参与。**

| 认证项 | 存储位置 | 值示例 | 用途 |
|---|---|---|---|
| **Authorization** | localStorage | `2060d9e762d64024a76bb3bea2fb5c09` | API 请求头认证 |
| **top-token** | localStorage | `afa0fc94-b685-4f1a-9eb4-f24ff1b0615d` | 辅助认证（UUID格式） |
| Cookie | — | **无** | 不使用 Cookie 认证 |

## 二、Token 注入方式

API 请求通过 HTTP Header 注入：

```
GET /icpsp-api/v4/pc/common/tools/getCacheCreateTime
Authorization: 2060d9e762d64024a76bb3bea2fb5c09
```

前端 Axios 拦截器从 localStorage 读取 Token 并注入请求头。

## 三、Vuex Store 中的认证状态

```javascript
// Vuex common 模块
state.common.token = "2060d9e762d64024a76bb3bea2fb5c09"
state.common.userInfo = {
    id, username, elename, desensitizeElename,
    elepaper, elepapername, elepapernumber,
    encryptedElepapernumber, tel, encryptedTel,
    email, authflag, mailFlag, pwdFlag, telFlag,
    faceFlag, elderType, languageType, usertype,
    uniScID, marPrId, source, isEntUser, officeCount
}
```

## 四、API 基础路径

```
https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-api/v4/pc/
```

已捕获的 API：
- `GET /icpsp-api/v4/pc/common/tools/getCacheCreateTime` — 获取缓存创建时间

## 五、反向代理可行性

### 5.1 为什么适合做反向代理

1. **Token 认证** — 不依赖 Cookie，代理服务器只需注入 Header
2. **无 SameSite Cookie 限制** — 跨域无障碍
3. **无 CSRF Token** — 不需要额外处理
4. **API 路径固定** — `/icpsp-api/v4/pc/` 前缀明确

### 5.2 反向代理架构

```
客户端 → API网关(localhost:8080) → 政务平台API(9087)
                ↓
         Token管理器（自动从CDP获取+刷新）
         请求缓存（LRU）
         API日志
         CORS处理
```

### 5.3 Token 获取方式

| 方式 | 说明 |
|---|---|
| **CDP 自动获取** | 从已登录的浏览器 localStorage 读取（推荐） |
| **手动指定** | `--token` 参数传入 |
| **持久化** | 自动保存到 `data/tokens.json`，重启后恢复 |

### 5.4 401 自动重试

当上游返回 401 时，网关自动：
1. 从 CDP 刷新 Token
2. 用新 Token 重试请求
3. 对客户端透明

## 六、安全注意事项

- Token 存储在 `data/tokens.json`，需保护该文件
- 代理服务器仅监听 `0.0.0.0`，生产环境应限制为 `127.0.0.1`
- HTTPS 上游使用 `verify=False`，因政务网站可能有自签名证书
- Token 自动刷新依赖 CDP 浏览器保持运行
