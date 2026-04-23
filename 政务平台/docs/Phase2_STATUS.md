# Phase 2 当前进度与快速续传指南

**更新**：2026-04-23 晚
**当前状态**：已推进到 `SlUploadMaterial`（材料补充上传页），卡在"租赁合同"上传的 fileId 绑定

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
| 13 | **SlUploadMaterial** | 当前位置，卡在文件上传绑定 | ⏸️ |

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

## 三、下次要做的组件（按流程顺序）

1. **SlUploadMaterial** ⏸️ (当前) — 租赁合同上传 fileId 需绑定到 Vue state
2. **BusinessLicenceWay** — 营业执照领取方式
3. **YbbSelect** — 云帮办流程选择
4. **PreElectronicDoc** — 信息确认
5. **PreSubmitSuccess** — 预提交成功 ← **用户要求停在这里**
6. ElectronicDoc / SubmitSuccess / RegNotification / RegBusiLicence（实际提交后阶段）

## 三-补、已证明的推进模式

点"保存并下一步"按钮会触发一系列 API 调用：
- `<当前组件>/operationBusinessDataInfo` (save)
- `<下一组件>/loadBusinessDataInfo` (自动 load 下一组件)

所以只要**前一组件 save 成功**（服务端业务校验通过），前端自动推进到下一组件。

---

## 三-后、SlUploadMaterial 卡点分析

**问题**：`DOM.setFileInputFiles` 对 Element UI 的 `<el-upload>` 不起作用（Element UI 使用自定义 `http-request`）。

**已尝试**：
1. ❌ DOM.setFileInputFiles + dispatchEvent('change')
2. ❌ 直接在 DOM 上 click
3. ⚠️ 调 `ElUpload.handleStart(file)` —— 加入 uploadFiles (status=ready) 但不触发 POST
4. ✅ 调 `upload-inner.post(file)` —— **成功触发 upload API 200 OK**
5. ⚠️ 但文件未绑定到 `sl-upload-material.businessDataInfo`（fileId 没回填）

**下次方案**（任选）：
- A. 用户手动在浏览器点上传按钮选文件
- B. 继续研究 `sl-upload-material.businessDataInfo.data` 结构，手动把 upload 响应的 fileId 填到对应 material 槽位
- C. 拦截 Element UI 的 onSuccess 回调，手动调用

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
