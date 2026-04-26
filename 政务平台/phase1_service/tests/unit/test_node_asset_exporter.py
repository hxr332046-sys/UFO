from __future__ import annotations

import json
from pathlib import Path

from node_asset_exporter import export_latest_node_assets


def test_export_latest_node_assets_builds_component_asset(tmp_path: Path):
    records_dir = tmp_path / "records"
    assets_dir = tmp_path / "assets"
    records_dir.mkdir(parents=True)

    phase2_record = {
        "context_state": {
            "phase2_driver_snapshot": {
                "YbbSelect_busiData": {
                    "flowData": {
                        "busiId": "EST-001",
                        "nameId": "NAME-001",
                        "currCompUrl": "YbbSelect",
                        "status": "10",
                    },
                    "linkData": {
                        "compUrl": "YbbSelect",
                        "compUrlPaths": ["YbbSelect"],
                        "busiCompComb": {
                            "compComb": "BusinessLicenceWay,YbbSelect,PreElectronicDoc,PreSubmitSuccess",
                            "processToBusiComp": "fill|1-26,confirm|27",
                        },
                        "compCombArr": ["BusinessLicenceWay", "YbbSelect", "PreElectronicDoc", "PreSubmitSuccess"],
                    },
                    "jurisdiction": ["loadbusinessData", "operationBusinessData", "loadCurrentLocation"],
                    "itemId": "",
                    "signInfo": "1425944578",
                    "currentLocationVo": {
                        "fillInfoStepList": ["fill"],
                        "readOnlyStepList": ["confirm"],
                    },
                    "processVo": {
                        "currentStep": "fill",
                        "currentComp": "YbbSelect",
                    },
                    "fieldList": [
                        {
                            "field": "isSelectYbb",
                            "fieldDesc": "业务流程模式：",
                            "mustFlag": "1",
                            "readonly": None,
                            "sensitive": None,
                            "gjhCode": "register.establish.YbbSelect.isSelectYbb",
                            "sort": 1,
                            "compUrl": "YbbSelect",
                        }
                    ],
                }
            },
            "problems": [
                {
                    "step_name": "[23] establish/YbbSelect/operationBusinessDataInfo [save]",
                    "protocol_step": 23,
                    "code": "STEP_NOT_ADVANCED",
                    "category": "step_not_advanced",
                    "severity": "recoverable",
                    "message": "未推进",
                    "meaning": "接口返回成功，但服务端状态没有推进",
                    "suggested_action": "检查推进合同",
                    "current_comp_url": "YbbSelect",
                    "current_status": "10",
                }
            ],
        },
        "steps": [
            {
                "name": "establish/YbbSelect/operationBusinessDataInfo [save]",
                "ok": True,
                "code": "00000",
                "resultType": "0",
                "message": "",
                "extracted": {
                    "ybb_followup_component": "PreElectronicDoc",
                    "ybb_followup_code": "D0010",
                    "ybb_followup_message": "当前表单无需填写",
                    "expected_components": ["PreElectronicDoc", "PreSubmitSuccess"],
                },
                "diagnostics": {
                    "protocol_step": 23,
                    "page_name": "云帮办流程模式选择",
                    "business_stage_name": "第二阶段：信息填报",
                    "category": "success",
                    "severity": "info",
                },
            }
        ],
    }
    smart_record = {
        "latest_diagnosis": {
            "step_name": "[24] establish/PreElectronicDoc/operationBusinessDataInfo [save]",
            "page_name": "预电子文档 / 信息确认",
            "category": "business_status_changed",
        },
        "last_phase2_state": {
            "phase2_driver_snapshot": {
                "last_save_flowData": {
                    "currCompUrl": "PreElectronicDoc",
                    "status": "10",
                }
            }
        },
        "checkpoint": {
            "context_state": {
                "phase2_driver_snapshot": {
                    "YbbSelect_busiData": {
                        "fieldList": [
                            {
                                "field": "preAuditSign",
                                "fieldDesc": "预审标记：",
                                "mustFlag": "0",
                                "gjhCode": "register.establish.YbbSelect.preAuditSign",
                                "sort": 2,
                                "compUrl": "YbbSelect",
                            }
                        ]
                    }
                }
            }
        },
    }
    survey_record = {
        "YbbSelect": {
            "compUrl": "YbbSelect",
            "label": "云帮办流程模式选择",
            "route": "ybb-select",
            "hash": "#/flow/base/ybb-select",
            "fields": [
                {"label": "业务流程模式", "required": True, "type": "radio", "readonly": False}
            ],
            "radioGroups": [
                {"label": "业务流程模式：", "options": ["一般流程办理", "云帮办流程办理"]}
            ],
            "visible_buttons": ["保存并下一步", "保存"],
            "dialogs": [
                {"title": "提示", "body_preview": "请选择业务流程模式", "buttons": ["确定"]}
            ],
            "apiCalls": [
                {"url": "v4/pc/register/establish/component/YbbSelect/loadBusinessDataInfo", "method": "POST"}
            ],
        }
    }

    (records_dir / "phase2_establish_latest.json").write_text(json.dumps(phase2_record, ensure_ascii=False, indent=2), encoding="utf-8")
    (records_dir / "smart_register_latest.json").write_text(json.dumps(smart_record, ensure_ascii=False, indent=2), encoding="utf-8")
    (records_dir / "1151_establish_full_survey.json").write_text(json.dumps(survey_record, ensure_ascii=False, indent=2), encoding="utf-8")

    result = export_latest_node_assets(records_dir=records_dir, assets_dir=assets_dir)

    manifest = json.loads((assets_dir / "node_assets_latest.json").read_text(encoding="utf-8"))
    asset = json.loads((assets_dir / "node_assets" / "YbbSelect.json").read_text(encoding="utf-8"))

    assert result["node_count"] >= 1
    assert manifest["node_count"] >= 1
    assert asset["comp_url"] == "YbbSelect"
    assert "load_business_data" in asset["functions"]
    assert "progression_transition" in asset["functions"]
    assert asset["prompt_assets"]["visible_buttons"] == ["保存并下一步", "保存"]
    assert "STEP_NOT_ADVANCED" in asset["error_assets"]["codes"]
    assert asset["protocol_contract"]["expected_components"] == ["PreElectronicDoc", "PreSubmitSuccess"]
    assert asset["ui_assets"]["field_summary"]["total"] == 2


