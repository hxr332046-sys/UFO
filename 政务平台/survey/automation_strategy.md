# 广西经营主体登记平台 — 自动化策略

## 一、技术架构

```
┌──────────────────────────────────────────────────────┐
│  L0: Vue Router 直跳（最快最稳）                       │
│    vm.$router.push('/index/enterprise/establish')     │
│    → 无需点击导航，直接到达目标页面                      │
├──────────────────────────────────────────────────────┤
│  L1: Element-UI 组件操控（表单填写/选择）               │
│    el-input → querySelector + 赋值 + 触发 input 事件   │
│    el-select → 模拟点击 + 选择选项                      │
│    el-radio → 直接设置 + 触发 change 事件               │
│    el-button → querySelector + click()                 │
├──────────────────────────────────────────────────────┤
│  L2: CDP 网络拦截（API 层面）                          │
│    Fetch.enable → 拦截/记录 API 请求                    │
│    → 逆向业务 API，直接调用后端接口                       │
├──────────────────────────────────────────────────────┤
│  L3: 截图 + OCR 视觉验证（兜底）                        │
│    Page.captureScreenshot → 视觉确认操作结果            │
└──────────────────────────────────────────────────────┘
```

## 二、CDP 控制核心方法

### 2.1 连接浏览器
```python
import requests, websocket, json

CDP_PORT = 9225
pages = requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5).json()
page = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=15)
```

### 2.2 执行 JS
```python
def cdp_eval(ws, js, msg_id=1, timeout=15):
    ws.send(json.dumps({
        "id": msg_id,
        "method": "Runtime.evaluate",
        "params": {"expression": js, "returnByValue": True, "timeout": timeout * 1000}
    }))
    while True:
        result = json.loads(ws.recv())
        if result.get("id") == msg_id:
            return result.get("result", {}).get("result", {}).get("value")
```

### 2.3 Vue Router 页面跳转
```python
cdp_eval(ws, """
    var app = document.getElementById('app');
    app.__vue__.$router.push('/index/enterprise/enterprise-zone');
""")
```

### 2.4 Element-UI 表单操控
```python
# 设置 el-input 值并触发 Vue 响应式
cdp_eval(ws, """
    var input = document.querySelector('.el-input__inner');
    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, 'value'
    ).set;
    nativeInputValueSetter.call(input, '要填入的值');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
""")
```

### 2.5 Element-UI Select 选择
```python
cdp_eval(ws, """
    // 点击 select 触发下拉
    var select = document.querySelector('.el-select .el-input__inner');
    select.click();
    // 等待后选择选项
    setTimeout(function() {
        var options = document.querySelectorAll('.el-select-dropdown__item');
        for (var i = 0; i < options.length; i++) {
            if (options[i].textContent.trim() === '目标选项') {
                options[i].click();
                break;
            }
        }
    }, 500);
""")
```

### 2.6 文件上传（CDP 原生方式）
```python
# 先找到 input[type=file]
cdp_eval(ws, """
    var fileInput = document.querySelector('input[type="file"]');
    // 返回其 backend node id 用于 DOM.setFileInputFiles
""")
# 然后通过 CDP DOM.setFileInputFiles 设置文件
```

### 2.7 截图验证
```python
ws.send(json.dumps({
    "id": 1,
    "method": "Page.captureScreenshot",
    "params": {"format": "png", "quality": 80}
}))
result = json.loads(ws.recv())
# result["result"]["data"] 是 base64 编码的 PNG
```

### 2.8 网络请求拦截
```python
# 启用网络监听
ws.send(json.dumps({"id": 1, "method": "Network.enable", "params": {}}))
# 监听请求和响应
# Network.requestWillBeSent → 记录请求
# Network.responseReceived → 记录响应
```

## 三、自动化优先级

| 优先级 | 场景 | 路由 | 难度 | 说明 |
|---|---|---|---|---|
| **P0** | 办件进度查询 | `/company/my-space/selecthandle-progress` | ⭐ | Router直跳+DOM读取 |
| **P0** | 经营主体列表 | `/company/enterprise-list` | ⭐ | Router直跳+DOM读取 |
| **P0** | 名称查询 | `/index/name-check` | ⭐ | 无需认证，输入+结果读取 |
| **P0** | 经营范围查询 | 首页卡片入口 | ⭐ | 无需认证 |
| **P1** | 设立登记表单 | `/index/enterprise/establish` | ⭐⭐⭐ | 多步表单，需逐步填写 |
| **P1** | 变更备案登记 | `/index/change-registration` | ⭐⭐⭐⭐ | 复杂表单+文件上传 |
| **P1** | 名称自主申报 | `/index/name-check` | ⭐⭐ | 输入+校验+提交 |
| **P1** | 企业开办一件事 | `/index/one-thing-gx` | ⭐⭐⭐⭐ | 多环节集成表单 |
| **P1** | 企业变更一件事 | `/index/change-one-thing` | ⭐⭐⭐⭐ | 多环节集成表单 |
| **P2** | 股权出质业务 | `/index/equity-pledge-processing` | ⭐⭐⭐⭐ | 复杂表单 |
| **P2** | 减资公告 | `/index/capital-reduction` | ⭐⭐⭐ | 表单+公告流程 |
| **P2** | 迁移登记 | `/index/qydj-one-thing` | ⭐⭐⭐⭐ | 多步骤 |
| **P3** | 电子签名 | `/company/enterprise-apply` | ⭐⭐⭐⭐⭐ | 需USB Key硬件 |
| **P3** | 注销登记 | 多步骤 | ⭐⭐⭐⭐ | 含公告期等待 |

## 四、关键技术要点

### 4.1 Element-UI 表单操控注意事项
- `el-input` 必须同时设置 value 并派发 `input`/`change` 事件，否则 Vue 响应式不触发
- 使用 `Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set` 原生 setter
- `el-select` 下拉选项是延迟渲染的，需要先 click 触发下拉，等待 DOM 更新后再选择
- `el-radio`/`el-checkbox` 需要触发 `change` 事件

### 4.2 文件上传
- CDP `DOM.setFileInputFiles` 可直接设置文件路径，无需打开系统对话框
- 不受系统文件对话框阻塞

### 4.3 验证码处理
- 如遇图形验证码，需 OCR 或第三方识别服务
- CDP 可截图验证码区域后送识别

### 4.4 电子签名
- 可能需要 USB Key 等硬件设备
- CDP 无法直接控制硬件，需 UIA/pywinauto 兜底

### 4.5 会话保持
- Cookie/localStorage 在 `C:\Temp\ChromeDevCDP` 中持久化
- 重启浏览器后登录态保留
- 每次启动必须使用相同的 `--user-data-dir` 参数

### 4.6 iframe 处理
- header/footer 是 iframe，主业务在 `#app` 内
- iframe 跨域可能无法通过 JS 访问 contentDocument
- 主业务操作不需要访问 iframe

## 五、API 逆向方向

通过 CDP `Network.enable` 监听所有 XHR/Fetch 请求，可逆向后端 API：
- 基础 URL: `https://zhjg.scjdglj.gxzf.gov.cn:9087/`
- 认证方式: Cookie/Token（从登录态获取）
- 关键 API 路径待抓包分析

逆向 API 后可实现：
- 直接调用后端接口，跳过前端表单
- 批量操作
- 数据导出
