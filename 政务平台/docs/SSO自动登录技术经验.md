# SSO 自动登录技术经验文档

> 最后更新：2026-04-22  
> 状态：**已验证可复现**，冷启动全自动完成

---

## 一、系统架构概览

```
浏览器 (Edge Dev + CDP 9225)
    │
    ├─ 9087 业务门户 (SPA)  ← 最终目标：拿到 Authorization token
    ├─ 6087 TopIP 门户      ← SSO 中枢，SESSION cookie 在此域
    ├─ tyrz SSO 统一认证    ← 账号密码 + 滑块验证
    └─ ssc.mohrss.gov.cn    ← 社保卡扫码二次验证（需拦截绕过）
```

### 完整 SSO 重定向链

```
9087/enterprise-zone
  → 6087/sso/authLogin
    → tyrz/am/oauth2/authorize
      → tyrz/am/auth/login          ← 用户在此填写账号密码 + 滑块
        → tyrz/am/oauth2/authorize   ← 登录成功后自动跳转
          → 6087/TopIP/sso/oauth2?code=xxx  ← 6087 处理 code，设置 SESSION cookie
            → ssc.mohrss.gov.cn      ← 【拦截点】社保卡扫码页
              → (被我们 302 到 6087 portal)
                → 9087/entservice    ← 用 6087 SESSION 换取 9087 Authorization
                  → 9087/portal.html?Authorization=xxx  ← 最终 token
```

---

## 二、核心技术栈

| 组件 | 用途 |
|------|------|
| Chrome DevTools Protocol (CDP) | 浏览器自动化，WebSocket 通信 |
| CDP Fetch Domain | 请求拦截，重定向 ssc 页面 |
| CDP Storage Domain | 跨域清除 localStorage（无需导航） |
| OpenCV (cv2) | 滑块缺口检测（模板匹配） |
| websocket-client | 原始 WebSocket 连接（Fetch 阶段专用） |

### 关键文件

| 文件 | 说明 |
|------|------|
| `system/cdp_auto_slider_login.py` | 主登录脚本，一键执行 |
| `system/_login_fetch_v2.py` | 独立验证脚本（最先跑通的版本） |
| `system/_clean_state.py` | 轻量清除工具（cookies + localStorage） |
| `scripts/launch_browser.py` | 启动带 CDP 的浏览器 |
| `config/credentials.json` | 凭证文件（用户名/密码） |
| `packet_lab/out/runtime_auth_headers.json` | token 输出文件 |

---

## 三、执行流程详解

### Step 1：清除认证状态

```python
# 清除所有相关域的 cookies
cdp.send("Network.getAllCookies")
# 遍历删除 scjdglj / zwfw / mohrss 域的所有 cookie

# 清除 localStorage（关键：无需导航到对应域）
cdp.send("Storage.clearDataForOrigin", {
    "origin": "https://zhjg.scjdglj.gxzf.gov.cn:9087",
    "storageTypes": "local_storage,session_storage",
})
```

### Step 2：触发 SSO 链

```python
# 必须从 9087 enterprise-zone 发起（不能直接去 tyrz）
cdp.navigate("about:blank")   # 先清空 SPA
cdp.navigate(LOGIN_URL)        # enterprise-zone 入口
# 等待自动重定向到 tyrz SSO 登录页
```

### Step 3：填写凭证

```python
# JS 设值 + 触发 input 事件（让 Vue 框架感知）
cdp.evaluate("document.querySelector('#username').focus(); ...")
cdp.type_text(username, delay_ms=60)  # CDP Input.dispatchKeyEvent 逐字输入
```

### Step 4：滑块验证

```python
# 1. 强制显示滑块图片面板（tyrz 默认 display:none）
# 2. 读取 base64 背景图和滑块图
# 3. OpenCV 带 alpha mask 的模板匹配检测缺口位置
# 4. JS dispatchEvent(MouseEvent) 模拟拖拽（CDP Input 事件不被 tyrz 响应）
# 5. 缓动函数 + 随机抖动模拟人类行为
```

### Step 5：Fetch 拦截（核心难点）

