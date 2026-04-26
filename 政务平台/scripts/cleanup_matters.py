"""列出并清理所有活跃办件（btnCode=103 两步删除）"""
import sys, json, time
sys.path.insert(0, "system")
from icpsp_api_client import ICPSPClient

API = "/icpsp-api/v4/pc/manager/mattermanager/matters/operate"
HDRS = {"Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html"}
c = ICPSPClient()

# 列出所有办件
r = c.get_json("/icpsp-api/v4/pc/manager/mattermanager/matters/search",
               params={"pageNo": "1", "pageSize": "50"})
bd = (r.get("data") or {}).get("busiData") or []
print(f"Total matters: {len(bd)}")
for it in bd:
    bid = it.get("id", "")
    state = it.get("matterStateLangCode", "")
    bt = it.get("busiType", "")
    nm = it.get("entName", "")
    print(f"  {bid}  state={state}  busiType={bt}  {nm}")

# 删除 status=100（填写中）的办件，保留已完成/审核中的
to_delete = [it for it in bd if "100" in str(it.get("matterStateLangCode", ""))]
print(f"\nMatters to delete (status=100): {len(to_delete)}")
for it in to_delete:
    bid = it.get("id", "")
    nm = it.get("entName", "")
    # btnCode=103 两步：before + operate
    r1 = c.post_json(API, {"busiId": bid, "btnCode": "103", "dealFlag": "before"}, extra_headers=HDRS)
    code1 = r1.get("code", "")
    rt1 = (r1.get("data") or {}).get("resultType", "")
    print(f"  {bid} ({nm}) before: code={code1} rt={rt1}")
    time.sleep(0.5)
    r2 = c.post_json(API, {"busiId": bid, "btnCode": "103", "dealFlag": "operate"}, extra_headers=HDRS)
    code2 = r2.get("code", "")
    msg2 = (r2.get("data") or {}).get("msg", r2.get("msg", ""))[:80]
    print(f"  {bid} ({nm}) operate: code={code2} msg={msg2}")
    time.sleep(0.5)

print("\nDone.")
