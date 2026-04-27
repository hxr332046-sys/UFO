"""Run full flow to producePdf step, capturing state at each step.
Uses the existing SmartRegisterRunner for Phase 1, then manual Phase 2 steps.
"""
import sys, json, time, copy, os
sys.path.insert(0, 'system')

from icpsp_api_client import ICPSPClient
from phase2_protocol_driver import Phase2Context
import phase2_protocol_driver as p2d

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

# ===== PHASE 1: Manual name registration =====
print("\n" + "="*60)
print("PHASE 1: Name Registration (manual API calls)")
print("="*60)

from phase1_protocol_driver import DriverContext as P1Ctx

p1_ctx = P1Ctx(case=case)
p1_ctx.ent_type = "4540"

# Step 1: namePreCheck
print("\n--- namePreCheck ---")
import phase1_protocol_driver as p1d
r1 = p1d.step1_name_pre_check(client, p1_ctx)
print(f"  code={r1.get('code')}")

# Step 2: nameApply
print("\n--- nameApply ---")
r2 = p1d.step2_name_apply(client, p1_ctx)
print(f"  code={r2.get('code')}")
busi_id_p1 = p1_ctx.busi_id
print(f"  busiId={busi_id_p1}")

# Step 3-7: supplement, shareholder, submit
print("\n--- Step 3: nameSupplement load ---")
r3 = p1d.step3_name_supplement_load(client, p1_ctx)
print(f"  code={r3.get('code')}")

print("\n--- Step 4: nameSupplement save ---")
r4 = p1d.step4_name_supplement_save(client, p1_ctx)
print(f"  code={r4.get('code')}")

print("\n--- Step 5: shareholder load ---")
r5 = p1d.step5_shareholder_load(client, p1_ctx)
print(f"  code={r5.get('code')}")

print("\n--- Step 6: shareholder save ---")
r6 = p1d.step6_shareholder_save(client, p1_ctx)
print(f"  code={r6.get('code')}")

print("\n--- Step 7: nameSubmit ---")
r7 = p1d.step7_name_submit(client, p1_ctx)
print(f"  code={r7.get('code')}")

# Wait for name approval
print("\n--- Waiting for name approval ---")
time.sleep(3)

print("\n--- Step 8: nameSuccess load ---")
r8 = p1d.step8_name_success_load(client, p1_ctx)
print(f"  code={r8.get('code')}")
name_id = p1_ctx.name_id
print(f"  nameId={name_id}")

if not name_id:
    print("Phase 1 failed - no nameId!")
    sys.exit(1)

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
            print(f"  ⚠️ Non-success!")
    except Exception as e:
        print(f"  ERROR: {e}")

# Check state
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
