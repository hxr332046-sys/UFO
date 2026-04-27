"""逐个 load 所有填报组件，检查每个组件返回的 busiData 是否完整。
重点关注：哪些字段是 null/空，哪个组件可能数据不全导致 PDF 生成失败。
"""
import sys, json, copy
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()
busi_id = "2048544858885832706"
name_id = "2048544825345122306"
user_id = "824032604"

# Step 1: get full flowData/linkData from loadCurrentLocationInfo
loc_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    {"flowData": {"busiId": busi_id, "busiType": "02", "entType": "4540", "nameId": name_id},
     "linkData": {"continueFlag": "continueFlag", "token": user_id}},
)
loc_bd = (loc_resp.get('data') or {}).get('busiData') or {}
loc_fd = loc_bd.get('flowData', {})
loc_ld = loc_bd.get('linkData', {})

print(f"loadCurrentLocationInfo: code={loc_resp.get('code')}")
print(f"flowData.currCompUrl={loc_fd.get('currCompUrl')} status={loc_fd.get('status')}")
print(f"producePdfVo={loc_bd.get('producePdfVo')}")

# components in fill step (从 005 响应里看到的)
components = [
    "BasicInfo", "MemberPost", "MemberPool", "ComplementInfo",
    "TaxInvoice", "SlUploadMaterial", "BusinessLicenceWay", "YbbSelect",
]

results = {}
for comp in components:
    print(f"\n=== Loading {comp} ===")
    body = {
        "flowData": copy.deepcopy(loc_fd),
        "linkData": copy.deepcopy(loc_ld),
        "itemId": "",
    }
    body["flowData"]["currCompUrl"] = comp
    body["linkData"]["compUrl"] = comp
    body["linkData"]["opeType"] = "load"
    body["linkData"]["compUrlPaths"] = [comp]
    
    resp = client.post_json(
        f"/icpsp-api/v4/pc/register/establish/component/{comp}/loadBusinessDataInfo",
        body,
    )
    code = resp.get('code')
    rt = (resp.get('data') or {}).get('resultType', '')
    bd = (resp.get('data') or {}).get('busiData') or {}
    
    print(f"  code={code} rt={rt}")
    
    # Save full response
    out_path = f"packet_lab/out/component_loads/{comp}_load.json"
    import os
    os.makedirs("packet_lab/out/component_loads", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resp, f, ensure_ascii=False, indent=2)
    
    if code == "00000" and bd:
        # Check critical data fields (extract by component)
        if comp == "BasicInfo":
            print(f"  entName={bd.get('entName')}")
            print(f"  regCap={bd.get('regCap')} regCapCur={bd.get('regCapCur')}")
            print(f"  ywqyFlag={bd.get('ywqyFlag')}")
            print(f"  domDistCode={bd.get('domDistCode')} dom={bd.get('dom')}")
        elif comp == "MemberPost":
            mems = bd.get('memberList') or []
            print(f"  memberList count={len(mems)}")
        elif comp == "MemberPool":
            mems = bd.get('list') or []
            print(f"  list count={len(mems)}")
            for m in mems[:3]:
                print(f"    member: {m.get('cerNo')} {m.get('memName')}")
        elif comp == "ComplementInfo":
            print(f"  benefitUsersList count={len(bd.get('benefitUsersList') or [])}")
            print(f"  keys: {list(bd.keys())[:10]}")
        elif comp == "TaxInvoice":
            print(f"  keys: {list(bd.keys())[:10]}")
        elif comp == "SlUploadMaterial":
            mats = bd.get('list') or bd.get('materialList') or []
            print(f"  materials count={len(mats)}")
        elif comp == "BusinessLicenceWay":
            print(f"  keys: {list(bd.keys())[:10]}")
        elif comp == "YbbSelect":
            print(f"  isSelectYbb={bd.get('isSelectYbb')} preAuditSign={bd.get('preAuditSign')} isOptional={bd.get('isOptional')}")
            print(f"  producePdfVo={bd.get('producePdfVo')}")
        
        results[comp] = {"code": code, "ok": True, "keys": list(bd.keys())[:20]}
    else:
        msg = (resp.get('data') or {}).get('msg', '') or resp.get('msg', '')
        print(f"  ❌ FAILED: {msg}")
        results[comp] = {"code": code, "ok": False, "msg": msg}

# Save summary
with open("packet_lab/out/component_loads/_summary.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n=== Summary ===")
for c, r in results.items():
    status = "✅" if r.get("ok") else "❌"
    print(f"  {status} {c}: code={r.get('code')}")
