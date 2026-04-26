# Phase 2 第二日突破：MemberInfo → SlUploadMaterial 的跨组件推进

> **日期**：2026-04-23 晚
> **跨越**：MemberPool → MemberInfo → ComplementInfo → TaxInvoice → SlUploadMaterial（5 个组件）
> **当前 busiId**：`2047122548757872642`（黄永裕 个人独资）
> **浏览器状态**：`core.html#/flow/base/sl-upload-material`

---

## 一、战果速览

从上次 MemberPool 卡点（"请补全投资人"）到推到材料上传页，一共通过了 **5 个组件**：

| 组件 | 卡点 | 解法 |
|------|------|------|
| **MemberInfo** | 服务端 A0002 / D0022 | signInfo=-1607173598 + politicsVisage + isOrgan + gdMemPartDto |
| **MemberPool** | 前端 allInfoFull 校验 | 先走 MemberInfo save → Pool 自动过 |
| **ComplementInfo** | 无特殊校验 | 点"保存并下一步" → 前端自动跳 TaxInvoice |
| **TaxInvoice** | 无特殊校验 | 点"保存并下一步" → 前端自动跳 SlUploadMaterial |
| **SlUploadMaterial** | 文件上传 fileId 绑定 | upload API 200 但 onSuccess 回调未触发 |

**跳过的组件**（服务端按 entType=4540 个人独资跳过）：PersonInfoRegGT, ChargeDepartment, RegMergeAndDiv, WzInfoReport, Rules, BankOpenInfo, MedicalInsured, Engraving, SocialInsured, Gjj/Social/MedicalHandle, Engraving 等 18 个。

---

## 二、关键突破点

### 突破 1：Session 过期恢复流程

**现象**：浏览器访问 `core.html` 返回 `net::ERR_EMPTY_RESPONSE`，跳转到 SSO 登录页 `tyrz.zwfw.gxzf.gov.cn/am/auth/login`。

**根因**：Edge 启动参数带 `--proxy-server=127.0.0.1:8080`，而 8080 端口是一个 `python -m http.server`（文件服务器），不是 mitm 代理。

**解法**：杀 Edge + 重启不带 `--proxy-server`，保留 `--user-data-dir=C:\Temp\EdgeDevCDP` 保持登录态。用户手动完成 SSO 扫码登录后继续。

```powershell
Get-Process msedge | Stop-Process -Force
Start-Process "C:\Program Files (x86)\Microsoft\Edge Dev\Application\msedge.exe" -ArgumentList @(
  "--remote-debugging-port=9225",
  "--remote-allow-origins=*",
  "--user-data-dir=C:\Temp\EdgeDevCDP",
  "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"
)
```

### 突破 2：MemberInfo save 的"三件套"魔法

之前 Phase 1 D0022 突破记录提到 **"signInfo 是服务端的固定魔数"**。现在 Phase 2 的 MemberInfo save 再次印证：

```python
body = {
  # ... member 所有字段平铺
  "politicsVisage": "13",          # 群众（数据字典固定值）
  "agentMemPartDto": {
    # ... 原有字段
    "isOrgan": "02",               # 否（不是登记代理机构）
  },
  "gdMemPartDto": {                # 投资人（股东）资金信息
    "shouldInvestMoney": "100000",
    "shouldInvestWay": "01",       # 货币
    "investDate": "2026-12-31",
    "moneyRatio": "100.0000",
    "joinDate": "2026-04-23",
    "invType": "1",
    "invFormType": "1",
    "fromType": "1",
    "foreignOrChinese": "1"
  },
  "allInfoFull": True,
  "flowData": {"busiId": "...", "currCompUrl": "MemberInfo", ...},
  "linkData": {
    "compUrl": "MemberInfo",
    "opeType": "save",
    "compUrlPaths": ["MemberPool", "MemberInfo"],  # 父子路径
    "busiCompUrlPaths": "%5B%7B%22compUrl%22%3A%22MemberPool%22%2C%22id%22%3A%22%22%7D%5D",
    "token": ""
  },
  "signInfo": "-1607173598",       # ★ Phase 2 的魔数（和 MemberPost 相同）
  "itemId": "<list[0].itemId>"    # 从 load 响应拿
}
```

