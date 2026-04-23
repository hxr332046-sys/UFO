# Phase 2 当前进度与快速续传指南

**更新**：2026-04-23 下午
**当前状态**：BasicInfo + MemberPost 协议化成功，浏览器已进入 MemberPool 组件

---

## 一、已完成组件（pure HTTP 协议化）

| # | 组件 | API | 作用 |
|---|---|---|---|
| 1 | matters/operate | `btnCode=108` | 返回 route，进入设立 |
| 2 | loadCurrentLocationInfo | POST | Session 切到设立态 |
| 3 | **BasicInfo** | `/operationBusinessDataInfo` | **创建 busiId** |
| 4-7 | Residence/OpManyAddress/ManyCert | `load*` | 字典预加载 |
| 8 | **MemberPost** | `/operationBusinessDataInfo` | **保存成员架构** |

**当前 busiId**: `2047122548757872642`（黄永裕 个人独资）

---

## 二、下次续传入口

### 2.1 读取已有上下文

```powershell
# 最新的完整协议化脚本（参考 body 构造）
g:\UFO\政务平台\system\_phase2_proto_save.py

# 现状开发记录（含所有突破点）
g:\UFO\政务平台\docs\Phase2_开发记录.md
```

### 2.2 恢复浏览器会话

```powershell
# 如果 Edge 已关
$env:EDGE_PROFILE = "C:\Users\13352\AppData\Local\Microsoft\Edge\User Data"
Start-Process "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" -ArgumentList "--remote-debugging-port=9225","--user-data-dir=$env:EDGE_PROFILE"

# 登录 portal（读 IDE 已存 token）
.\.venv-portal\Scripts\python.exe system\portal_ufo.py --check

# 跳到 core.html（#/flow/base/member-pool 应该是当前位置）
```

### 2.3 mitm 监控

```powershell
.\.venv-portal\Scripts\python.exe -m mitmproxy.tools.main --scripts system\mitm_record_ufo.py --listen-port 8082
```

---

## 三、下次要做的组件（按流程顺序）

1. **MemberPool** (当前位置) — 成员池，可能只是 load/show
2. **MemberInfo** — 成员详情
3. **PersonInfoRegGT** — 个人信息登记（可能需要身份证 OCR）
4. **ChargeDepartment** — 监管部门
5. **Rules** — 章程决议
6. **ComplementInfo** — 补充信息
7. **TaxInfo** — 税务信息
8. **MaterialSuppl** — 材料补充
9. **BusinessLicense** — 营业执照领取
10. **CloudFlow** — 云办流程

---

## 四、关键协议片段

### 4.1 通用 save body 骨架

```python
body = {
    "flowData": {
        "busiId": "2047122548757872642",
        "entType": "4540",           # 个体个独
        "busiType": "02",            # 设立
        "currCompUrl": "<CURRENT_COMP>",
        "status": "10",
        "nameId": "2047094115971878913",
        # ... 其他复制自 mitm
    },
    "linkData": {
        "compUrl": "<CURRENT_COMP>",
        "opeType": "save",
        "compUrlPaths": ["<CURRENT_COMP>"],
        "busiCompUrlPaths": "%5B%5D",
        "token": ""
    },
    "signInfo": "-1607173598",       # 固定常量
    "itemId": "",
    # ... 业务字段
}
```

### 4.2 CDP fetch 协议化发送

```python
body_b64 = base64.b64encode(json.dumps(body).encode()).decode()
js = f"""
(function(){{
    window.__r__ = null;
    fetch('/icpsp-api/v4/pc/register/establish/component/<COMP>/operationBusinessDataInfo?t='+Date.now(), {{
        method: 'POST',
        headers: {{
            'Authorization': localStorage.getItem('Authorization'),
            'Content-Type': 'application/json;charset=UTF-8',
            'language': 'CH'
        }},
        body: JSON.stringify(JSON.parse(decodeURIComponent(escape(atob('{body_b64}'))))),
        credentials: 'include'
    }}).then(r=>r.json()).then(j=>{{window.__r__=j;}});
    return 'sent';
}})()
"""
```

---

## 五、CDP 关键技术库（可复用）

```python
# 所有 CDP 脚本模板都在 system/_phase2_cdp_*.py
# 核心类
import websocket

# 打开 tab 并点击 "继续办理"
system/_phase2_cdp_reuse_tab.py

# 上传身份证（DOM.setFileInputFiles）
system/_phase2_cdp_upload_cn.py

# 清除 MessageBox 遮罩 + Vue state 修改
system/_phase2_cdp_patch_postcode.py

# 协议化 fetch save
system/_phase2_proto_save.py
```

---

## 六、下次要问用户的

1. 是否同意 MemberPool 用**同样的 protocolize 策略**（逐组件 fetch + body patch）？
2. 是否要写**通用推进器**（基于 curCompUrl 自动发下一 save）？
3. 剩余身份证 OCR 组件（PersonInfoRegGT）用 Vue state 注入还是真实 OCR 流程？
