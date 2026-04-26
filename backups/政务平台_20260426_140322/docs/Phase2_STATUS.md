# Phase 2 当前进度与快速续传指南

**更新**：2026-04-23 深夜
**当前状态**：已推进到 `PreElectronicDoc`（信息确认页），再一步就是 **PreSubmitSuccess** 🎯
**关键突破**：SlUploadMaterial 文件上传 fileId 绑定完成（`cerno` 小写 ≠ `cerNo` 大写 N）

---

## 一、已完成组件（pure HTTP 协议化 + 前端自动推进）

| # | 组件 | API | 状态 |
|---|---|---|---|
| 1 | matters/operate | `btnCode=108` | ✅ |
| 2 | loadCurrentLocationInfo | POST | ✅ |
| 3 | **BasicInfo** | `/operationBusinessDataInfo` | ✅ **创建 busiId** |
| 4-7 | Residence/OpManyAddress/ManyCert | `load*` | ✅ |
| 8 | **MemberPost** | `/operationBusinessDataInfo` | ✅ **保存成员架构** |
| 9 | **MemberInfo** | `/operationBusinessDataInfo` | ✅ **补投资人+政治面貌+代理机构** |
| 10 | **MemberPool** | `/operationBusinessDataInfo` | ✅ (自动推进) |
| 11 | **ComplementInfo** | `/operationBusinessDataInfo` | ✅ (自动推进) |
| 12 | **TaxInvoice** | `/operationBusinessDataInfo` | ✅ (自动推进) |
| 13 | **SlUploadMaterial** | upload + special(cerno) + save | ✅ **租赁合同上传 + 绑定 fileId** |
| 14 | **BusinessLicenceWay** | `/operationBusinessDataInfo` | ✅ (自动推进) |
| 15 | **YbbSelect** | `/operationBusinessDataInfo` | ✅ 一般流程 (isSelectYbb=0) |
| 16 | **PreElectronicDoc** | 当前位置 | ⏸️ 下一步点"云帮办提交"=PreSubmitSuccess 🎯 |

**跳过的组件**（个人独资不需要）：PersonInfoRegGT, ChargeDepartment, RegMergeAndDiv, WzInfoReport, Rules, BankOpenInfo, MedicalInsured, Engraving, SocialInsured, GjjHandle, WaterNewHandle, GasNewHandle, ElectricNewHandle, NetHandle, CreditHandle, HouseConstructHandle, YjsRegPrePack, YjsRegFoodOp

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

## 三、下次要做的最后一步

**当前在 PreElectronicDoc**（信息确认页），页面有"云帮办提交"按钮。

点击后应当推进到 **PreSubmitSuccess**（预提交成功，用户最终目标）。

协议化做法：
```python
# PreElectronicDoc save 一次 → 前端自动 load 下一组件 PreSubmitSuccess
POST /register/establish/component/PreElectronicDoc/operationBusinessDataInfo
body = {
    "flowData": {...busiId=2047122548757872642, currCompUrl="PreElectronicDoc"...},
    "linkData": {"compUrl": "PreElectronicDoc", "opeType": "save", ...},
    "signInfo": "-1607173598",
    "itemId": ""
}
```

更简单：CDP 真实点击"云帮办提交"按钮（system/_phase2_ci_click_next.py 模板）。

## 三-补、已证明的推进模式

点"保存并下一步"按钮会触发一系列 API 调用：
- `<当前组件>/operationBusinessDataInfo` (save)
- `<下一组件>/loadBusinessDataInfo` (自动 load 下一组件)

所以只要**前一组件 save 成功**（服务端业务校验通过），前端自动推进到下一组件。

---

## 三-后、SlUploadMaterial 完整协议化解法（已验证通过）

```python
# Step 1: 协议化上传文件 → 拿 fileId
POST /icpsp-api/v4/pc/common/tools/upload/uploadfile
headers: Authorization, language=CH
body: FormData { file: <File> }
→ response.data.busiData = "<fileId>"  (uploadUuid)

# Step 2: 协议化绑定 fileId 到 busiId+code (special API)
POST /register/establish/component/SlUploadMaterial/operationBusinessDataInfo
body = {
    "type": "upload_save",
    "code": "176",                 # 租赁合同材料 code (175=住所证明)
    "name": "租赁合同或其他使用证明",
    "cerno": null,                  # ★ 必须小写 n
    "uploadUuid": "<fileId>",
    "zzlx": null,
    "deptCode": null,
    "flowData": {...},
    "linkData": {"opeType": "special", ...},
    "signInfo": "-1607173598",
    "itemId": "176"
}
→ code=00000, resultType=0 ✅

# Step 3: 点击"保存并下一步"推进（前端自动进 BusinessLicenceWay）
```

**关键教训**：
1. `cerno`（小写 n）≠ `cerNo`（大写 N），Element UI 源码用小写，服务端严格匹配。大写会 A0002 服务端异常。
2. Element UI ElUpload 自定义 http-request，`DOM.setFileInputFiles` 无效；正确路径是直接协议化 fetch upload API + 手动调 special API，比走 Vue 更可靠。
3. 关联三步：upload (get fileId) → special (bind to busiId+code) → save (progress)。

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
