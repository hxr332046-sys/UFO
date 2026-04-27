"""批量拉取 establish 流所有 33 个组件的 loadBusinessDataInfo。

用 phase1_busi_id + nameId 调每个组件的 load 接口。响应保存到
packet_lab/out/component_loads_full/，同时喂给 OptionsScout 沉淀字典。
"""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient
from governance import OptionsScout, OptionDict


COMPONENTS = [
    "NameInfoDisplay", "BasicInfo", "MemberPost", "MemberPool", "PersonInfoRegGT",
    "ChargeDepartment", "RegMergeAndDiv", "WzInfoReport", "ComplementInfo", "Rules",
    "BankOpenInfo", "MedicalInsured", "Engraving", "TaxInvoice", "SocialInsured",
    "GjjHandle", "WaterNewHandle", "GasNewHandle", "ElectricNewHandle", "NetHandle",
    "CreditHandle", "HouseConstructHandle", "YjsRegPrePack", "YjsRegFoodOp",
    "SlUploadMaterial", "BusinessLicenceWay", "YbbSelect", "PreElectronicDoc",
    "PreSubmitSuccess", "ElectronicDoc", "SubmitSuccess", "RegNotification",
]


def main():
    # 从最近的 records 拿 busiId/nameId
    rec = json.load(open("dashboard/data/records/phase2_establish_latest.json", "r", encoding="utf-8"))
    busi_id = None
    name_id = None
    for s in rec.get("steps", []):
        ext = s.get("extracted") or {}
        if ext.get("busiId") and not busi_id:
            busi_id = ext["busiId"]
        if ext.get("nameId") and not name_id:
            name_id = ext["nameId"]
    print(f"busiId={busi_id} nameId={name_id}")
    if not busi_id:
        print("❌ 找不到 busi_id")
        return 1

    client = ICPSPClient()
    od = OptionDict.load()
    scout = OptionsScout(od, log=True)

    # 验证登录
    ui = client.get_json("/icpsp-api/v4/pc/manager/usermanager/getUserInfo", params={})
    if ui.get("code") != "00000":
        print(f"❌ 未登录: {ui.get('code')}")
        return 1
    print(f"✅ 登录有效\n")

    out_dir = Path("packet_lab/out/component_loads_full")
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for comp in COMPONENTS:
        url = f"/icpsp-api/v4/pc/register/establish/component/{comp}/loadBusinessDataInfo"
        body = {
            "flowData": {
                "busiId": busi_id,
                "nameId": name_id,
                "entType": "4540",
                "busiType": "02",
                "currCompUrl": comp,
                "status": "10",
            },
            "linkData": {
                "compUrl": comp,
                "compUrlPaths": [comp],
                "continueFlag": False,
            },
        }
        try:
            r = client.post_json(url, body)
            code = r.get("code", "?")
            bd = (r.get("data") or {}).get("busiData")
            field_count = len(bd) if isinstance(bd, dict) else 0
            print(f"  {comp:25s} code={code:8s} fields={field_count}")
            results.append((comp, code, field_count))
            # 保存 raw
            out_path = out_dir / f"{comp}_load.json"
            out_path.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
            # 喂 scout（仅成功的）
            if code == "00000" and bd:
                scout.ingest_load_response(component=comp, load_resp=r)
        except Exception as e:
            print(f"  {comp:25s} ERROR: {e}")
            results.append((comp, "ERR", 0))
        time.sleep(0.3)  # 节流

    print(f"\n=== 拉取完成 ===")
    success = sum(1 for _,c,_ in results if c == "00000")
    print(f"  成功: {success}/{len(COMPONENTS)}")

    # 持久化
    rep = scout.report()
    print(f"  Scout 发现: {rep['total_findings']} 个枚举/元数据")
    p = scout.persist()
    print(f"  字典已写入: {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