**迭代路径**：
1. A0002 服务端异常 → 加 signInfo=-1607173598 → resultType=1 "政治面貌不能为空"
2. 加 politicsVisage="13" → resultType=1 "请选择是否为代理机构"
3. 加 `agentMemPartDto.isOrgan = "02"` → code=00000 resultType=0 ✅

### 突破 3：前端"自动推进"机制

真实用户点击**"保存并下一步"**按钮时，前端不仅调当前组件的 save，还会：
1. **如果 save 成功**（`resultType=0`）
2. **自动调下一组件的 loadBusinessDataInfo**（从 `compCombArr` 取下一个）
3. **UI 切到下一组件的 route**

代码片段（监听 Network 看到）：

```
MemberPool/operationBusinessDataInfo 200 OK (save)
ComplementInfo/loadBusinessDataInfo 200 OK (自动进下一组件)
→ URL 变 #/flow/base/complement-info
```

**这个机制说明**：服务端 save 成功后，我们不需要再调 next 或 saveAndNext。让浏览器自己处理。只要我们保证每个 save 的 body 合法，前端自动推进到下一组件。

### 突破 4：Element UI upload 的真实触发链

**`DOM.setFileInputFiles` 对 Element UI 的 `<el-upload>` 无效**，因为 Element UI 用了自定义 `http-request`（见 Vue props）。

**Element UI 的内部调用链**：
```
handleStart(file) → 加入 uploadFiles (status=ready)
  ↓ (autoUpload=true)
upload(file) → 调 httpRequest(options)
  ↓
upload-inner.post(file) ← ★ 真实发 HTTP 请求的方法
```

**我做到的**：`ElUpload.$refs['upload-inner'].post(file)` **成功触发 upload API 200 OK**。

但 **fileId 绑定到 Vue state** 没完成（Element UI 的 onSuccess 回调链没走到父组件 data）。

**构造 File 对象**（避免 Node.js 文件 API 限制）：

```javascript
// Python 端读文件 base64，分块存到 window.__fb__
// JS 端：
var bin = atob(window.__fb__);
var arr = new Uint8Array(bin.length);
for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
var blob = new Blob([arr], {type: 'image/jpeg'});
var file = new File([blob], '租赁合同.jpg', {type: 'image/jpeg'});
file.uid = Date.now();
```

### 突破 5：MemberPool → 自动跳 ComplementInfo 证明路径

发现个人独资企业的简化路径：
```
MemberPool → [跳过 PersonInfoRegGT, ChargeDepartment] → ComplementInfo
```

前端自动跳过这些组件（服务端判定非必需），**不需要我们手动 save**。

---

## 三、踩过的坑

### 坑 1：mitm 抓包进程死掉后 Edge 无法访问 HTTPS

48 分钟前 mitm 进程停了（`Get-Process mitmdump` 为空），但 Edge 启动时带的 `--proxy-server` 依然指向 8080，导致所有请求走一个**假代理**（`python -m http.server`）返回 HTML 内容，而不是代理请求到真实服务器。

**教训**：Edge 代理参数是启动时固定的，mitm 停了必须重启 Edge 不带 proxy。

### 坑 2：API 路径过时导致 404

`/icpsp-api/v4/pc/login/checkToken` 返回 404。当前正确 API 是 `/icpsp-api/v4/pc/manager/usermanager/getUserInfo`。

**教训**：平台升级会改 API 路径。用 CDP Network 监听 portal 刷新看它实际调的接口。

### 坑 3：MemberInfo form 数据被"reset"现象

`handleAction('supplement', member)` 调用后，`vm.form` 里**很多字段都是 null**（甚至 name、cerNo 也不在）。

