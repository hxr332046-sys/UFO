from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "system"))

from icpsp_api_client import ICPSPClient  # noqa: E402
import phase2_bodies as pb  # noqa: E402
from phase2_constants import establish_comp_load  # noqa: E402

BID = "2047965798241648641"
PHASE1_BID = "2047965588978008064"
NAME_ID = "2047965733625339906"
ENT = "4540"
REFERER = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html"


def summarize(label: str, resp: dict) -> None:
    data = resp.get("data") or {}
    bd = data.get("busiData") if isinstance(data, dict) else None
    if not isinstance(bd, dict):
        bd = {}
    fd = bd.get("flowData") or {}
    ld = bd.get("linkData") or {}
    pvo = bd.get("processVo") or {}
    out = {
        "label": label,
        "code": resp.get("code"),
        "msg": resp.get("msg"),
        "resultType": data.get("resultType") if isinstance(data, dict) else None,
        "flowData": {k: fd.get(k) for k in ["busiId", "entType", "busiType", "nameId", "currCompUrl", "status"]},
        "linkData": {k: ld.get(k) for k in ["compUrl", "opeType", "compUrlPaths", "continueFlag", "busiCompUrlPaths"]},
        "signInfo": bd.get("signInfo"),
        "busiComp": {
            "compUrl": (bd.get("busiComp") or {}).get("compUrl"),
            "compName": (bd.get("busiComp") or {}).get("compName"),
        },
        "processVo": {k: pvo.get(k) for k in ["maxSaveStep", "lastOperStep", "currentStep", "currentComp", "showFlag"]},
        "ybb": {k: bd.get(k) for k in ["isOptional", "preAuditSign", "isSelectYbb"]},
    }
    print(f"\n--- {label}")
    print(json.dumps(out, ensure_ascii=False, indent=2))


def main() -> int:
    client = ICPSPClient()
    record = json.loads((ROOT / "dashboard/data/records/phase2_establish_latest.json").read_text(encoding="utf-8"))
    snap = record["context_state"]["phase2_driver_snapshot"]

    for label, bid, bt, cf in [
        ("loc_est_02_continue", BID, "02", "continueFlag"),
        ("loc_est_02_4_continue", BID, "02_4", "continueFlag"),
        ("loc_est_02_empty", BID, "02", ""),
        ("loc_phase1_02_4_continue", PHASE1_BID, "02_4", "continueFlag"),
    ]:
        body = {
            "flowData": {
                "busiId": bid,
                "entType": ENT,
                "busiType": bt,
                "ywlbSign": "4",
                "busiMode": None,
                "nameId": NAME_ID,
                "marPrId": None,
                "secondId": None,
                "vipChannel": None,
            },
            "linkData": {"continueFlag": cf, "token": ""},
        }
        summarize(label, client.post_json(
            "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
            body,
            extra_headers={"Referer": REFERER},
        ))

    body = {
        "flowData": pb._base_flow_data(ENT, NAME_ID, "YbbSelect", busi_id=BID),
        "linkData": pb._base_link_data("YbbSelect", ope_type="load"),
        "itemId": "",
    }
    summarize("load_YbbSelect_base", client.post_json(establish_comp_load("YbbSelect"), body, extra_headers={"Referer": REFERER}))

    body = {
        "flowData": pb._base_flow_data(ENT, NAME_ID, "PreElectronicDoc", busi_id=BID),
        "linkData": pb._base_link_data("PreElectronicDoc", ope_type="load"),
        "itemId": "",
    }
    summarize("load_PreElectronicDoc_base", client.post_json(establish_comp_load("PreElectronicDoc"), body, extra_headers={"Referer": REFERER}))

    prev_fd = copy.deepcopy(snap.get("last_save_flowData") or {})
    prev_fd["currCompUrl"] = "PreElectronicDoc"
    prev_ld = copy.deepcopy(snap.get("last_save_linkData") or {})
    prev_ld["compUrl"] = "PreElectronicDoc"
    prev_ld["opeType"] = "load"
    prev_ld["compUrlPaths"] = ["PreElectronicDoc"]
    body = {"flowData": prev_fd, "linkData": prev_ld, "itemId": ""}
    summarize("load_PreElectronicDoc_prev_link", client.post_json(establish_comp_load("PreElectronicDoc"), body, extra_headers={"Referer": REFERER}))

    body = {
        "flowData": pb._base_flow_data(ENT, NAME_ID, "PreSubmitSuccess", busi_id=BID),
        "linkData": {"compUrl": "PreSubmitSuccess", "compUrlPaths": ["PreSubmitSuccess"], "token": ""},
        "itemId": "",
    }
    summarize("load_PreSubmitSuccess_base", client.post_json(establish_comp_load("PreSubmitSuccess"), body, extra_headers={"Referer": REFERER}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
