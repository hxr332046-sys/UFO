"""Check and clean up existing active matters to unblock new registration."""
import sys, json
sys.path.insert(0, 'system')
from icpsp_api_client import ICPSPClient

client = ICPSPClient()

# Step 1: Query active matters
print("=== 查询活跃办件 ===")
resp = client.post_json(
    "/icpsp-api/v4/pc/manager/mattermanager/matters/list",
    {"pageSize": 20, "pageNo": 1, "state": "101"},
)
if resp.get("code") != "00000":
    print(f"  查询失败: code={resp.get('code')} msg={resp.get('msg')}")
else:
    rows = (resp.get("data") or {}).get("rows") or []
    print(f"  找到 {len(rows)} 个活跃办件:")
    for row in rows:
        busi_id = row.get("busiId")
        ent_name = row.get("entName", "")
        state = row.get("state")
        busi_type_name = row.get("busiTypeName", "")
        print(f"    busiId={busi_id} entName={ent_name} state={state} type={busi_type_name}")

# Step 2: For each active matter, try withdraw (104) then delete (103)
for row in (resp.get("data") or {}).get("rows") or []:
    busi_id = row.get("busiId")
    ent_name = row.get("entName", "")
    if not busi_id:
        continue
    
    print(f"\n=== 清理办件: {ent_name} (busiId={busi_id}) ===")
    
    # Withdraw: btnCode=104, two-step (before + operate)
    # Step 2a: before
    print("  撤回 before...")
    before_resp = client.post_json(
        "/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
        {"busiId": busi_id, "btnCode": "104", "dealFlag": "before"},
    )
    before_code = before_resp.get("code")
    before_rt = str((before_resp.get("data") or {}).get("resultType", ""))
    before_msg = (before_resp.get("data") or {}).get("msg") or before_resp.get("msg") or ""
    print(f"    code={before_code} rt={before_rt} msg={before_msg}")
    
    if before_code == "00000" and before_rt == "2":
        # Step 2b: operate (confirm withdraw)
        print("  撤回 operate...")
        op_resp = client.post_json(
            "/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
            {"busiId": busi_id, "btnCode": "104", "dealFlag": "operate"},
        )
        op_code = op_resp.get("code")
        op_rt = str((op_resp.get("data") or {}).get("resultType", ""))
        op_msg = (op_resp.get("data") or {}).get("msg") or op_resp.get("msg") or ""
        print(f"    code={op_code} rt={op_rt} msg={op_msg}")
        
        if op_code == "00000" and op_rt == "0":
            print("  ✓ 撤回成功!")
            # Step 2c: delete (103)
            print("  删除 before...")
            del_before = client.post_json(
                "/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
                {"busiId": busi_id, "btnCode": "103", "dealFlag": "before"},
            )
            del_rt = str((del_before.get("data") or {}).get("resultType", ""))
            print(f"    rt={del_rt}")
            
            if del_rt == "2":
                print("  删除 operate...")
                del_op = client.post_json(
                    "/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
                    {"busiId": busi_id, "btnCode": "103", "dealFlag": "operate"},
                )
                del_op_rt = str((del_op.get("data") or {}).get("resultType", ""))
                del_op_msg = (del_op.get("data") or {}).get("msg") or del_op.get("msg") or ""
                print(f"    rt={del_op_rt} msg={del_op_msg}")
                if del_op_rt == "0":
                    print("  ✓ 删除成功!")
        elif "已提交" in op_msg or "104" in str(op_msg):
            print("  办件已提交，无法撤回，尝试直接删除...")
        else:
            print(f"  撤回失败: {op_msg}")
    else:
        print(f"  撤回before失败或无需确认: rt={before_rt} msg={before_msg}")
        # Try direct delete
        print("  尝试直接删除...")
        del_before = client.post_json(
            "/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
            {"busiId": busi_id, "btnCode": "103", "dealFlag": "before"},
        )
        del_rt = str((del_before.get("data") or {}).get("resultType", ""))
        del_msg = (del_before.get("data") or {}).get("msg") or del_before.get("msg") or ""
        print(f"    rt={del_rt} msg={del_msg}")
        if del_rt == "2":
            del_op = client.post_json(
                "/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
                {"busiId": busi_id, "btnCode": "103", "dealFlag": "operate"},
            )
            del_op_rt = str((del_op.get("data") or {}).get("resultType", ""))
            print(f"    删除结果: rt={del_op_rt}")
            if del_op_rt == "0":
                print("  ✓ 删除成功!")

# Step 3: Verify cleanup
print("\n=== 验证清理结果 ===")
resp2 = client.post_json(
    "/icpsp-api/v4/pc/manager/mattermanager/matters/list",
    {"pageSize": 20, "pageNo": 1, "state": "101"},
)
rows2 = (resp2.get("data") or {}).get("rows") or []
print(f"  剩余活跃办件: {len(rows2)}")
for row in rows2:
    print(f"    busiId={row.get('busiId')} entName={row.get('entName')}")