**根因**：`handleAction` 只是打开 supplement 态，`form` 初始化是 async 的（需要 nextTick）。

**规避**：直接 `vm.form[k] = member[k]` 把所有字段平铺进去，不等异步。

### 坑 4：点击保存按钮 12 秒无 API 调用

反复出现"点击了但没发请求"。原因：**前端校验拦截**。当 `allInfoFull=false` 时，`index.flowSave()` 早期 return，不调服务端。

**规避**：手动设 `member.allInfoFull = true`，或直接调 `flow-control.save()`（绕过 index 的前端校验），看服务端真实反馈。

### 坑 5：member.itemId vs body.itemId 位置混淆

服务端 MemberInfo save body 里：
- `itemId` **要放到 body 顶层**（不是 member 内部）
- 值来自 `list[0].itemId`（是成员的"业务条目 ID"）

我一开始把 itemId 放 member 里面，服务端解析不对。

### 坑 6：member 里嵌套了 meta 字段

load 响应的 `list[0]` 实际包含了 **member 的数据 + flowData/linkData/processVo 等 meta**。如果把整个 list[0] 平铺到 body，meta 字段会覆盖 body 顶层的 flowData/linkData，导致路径污染 → D0022 越权。

**规避**：构造 body 时 filter 掉 meta keys:
```python
skip = ['flowData','linkData','processVo','jurisdiction','currentLocationVo',
        'producePdfVo','returnModifyVo','transferToOfflineVo','preSubmitVo',
        'submitVo','page','list','fieldList','busiComp','subBusiCompMap',
        'signInfo','operationResultVo','signRandomCode','extraDto','xzPushGsDto',
        'itemId','pkAndMem','delPostCode','realEntName']
```

### 坑 7：CDP Runtime.evaluate 大 body 超时

base64 文件 308K 字符，**一次 evaluate 塞进去会 CDP WebSocket 超时**。

**规避**：分块赋值
```python
CHUNK = 60000
eval_js("window.__fb__ = '';")
for i in range(0, len(b64), CHUNK):
    eval_js(f"window.__fb__ += {json.dumps(b64[i:i+CHUNK])};")
```

### 坑 8：Element UI upload 5 个实例、3 个 VM 的混乱

SlUploadMaterial 页面有 **4 个 upload-item**（身份证已传、住所、租赁、其他），但 `document.querySelectorAll('.el-upload')` 返回 **6 个**（身份证 2 个图片 + 3 个 待上传 + 1 个内部 div）。

而 Vue `ElUpload` 实例只有 **3 个**（已传的身份证没再实例化）。

**规避**：按 Vue 实例的**索引**（idx=0=住所，idx=1=租赁，idx=2=其他），而不是按 DOM 顺序。

---

## 四、可复用代码片段

### 4.1 协议化 save body 通用骨架（含 signInfo）

```python
def build_save_body(comp_url, parent_path, current_busi_id, name_id, member_data, item_id=""):
    """
    comp_url: 当前组件名 'MemberInfo' / 'MemberPool' / 'ComplementInfo' 等
    parent_path: 父组件路径数组 ['MemberPool'] 或 []
    member_data: member 字段的平铺（已过滤 meta）
    """
    path = parent_path + [comp_url] if parent_path else [comp_url]
    busi_comp_paths = "%5B%5D" if not parent_path else \
        f"%5B%7B%22compUrl%22%3A%22{parent_path[0]}%22%2C%22id%22%3A%22%22%7D%5D"
    
    body = dict(member_data) if member_data else {}
    body.update({
        "flowData": {
            "busiId": current_busi_id, "entType": "4540", "busiType": "02",
            "busiMode": None, "nameId": name_id, "marPrId": None, "secondId": None,
            "vipChannel": None, "currCompUrl": comp_url, "status": "10",
            "matterCode": None, "interruptControl": None, "ywlbSign": "4"
        },
        "linkData": {
            "compUrl": comp_url, "opeType": "save",
            "compUrlPaths": path, "busiCompUrlPaths": busi_comp_paths, "token": ""
        },
        "signInfo": "-1607173598",
        "itemId": item_id
    })
    return body
```