```python
# ⚠ 关键：必须关闭 CDPSession，用全新 raw WebSocket
ws_url = cdp.ws.url  # 保存 WS 地址
cdp.close()           # 关闭 CDPSession

_ws = websocket.create_connection(ws_url, timeout=60)

# 启用 Fetch 拦截
_raw_send("Fetch.enable", {"patterns": [
    {"urlPattern": "*ssc.mohrss.gov.cn*", "requestStage": "Request"},
]})

# JS 点击登录按钮
_raw_ev("document.querySelector('.form_button').click()")

# 等待 ssc 请求被拦截 → 返回 302 到 6087 portal
_ws.send(json.dumps({
    "method": "Fetch.fulfillRequest",
    "params": {
        "requestId": req_id,
        "responseCode": 302,
        "responseHeaders": [{"name": "Location",
            "value": "https://...6087/TopIP/web/web-portal.html#/index/page"}],
        "body": ""
    }
}))

# 关闭 Fetch（_raw_send 内联处理残余 paused 请求）
_raw_send("Fetch.disable")
```

### Step 6：获取 Token

```python
# 等 6087 SPA 加载完成（设置 top-token / SESSION）
time.sleep(8)

# 导航到 entservice 端点
_raw_send("Page.navigate", {
    "url": "https://...9087/icpsp-api/sso/entservice?targetUrlKey=02_0002"
})
time.sleep(10)

# 读取 localStorage 中的 Authorization
auth = _raw_ev("localStorage.getItem('Authorization') || ''")
# → 32 位十六进制 token
```

---

## 四、遇到的问题与解决方法

### 问题 1：CDPSession.send() 吞掉 Fetch 事件

**现象**：启用 Fetch.enable 后，`Fetch.requestPaused` 事件从未被捕获，ssc 拦截失败。

**根因**：`CDPSession.send()` 方法内部有 `while True: recv()` 循环，只匹配 `response.id == request.id`，其他所有 CDP 事件（包括 `Fetch.requestPaused`）被静默丢弃。

```python
# CDPSession.send() 的实现 — 会丢弃非匹配消息
def send(self, method, params=None):
    self._id += 1
    self.ws.send(...)
    while True:
        resp = json.loads(self.ws.recv())
        if resp.get("id") == self._id:  # 只看 id 匹配
            return resp.get("result", {})
        # ← 所有 Fetch 事件在这里被无声丢弃！
```

**解决**：Fetch 阶段**关闭 CDPSession，新建 raw WebSocket 连接**。自定义 `_raw_send()` 函数内联处理 `Fetch.requestPaused` 事件：

```python
def _raw_send(method, params=None):
    ...
    while True:
        msg = json.loads(_ws.recv())
        if msg.get("method") == "Fetch.requestPaused":
            # 内联处理：continue 或 fail
            ...
            continue
        if msg.get("id") == mid:
            return msg.get("result", {})
```

---

### 问题 2：直接构造 tyrz URL 导致 entservice 失败

**现象**：手动拼接 tyrz 登录 URL 并成功登录后，调用 `9087/entservice` 被重定向回 tyrz。

**根因**：9087 服务端在 SSO 发起时（通过 enterprise-zone 入口）会记录 SSO 上下文。如果跳过 9087 直接去 tyrz，9087 没有上下文，后续 entservice 拒绝。

**解决**：**必须从 9087 enterprise-zone 入口发起 SSO**，不能直接构造 tyrz URL。

```
✗ 直接去 tyrz → 登录成功 → entservice 失败（无上下文）
✓ enterprise-zone → 自动 302 到 tyrz → 登录成功 → entservice 成功
```

---

### 问题 3：旧 localStorage 导致 SPA 不触发 SSO 重定向

**现象**：清除 cookies 后导航到 enterprise-zone，9087 SPA 停留在 `/login/404` 或 `/index/enterprise`，不跳转到 tyrz。

**根因**：SPA 从 `localStorage.Authorization` 读取 token，发现存在就认为已登录，不触发 SSO 重定向。单清 cookies 不够。

**解决**：使用 CDP `Storage.clearDataForOrigin` 命令清除指定域的 localStorage，**无需导航到该域**：

```python
cdp.send("Storage.clearDataForOrigin", {
    "origin": "https://zhjg.scjdglj.gxzf.gov.cn:9087",
    "storageTypes": "local_storage,session_storage",
})
```

---

### 问题 4：ssc.mohrss.gov.cn 阻塞整个登录流程

**现象**：tyrz 登录成功后，浏览器跳转到 `ssc.mohrss.gov.cn`（社保卡扫码页），需要用户手动扫码，无法自动化。

**根因**：这是人社部的二次身份验证页面，要求扫描社保卡二维码。但实际上 6087 的 SESSION cookie 在跳转到 ssc **之前**就已经设置好了。

**解决**：使用 CDP Fetch Domain 拦截 ssc 请求，返回 302 重定向到 6087 portal：

```python
Fetch.fulfillRequest({
    requestId: ...,
    responseCode: 302,
    responseHeaders: [{"name": "Location", "value": "6087 portal URL"}],
    body: ""
})
```

