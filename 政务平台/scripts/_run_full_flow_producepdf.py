"""Run full flow to producePdf step, capturing state at each step."""
import sys, json, time, copy, os
sys.path.insert(0, 'system')

from icpsp_api_client import ICPSPClient
from phase2_protocol_driver import Phase2Context
import phase2_protocol_driver as p2d
from phase1_protocol_driver import Phase1Driver

client = ICPSPClient()

# Verify session
user_resp = client.get_json('/icpsp-api/v4/pc/manager/usermanager/getUserInfo')
user_bd = (user_resp.get('data') or {}).get('busiData') or {}
user_id = user_bd.get('id', '')
print(f"User: id={user_id}")
if not user_id:
    print("Session expired!")
    sys.exit(1)

# Load case
with open("docs/case_兴裕为.json", "r", encoding="utf-8") as f:
    case = json.load(f)

name_mark = case["name_mark"]
print(f"Name mark: {name_mark}")

# ===== PHASE 1 =====
print("\n" + "="*60)
print("PHASE 1: Name Registration")
print("="*60)

p1 = Phase1Driver(client)
result = p1.run_full_name_registration(
    name_mark=name_mark, ent_type="4540",
    industry_code=case.get("phase1_industry_code", "6513"),
    industry_name=case.get("phase1_industry_name", "应用软件开发"),
    main_business=case.get("phase1_main_business_desc", "软件开发"),
    organize=case.get("phase1_organize", "中心（个人独资）"),
    dist_codes=case.get("phase1_dist_codes", ["450000","450900","450921"]),
    region_text=case.get("region_text", "广西容县"),
)

if not result or not result.get("name_id"):
    print(f"Phase 1 failed: {result}")
    sys.exit(1)

name_id = result["name_id"]
busi_id_p1 = result.get("busi_id", "")
print(f"\nPhase 1 OK! nameId={name_id} busiId={busi_id_p1}")

# ===== PHASE 2 =====
print("\n" + "="*60)
print("PHASE 2: Establish Flow")
print("="*60)

ctx = Phase2Context(case=case, user_id=user_id, name_id=name_id, ent_type="4540", busi_type="02")
ctx.phase1_busi_id = busi_id_p1

steps = [
    ("step10_matters_before", p2d.step10_matters_before),
    ("step11_matters_operate", p2d.step11_matters_operate),
    ("step12_establish_location", p2d.step12_establish_location),
    ("step13_ybb_select", p2d.step13_ybb_select),
    ("step14_basicinfo_load", p2d.step14_basicinfo_load),
    ("step15_basicinfo_save", p2d.step15_basicinfo_save),
    ("step16_memberpost_save", p2d.step16_memberpost_save),
    ("step17_memberpool_list_load", p2d.step17_memberpool_list_load),
    ("step18_memberinfo_save", p2d.step18_memberinfo_save),
    ("step19_complement_info_advance", p2d.step19_complement_info_advance),
    ("step20_tax_invoice_advance", p2d.step20_tax_invoice_advance),
    ("step21_sl_upload_material", p2d.step21_sl_upload_material),
    ("step22_licence_way_advance", p2d.step22_licence_way_advance),
    ("step23_ybb_select_save", p2d.step23_ybb_select_save),
]

for name, func in steps:
    print(f"\n--- {name} ---")
    try:
        r = func(client, ctx)
        code = r.get("code", "") if isinstance(r, dict) else ""
        rt = str((r.get("data") or {}).get("resultType", "")) if isinstance(r, dict) else ""
        msg = (r.get("msg", "") or "")[:60] if isinstance(r, dict) else ""
        print(f"  code={code} rt={rt} msg={msg}")
        if code and code not in ("00000",):
            print(f"  ⚠️ Non-success! Full: {json.dumps(r, ensure_ascii=False)[:200]}")
    except Exception as e:
        print(f"  ERROR: {e}")

# Check state after all steps
print("\n--- State after all steps ---")
loc_resp = client.post_json(
    "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
    {"flowData": {"busiId": ctx.establish_busi_id, "busiType": "02_4", "entType": "4540", "nameId": name_id},
     "linkData": {"continueFlag": "continueFlag", "token": user_id}},
)
loc_bd = (loc_resp.get('data') or {}).get('busiData') or {}
loc_fd = loc_bd.get('flowData', {})
pvo = loc_bd.get('processVo', {})
print(f"  currCompUrl={loc_fd.get('currCompUrl')}")
print(f"  currentComp={pvo.get('currentComp')}")
print(f"  maxSaveStep={pvo.get('maxSaveStep')}")
print(f"  producePdfVo={loc_bd.get('producePdfVo')}")

# Try producePdf
print("\n--- producePdf attempt ---")
pdf_body = {"flowData": copy.deepcopy(loc_fd), "linkData": copy.deepcopy(loc_bd.get('linkData', {}))}
pdf_body["linkData"]["token"] = user_id
pdf_body["linkData"]["continueFlag"] = ""

pdf_resp = client.post_json("/icpsp-api/v4/pc/register/establish/producePdf", pdf_body)
print(f"  code={pdf_resp.get('code')} msg={pdf_resp.get('msg')}")

# Save state
out = {"busi_id": ctx.establish_busi_id, "name_id": name_id, "user_id": user_id,
       "loc_response": loc_resp, "producePdf_response": pdf_resp}
out_path = "packet_lab/out/full_flow_producepdf_state.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f"\nState saved to {out_path}")