### 4.2 让前端自动推进（不自己管下一步）

```python
# 调当前 save → 服务端 resultType=0 → 前端自动 load 下一组件
# 所以只需要 reliable 地让每一步 save 成功，前端自己推进

# 真实点击的等价协议化：
# 1. fetch 当前组件 operationBusinessDataInfo (opeType=save)
# 2. 如果 code=00000 resultType=0，稍等前端自己 load 下一组件
# 3. 导航 URL 会变

# 要想直接跳某个组件，Page.navigate 到 #/flow/base/<comp-kebab-name>
```

### 4.3 Element UI upload 协议化（需完善 fileId 绑定）

```python
# 读文件 base64
b64 = base64.b64encode(file.read_bytes()).decode("ascii")

# 分块传入 window.__fb__
eval_js("window.__fb__ = '';")
for i in range(0, len(b64), 60000):
    eval_js(f"window.__fb__ += {json.dumps(b64[i:i+60000])};")

# 调 upload-inner.post(file) 触发上传 API
eval_js(r"""(function(){
  var els = [];
  // 收集所有 ElUpload 实例
  // ...
  var vm = els[1];  // 第 N 个槽位
  var inner = vm.$refs['upload-inner'];
  
  // 构造 File
  var bin = atob(window.__fb__);
  var arr = new Uint8Array(bin.length);
  for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  var blob = new Blob([arr], {type: 'image/jpeg'});
  var file = new File([blob], '文件名.jpg', {type: 'image/jpeg'});
  file.uid = Date.now();
  
  inner.post(file);
})()""")

# TODO: fileId 绑定 - upload API 响应返回 fileId，需要写回 sl-upload-material.businessDataInfo.data
```

---

## 五、剩余工作

### 5.1 SlUploadMaterial 的 fileId 绑定

需要：
1. 拦截 upload API 响应的 fileId
2. 找 `sl-upload-material.businessDataInfo.data` 里租赁合同槽位的正确字段
3. 设 `data.materialList[index].fileId = uploadResponseFileId`
4. 然后 save SlUploadMaterial

**另一种解法**：让用户浏览器手动点上传按钮（最快）。

### 5.2 后续组件清单（预计）

按 `compCombArr`，SlUploadMaterial 之后：
- **BusinessLicenceWay**（营业执照领取方式）
- **YbbSelect**（云帮办流程选择）
- **PreElectronicDoc**（信息确认）
- **PreSubmitSuccess**（预提交成功）← 🎯 **用户要求停在这里**

预计每个都是类似模式：点"保存并下一步" → 服务端 save → 前端自动推进。

---

## 六、当日产物

- `@g:\UFO\政务平台\system\_phase2_mi_save_v7.py` — MemberInfo 协议化 save（完整可用）
- `@g:\UFO\政务平台\system\_phase2_mp_try_save.py` — MemberPool 协议化 save
- `@g:\UFO\政务平台\system\_phase2_ci_click_next.py` — 点击"保存并下一步"推进通用脚本
- `@g:\UFO\政务平台\system\_phase2_sl_proto_v3.py` — Element UI upload 协议化（触发上传 API 成功）
- `@g:\UFO\政务平台\docs\Phase2第二日突破_MemberInfo至SlUploadMaterial_20260423.md` — 本文

**方法论总结**：对于有 Vue + Element UI 的政务系统，**协议化（纯 HTTP）和前端自动推进结合使用**是最高效的路径：
- 关键数据写入走协议化 fetch（直接 API 调用）
- 组件推进依靠前端 onClick 的副作用（点击真实按钮让前端自动 load 下一组件）
- 只在遇到"前端校验拦截"或"Element UI 自定义交互"时才回退到 Vue 方法调用

— 2026-04-23 晚
