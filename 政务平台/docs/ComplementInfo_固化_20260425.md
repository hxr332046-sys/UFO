# ComplementInfo 非公党建固化纪要 — 2026-04-25

## 达标状态
- **4540 个人独资** ✅ 已固化（mitmproxy 捕获 + step19 重写）
- **1151 有限公司** ⚠️ 另有受益所有人 BenefitUsers，见 step19_1151_complement_info_advance

---

## 真实浏览器请求体（4540，mitmproxy 捕获）

```json
{
  "signerSupplementInfoDto": null,
  "sendPdfInfoDto": null,
  "promiseInfoDto": null,
  "partyBuildDto": {
    "partyBuildFlag": "6",
    "otherDto": {
      "numFormalParM": null, "numProParM": null, "organizationName": null,
      "parRegisterDate": null, "parIns": "1",
      "resParSecSign": false, "djgAsSecretary": false, "entWithPartyBuild": false,
      "parOrgSecName": null, "parOrgSecTel": null, "encryptedParOrgSecTel": null,
      "supOrganizationName": null,
      "estParSign": false,
      "numParM": 0,
      "numParNmae": null, "parOrgw": "1",
      "resParMSign": false, "anOrgParSign": false
    },
    "xzDto": {
      "estParSign": false, "parIns": "1", "parOrgw": "1", "standardEsFlag": false
    }
  },
  "guardianInfoDto": null, "extendInfoDto": null,
  "xzPushGsDto": null, "entAssertDto": null, "authorizedInfoDto": null,
  "flowData": {
    "busiId": "<BUSI_ID>", "entType": "4540",
    "busiType": "02",
    "ywlbSign": "4", "busiMode": null, "nameId": "<NAME_ID>",
    "marPrId": null, "secondId": null, "vipChannel": null,
    "currCompUrl": "ComplementInfo", "status": "10",
    "matterCode": null, "interruptControl": null
  },
  "linkData": {
    "compUrl": "ComplementInfo", "opeType": "save",
    "compUrlPaths": ["ComplementInfo"],
    "busiCompUrlPaths": "%5B%5D", "token": ""
  },
  "signInfo": "<dynamic>",
  "itemId": ""
}
```

---

## 关键坑点（与之前猜测的差异）

| 字段 | 之前错误猜测 | 真实值 |
|------|------------|--------|
| `estParSign` | `"2"` (字符串) | `false` (boolean，在 `otherDto` 里) |
| `numParM` | `"0"` (字符串) | `0` (integer，在 `otherDto` 里) |
| `busiType` | `"02_4"` | `"02"` |
| `linkData.busiCompUrlPaths` | 服务端返回值 | `"%5B%5D"` (固定空数组) |
| DTO 顶层结构 | 平铺 `estParSign` 在 partyBuildDto 下 | 嵌套 `partyBuildDto.otherDto.estParSign` |
| 其他 DTO 字段 | 未发送 | 全部 `null`（`signerSupplementInfoDto` 等 8 个） |

---

## D0029 根因（本次解决）
服务端对 `otherDto.estParSign`（boolean）做了强类型校验。
之前发送 `estParSign: "2"` 或放在 `partyBuildDto` 顶层 → 服务端反序列化失败 → D0029。

---

## 代码位置
- **step19**: `system/phase2_protocol_driver.py` → `step19_complement_info_advance`（已重写）
- **bodies 注释**: `system/phase2_bodies.py` → `build_empty_advance_save_body` 注释已更新

---

## 表单字段含义（4540 个人独资，entType=4540）

| 表单标签 | 字段路径 | 值（全否） |
|---------|---------|-----------|
| 是否建立党组织建制 | `partyBuildDto.otherDto.estParSign` | `false` |
| 党员人数 | `partyBuildDto.otherDto.numParM` | `0` |
| 法定代表人党组织书记标志 | `partyBuildDto.otherDto.resParSecSign` | `false` |
| 本年检年度组建党组织标志 | `partyBuildDto.otherDto.anOrgParSign` | `false` |
| 法定代表人党员标志 | `partyBuildDto.otherDto.resParMSign` | `false` |
| partyBuildFlag（非公党建） | `partyBuildDto.partyBuildFlag` | `"6"` |

---

## 捕获文件
- 请求体: `packet_lab/out/complement_info_save_body.json`
- 捕获工具: `packet_lab/mitm_capture_complement.py`
