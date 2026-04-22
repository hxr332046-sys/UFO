"""直接用 mitm step5 原样 body 调 NameCheckInfo/operationBusinessDataInfo，定位拒绝原因。"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "system"))
from icpsp_api_client import ICPSPClient  # noqa: E402

dump = json.loads((ROOT / "dashboard/data/records/phase1_steps_5_7_dump.json").read_text(encoding="utf-8"))
body = json.loads(dump["5"]["req_body"])
print("original body keys:", sorted(body.keys()))
print("name:", body["name"])
print("entType:", body["entType"])

c = ICPSPClient()
r = c.post_json("/icpsp-api/v4/pc/register/name/component/NameCheckInfo/operationBusinessDataInfo", body)
print("code=", r.get("code"), "msg=", r.get("msg"))
data = r.get("data") or {}
bd = data.get("busiData") if isinstance(data.get("busiData"), dict) else {}
fd = bd.get("flowData") or {}
print("resultType=", data.get("resultType"), "busiId=", fd.get("busiId"))
print("raw[:300]:", str(r)[:300])