def test_export_latest_node_assets_marks_route_hash_mismatch_as_invalid_ui(tmp_path: Path):
    records_dir = tmp_path / "records"
    assets_dir = tmp_path / "assets"
    records_dir.mkdir(parents=True)

    (records_dir / "phase2_establish_latest.json").write_text(json.dumps({"context_state": {}, "steps": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    (records_dir / "smart_register_latest.json").write_text(json.dumps({}, ensure_ascii=False, indent=2), encoding="utf-8")
    (records_dir / "1151_establish_full_survey.json").write_text(
        json.dumps(
            {
                "YbbSelect": {
                    "compUrl": "YbbSelect",
                    "label": "云帮办流程模式选择",
                    "route": "ybb-select",
                    "hash": "#/flow/base/basic-info",
                    "fields": [{"label": "错误页面字段", "required": True}],
                    "visible_buttons": ["保存并下一步"],
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    export_latest_node_assets(records_dir=records_dir, assets_dir=assets_dir)

    asset = json.loads((assets_dir / "node_assets" / "YbbSelect.json").read_text(encoding="utf-8"))

    assert asset["asset_quality"]["ui_capture_valid"] is False
    assert "route_hash_mismatch" in asset["asset_quality"]["flags"]
    assert asset["ui_assets"]["field_summary"]["total"] == 0
    assert asset["prompt_assets"]["visible_buttons"] == []