---

### 问题 5：Fetch.disable 后残余 paused 请求导致浏览器卡死

**现象**：Fetch 拦截 ssc 后 break 出循环，但浏览器页面无法加载。

**根因**：break 后 Fetch 仍处于 enable 状态，6087 portal 加载时发出的其他请求也被 pause，但从未被 continue 或 fail，浏览器挂起。

**解决**：`_raw_send("Fetch.disable")` 内联处理所有残余 `Fetch.requestPaused` 事件（continue 非 ssc 请求，fail ssc 请求），直到收到 disable 的 response。

---

### 问题 6：tyrz 滑块验证码 CDP Input 事件无效

**现象**：使用 CDP `Input.dispatchMouseEvent` 拖拽滑块，滑块不动。

**根因**：tyrz 的滑块库 (vue-puzzle-vcode 变体) 只监听 DOM `MouseEvent`，不响应 CDP 合成的 Input 事件。

**解决**：通过 JS `dispatchEvent(new MouseEvent(...))` 在 DOM 层面模拟鼠标事件：

```javascript
// mousedown 在滑块元素上
moveBlock.dispatchEvent(new MouseEvent('mousedown', {
    bubbles: true, clientX: ..., clientY: ..., button: 0, buttons: 1
}));

// mousemove 在 document 上（滑块库全局监听）
document.dispatchEvent(new MouseEvent('mousemove', { ... }));

// mouseup 在 document 上
document.dispatchEvent(new MouseEvent('mouseup', { ... }));
```

---

### 问题 7：滑块图片面板默认隐藏

**现象**：读取 `img.backImg` 的 `naturalWidth` 为 0，图片无法用于 OpenCV 匹配。

**根因**：tyrz 滑块库将图片容器 `.verify-img-out` 设为 `display:none`，鼠标悬停时才显示。CDP 自动化无法触发 hover。

**解决**：通过 JS 强制显示图片面板后再读取：

```javascript
imgOut.style.display = 'block';
imgOut.style.position = 'absolute';
imgOut.style.bottom = '65px';
imgOut.style.zIndex = '99999';
```

---

### 问题 8：滑块连续失败后图片返回空

**现象**：`bg=0` bytes，OpenCV 解码失败。

**根因**：tyrz 服务端限流，连续失败多次后图片接口返回空数据。

**解决**：等待 30-60 秒后重试，限流会自动恢复。脚本内置 5 次尝试机制。

---

## 五、滑块识别算法

```python
# 1. 优先使用带 alpha mask 的模板匹配（适配非矩形拼图块）
mask = block_rgba[:, :, 3]  # alpha 通道作为 mask
result = cv2.matchTemplate(bg_gray, block_gray, cv2.TM_CCORR_NORMED, mask=mask)

# 2. Fallback：Canny 边缘检测 + 模板匹配
bg_edges = cv2.Canny(bg_gray, 100, 200)
block_edges = cv2.Canny(block_gray, 100, 200)
result = cv2.matchTemplate(bg_edges, block_edges, cv2.TM_CCOEFF_NORMED)

# 3. 坐标换算：图片坐标 → 屏幕拖拽距离
scale = bgDisplayWidth / bgNaturalWidth
drag_px = gap_x * scale + random.uniform(-2, 2)
```

成功率约 **50-60%**，5 次尝试内通常至少成功 1 次。

---

## 六、使用方法

```bash
# 1. 启动浏览器
python scripts/launch_browser.py

# 2. 执行自动登录（从零到 token）
python system/cdp_auto_slider_login.py

# 3. 仅同步已有 token
python system/cdp_auto_slider_login.py --sync-only

# 4. 探测模式（不执行操作）
python system/cdp_auto_slider_login.py --dry-run

# 5. 手动清除状态
python system/_clean_state.py
```

### 输出示例

```
[login] 清除所有 auth 状态，通过 enterprise-zone 触发 SSO...
[login] about:blank → enterprise-zone 全量跳转...
  [1/15] https://tyrz.zwfw.gxzf.gov.cn/am/auth/login?...
[login] 在 SSO 登录页
[login] 填入凭证...
[login] 自动滑块验证...
  [slider] 尝试 1/5...
  [slider] ✓ 验证成功!
[login] 启用 Fetch 拦截 ssc.mohrss.gov.cn...
[login] 点击登录...
[login] 等待 ssc 拦截...
[login] 通过 SSO entservice 获取 9087 token...
[login] ✓ 登录成功! token=6ddac7a1... (len=32)
[sync] Token synced to .../runtime_auth_headers.json
```
