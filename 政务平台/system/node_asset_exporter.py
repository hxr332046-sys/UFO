from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RECORDS_DIR = ROOT / "dashboard" / "data" / "records"
DEFAULT_ASSETS_DIR = ROOT / "dashboard" / "data" / "assets"
DEFAULT_NODE_ASSETS_DIR = DEFAULT_ASSETS_DIR / "node_assets"
STEP_COMPONENT_RE = re.compile(r"(?:^|\s)(?:name|establish)/([A-Za-z0-9_]+)/")


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _walk(value: Any) -> Iterable[Any]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _short(value: Any, limit: int = 240) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit]


def _dedupe_strings(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _dedupe_dicts(values: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for value in values:
        if not isinstance(value, dict):
            continue
        key = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _component_from_step_name(step_name: Any) -> str:
    match = STEP_COMPONENT_RE.search(str(step_name or ""))
    if match:
        return match.group(1)
    return ""


def _action_from_step_name(step_name: Any) -> str:
    text = str(step_name or "")
    lower = text.lower()
    if "loadcurrentlocationinfo" in lower:
        return "load_current_location"
    if "loadbusinessinfolist" in lower:
        return "load_business_list"
    if "loadbusinessdatainfo" in lower:
        return "load_business_data"
    if "operationbusinessdatainfo" in lower:
        if "[save" in lower:
            return "save"
        if "[special" in lower:
            return "special"
        return "operation_business_data"
    if "matters/operate" in lower:
        return "matters_operate"
    if "submit" in lower:
        return "submit"
    return ""


def _coerce_bool_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "y", "yes"}


def _extract_component_from_busi_data(key: str, value: Dict[str, Any]) -> str:
    link_data = value.get("linkData") or {}
    flow_data = value.get("flowData") or {}
    field_list = value.get("fieldList") or []
    comp = str(link_data.get("compUrl") or flow_data.get("currCompUrl") or "").strip()
    if comp:
        return comp
    for field in field_list:
        field_comp = str((field or {}).get("compUrl") or "").strip()
        if field_comp:
            return field_comp
    if key.endswith("_busiData"):
        raw = key[: -len("_busiData")]
        if raw == "basicinfo":
            return "BasicInfo"
        if raw:
            return raw
    return ""


def _score_busi_data(value: Dict[str, Any]) -> int:
    return (
        len(value.get("fieldList") or []) * 5
        + len(value.get("jurisdiction") or []) * 3
        + (10 if value.get("linkData") else 0)
        + (10 if value.get("flowData") else 0)
        + (4 if value.get("currentLocationVo") else 0)
        + (2 if value.get("processVo") else 0)
    )


def _build_survey_index(records_dir: Path) -> Dict[str, Dict[str, Any]]:
    best: Dict[str, Tuple[int, Dict[str, Any]]] = {}
    for path in sorted(records_dir.glob("*survey*.json")):
        payload = _load_json(path)
        if not isinstance(payload, dict):
            continue
        for key, value in payload.items():
            if not isinstance(value, dict):
                continue
            comp = str(value.get("compUrl") or key or "").strip()
            if not comp:
                continue
            score = (
                len(value.get("fields") or [])
                + len(value.get("radioGroups") or value.get("radio_groups") or [])
                + len(value.get("tables") or value.get("table_rows") or [])
                + len(value.get("apiCalls") or [])
                + len(value.get("dialogs") or [])
                + len(value.get("visible_buttons") or [])
            )
            enriched = dict(value)
            enriched["_source_file"] = str(path)
            existing = best.get(comp)
            if not existing or score >= existing[0]:
                best[comp] = (score, enriched)
    return {comp: item[1] for comp, item in best.items()}


def _build_snapshot_index(*snapshots: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    scores: Dict[str, int] = defaultdict(int)
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        for key, value in snapshot.items():
            if not isinstance(value, dict):
                continue
            comp = _extract_component_from_busi_data(key, value)
            if not comp:
                continue
            score = _score_busi_data(value)
            current = index.get(comp) or {
                "field_list": [],
                "jurisdiction": [],
                "flow_data": {},
                "link_data": {},
                "process_vo": {},
                "current_location_vo": {},
                "item_id": "",
                "sign_info": "",
                "busi_data": {},
            }
            current["field_list"] = _dedupe_dicts([*(current.get("field_list") or []), *(value.get("fieldList") or [])])
            current["jurisdiction"] = _dedupe_strings([*(current.get("jurisdiction") or []), *(value.get("jurisdiction") or [])])
            if score >= scores.get(comp, 0):
                current["flow_data"] = value.get("flowData") or current.get("flow_data") or {}
                current["link_data"] = value.get("linkData") or current.get("link_data") or {}
                current["process_vo"] = value.get("processVo") or current.get("process_vo") or {}
                current["current_location_vo"] = value.get("currentLocationVo") or current.get("current_location_vo") or {}
                current["item_id"] = value.get("itemId") or current.get("item_id") or ""
                current["sign_info"] = value.get("signInfo") or current.get("sign_info") or ""
                current["busi_data"] = value
                scores[comp] = score
            index[comp] = current
    return index


def _extract_sequence(*sources: Dict[str, Any]) -> Tuple[List[str], str]:
    best: List[str] = []
    process_map = ""
    for source in sources:
        for node in _walk(source):
            if not isinstance(node, dict):
                continue
            arr = node.get("compCombArr")
            if isinstance(arr, list) and len(arr) > len(best):
                best = [str(item).strip() for item in arr if str(item or "").strip()]
            busi_comp_comb = node.get("busiCompComb") or {}
            if isinstance(busi_comp_comb, dict):
                comp_comb = str(busi_comp_comb.get("compComb") or "").strip()
                if comp_comb:
                    comp_arr = [item.strip() for item in comp_comb.split(",") if item.strip()]
                    if len(comp_arr) > len(best):
                        best = comp_arr
                proc = str(busi_comp_comb.get("processToBusiComp") or "").strip()
                if proc and len(proc) >= len(process_map):
                    process_map = proc
    return best, process_map


def _normalize_server_fields(field_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for field in field_list:
        if not isinstance(field, dict):
            continue
        row = {
            "field": str(field.get("field") or "").strip(),
            "field_desc": str(field.get("fieldDesc") or "").strip(),
            "must": _coerce_bool_flag(field.get("mustFlag")),
            "readonly": _coerce_bool_flag(field.get("readonly")),
            "sensitive": _coerce_bool_flag(field.get("sensitive")),
            "gjh_code": str(field.get("gjhCode") or "").strip(),
            "sort": field.get("sort"),
            "comp_url": str(field.get("compUrl") or "").strip(),
        }
        key = (row["field"], row["gjh_code"], row["field_desc"])
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    out.sort(key=lambda item: (item.get("sort") is None, item.get("sort") or 0, item.get("field_desc") or item.get("field") or ""))
    return out


def _extract_protocol_details(extracted: Dict[str, Any]) -> Dict[str, Any]:
    details: Dict[str, Any] = {}
    for key, value in (extracted or {}).items():
        if isinstance(value, str):
            details[key] = _short(value)
        elif isinstance(value, (bool, int, float)) or value is None:
            details[key] = value
        elif isinstance(value, list):
            details[key] = value
        elif isinstance(value, dict):
            details[key] = value
    return details


def _build_runtime_index(phase2_record: Dict[str, Any], smart_record: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    runtime: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "steps": [],
        "problems": [],
        "codes": [],
        "categories": [],
        "messages": [],
        "suggested_actions": [],
        "page_names": [],
        "business_stage_names": [],
        "expected_components": [],
        "followup_messages": [],
        "action_labels": [],
        "action_semantics": [],
    })

    for step in phase2_record.get("steps") or []:
        if not isinstance(step, dict):
            continue
        comp = _component_from_step_name(step.get("name"))
        if not comp:
            continue
        diagnostics = step.get("diagnostics") or {}
        extracted = step.get("extracted") or {}
        protocol_details = _extract_protocol_details(extracted if isinstance(extracted, dict) else {})
        action_semantics = next((str(v).strip() for k, v in protocol_details.items() if k.endswith("_action_semantics") and str(v or "").strip()), "")
        action_label = next((str(v).strip() for k, v in protocol_details.items() if k.endswith("_action_label") and str(v or "").strip()), "")
        entry = {
            "step_name": str(step.get("name") or "").strip(),
            "protocol_step": diagnostics.get("protocol_step"),
            "action": _action_from_step_name(step.get("name")),
            "action_semantics": action_semantics,
            "action_label": action_label,
            "ok": bool(step.get("ok")),
            "code": str(step.get("code") or "").strip(),
            "result_type": str(step.get("resultType") or step.get("result_type") or "").strip(),
            "message": _short(step.get("message") or diagnostics.get("message") or ""),
            "category": str(diagnostics.get("category") or "").strip(),
            "severity": str(diagnostics.get("severity") or "").strip(),
            "page_name": str(diagnostics.get("page_name") or "").strip(),
            "business_stage_name": str(diagnostics.get("business_stage_name") or "").strip(),
            "expected_components": diagnostics.get("expected_components") or extracted.get("expected_components") or [],
            "followup_component": extracted.get("ybb_followup_component"),
            "followup_code": extracted.get("ybb_followup_code"),
            "followup_message": _short(extracted.get("ybb_followup_message") or ""),
            "protocol_extracted": protocol_details,
        }
        bucket = runtime[comp]
        bucket["steps"].append(entry)
        if entry["code"]:
            bucket["codes"].append(entry["code"])
        if entry["category"]:
            bucket["categories"].append(entry["category"])
        if entry["message"]:
            bucket["messages"].append(entry["message"])
        if entry["page_name"]:
            bucket["page_names"].append(entry["page_name"])
        if entry["business_stage_name"]:
            bucket["business_stage_names"].append(entry["business_stage_name"])
        bucket["expected_components"].extend(entry["expected_components"] or [])
        if entry["followup_message"]:
            bucket["followup_messages"].append(entry["followup_message"])
        if entry["action_label"]:
            bucket["action_labels"].append(entry["action_label"])
        if entry["action_semantics"]:
            bucket["action_semantics"].append(entry["action_semantics"])

    problem_sources: List[Dict[str, Any]] = []
    ctx_state = phase2_record.get("context_state") or {}
    if isinstance(ctx_state, dict):
        problem_sources.extend(item for item in (ctx_state.get("problems") or []) if isinstance(item, dict))
    latest_diag = smart_record.get("latest_diagnosis") or {}
    if isinstance(latest_diag, dict) and latest_diag:
        problem_sources.append(latest_diag)
    for item in problem_sources:
        comp = _component_from_step_name(item.get("step_name")) or str(item.get("current_comp_url") or item.get("server_curr_comp_url") or "").strip()
        if not comp:
            continue
        problem = {
            "step_name": str(item.get("step_name") or "").strip(),
            "protocol_step": item.get("protocol_step"),
            "code": str(item.get("code") or "").strip(),
            "result_type": str(item.get("result_type") or item.get("resultType") or "").strip(),
            "message": _short(item.get("message") or ""),
            "category": str(item.get("category") or "").strip(),
            "severity": str(item.get("severity") or "").strip(),
            "meaning": _short(item.get("meaning") or ""),
            "suggested_action": _short(item.get("suggested_action") or ""),
            "recovery_action": str(item.get("recovery_action") or "").strip(),
            "current_comp_url": str(item.get("current_comp_url") or "").strip(),
            "current_status": str(item.get("current_status") or "").strip(),
        }
        bucket = runtime[comp]
        bucket["problems"].append(problem)
        if problem["code"]:
            bucket["codes"].append(problem["code"])
        if problem["category"]:
            bucket["categories"].append(problem["category"])
        if problem["message"]:
            bucket["messages"].append(problem["message"])
        if problem["meaning"]:
            bucket["messages"].append(problem["meaning"])
        if problem["suggested_action"]:
            bucket["suggested_actions"].append(problem["suggested_action"])

    for value in runtime.values():
        value["steps"] = _dedupe_dicts(value["steps"])
        value["problems"] = _dedupe_dicts(value["problems"])
        value["codes"] = _dedupe_strings(value["codes"])
        value["categories"] = _dedupe_strings(value["categories"])
        value["messages"] = _dedupe_strings(value["messages"])
        value["suggested_actions"] = _dedupe_strings(value["suggested_actions"])
        value["page_names"] = _dedupe_strings(value["page_names"])
        value["business_stage_names"] = _dedupe_strings(value["business_stage_names"])
        value["expected_components"] = _dedupe_strings(value["expected_components"])
        value["followup_messages"] = _dedupe_strings(value["followup_messages"])
        value["action_labels"] = _dedupe_strings(value["action_labels"])
        value["action_semantics"] = _dedupe_strings(value["action_semantics"])
    return runtime


def _field_summary(server_fields: List[Dict[str, Any]], survey_fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    if server_fields:
        return {
            "source": "server_field_list",
            "total": len(server_fields),
            "required": len([item for item in server_fields if item.get("must")]),
            "readonly": len([item for item in server_fields if item.get("readonly")]),
            "sensitive": len([item for item in server_fields if item.get("sensitive")]),
        }
    return {
        "source": "survey_fields",
        "total": len(survey_fields),
        "required": len([item for item in survey_fields if item.get("required")]),
        "readonly": len([item for item in survey_fields if item.get("readonly")]),
        "sensitive": len([item for item in survey_fields if item.get("sensitive")]),
    }


def _survey_quality(survey: Dict[str, Any]) -> Dict[str, Any]:
    route = str(survey.get("route") or "").strip()
    hash_value = str(survey.get("hash") or "").strip()
    flags: List[str] = []
    ui_capture_valid = True
    if route and hash_value and route not in hash_value:
        flags.append("route_hash_mismatch")
        ui_capture_valid = False
    return {
        "ui_capture_valid": ui_capture_valid,
        "flags": flags,
    }


def _build_functions(jurisdiction: List[str], survey: Dict[str, Any], runtime: Dict[str, Any], sequence: Dict[str, Any], survey_ui_valid: bool) -> List[str]:
    functions: List[str] = []
    mapping = {
        "loadbusinessList": "load_business_list",
        "loadbusinessData": "load_business_data",
        "operationBusinessData": "operation_business_data",
        "loadCurrentLocation": "load_current_location",
    }
    for item in jurisdiction:
        if item in mapping:
            functions.append(mapping[item])
    if survey_ui_valid and ((survey.get("fields") or []) or (survey.get("fieldList") or [])):
        functions.append("form_fields")
    if survey_ui_valid and (survey.get("radioGroups") or survey.get("radio_groups")):
        functions.append("radio_selection")
    if survey_ui_valid and (survey.get("tables") or survey.get("table_rows")):
        functions.append("table_view")
    if survey_ui_valid and (survey.get("visible_buttons") or survey.get("recommended_actions") or survey.get("actionables")):
        functions.append("button_actions")
    if survey_ui_valid and survey.get("dialogs"):
        functions.append("dialogs")
    if survey_ui_valid and survey.get("picker_placeholders"):
        functions.append("picker_selection")
    if runtime.get("messages") or runtime.get("problems") or (survey_ui_valid and survey.get("error_messages")):
        functions.append("validation_feedback")
    if runtime.get("steps"):
        functions.extend(step.get("action") for step in runtime.get("steps") if step.get("action"))
        functions.extend(step.get("action_semantics") for step in runtime.get("steps") if step.get("action_semantics"))
    if sequence.get("next_component") or runtime.get("expected_components"):
        functions.append("progression_transition")
    return _dedupe_strings(functions)


def _build_prompt_assets(survey: Dict[str, Any], runtime: Dict[str, Any], survey_ui_valid: bool) -> Dict[str, Any]:
    survey_source = survey if survey_ui_valid else {}
    dialogs = _dedupe_dicts(survey_source.get("dialogs") or [])
    blocking_prompts = _dedupe_strings(survey_source.get("blocking_prompts") or [])
    visible_buttons = _dedupe_strings([*(survey_source.get("visible_buttons") or []), *(runtime.get("action_labels") or [])])
    recommended_actions = _dedupe_dicts(survey_source.get("recommended_actions") or [])
    messages = _dedupe_strings([
        *(runtime.get("followup_messages") or []),
        *(runtime.get("messages") or []),
        *(survey_source.get("error_messages") or []),
    ])
    return {
        "blocking_prompts": blocking_prompts,
        "dialogs": dialogs,
        "visible_buttons": visible_buttons,
        "recommended_actions": recommended_actions,
        "messages": messages,
    }


def _build_ui_assets(survey: Dict[str, Any], server_fields: List[Dict[str, Any]], survey_ui_valid: bool) -> Dict[str, Any]:
    survey_source = survey if survey_ui_valid else {}
    survey_fields = list(survey_source.get("fields") or [])
    return {
        "label": str(survey.get("label") or "").strip(),
        "route": str(survey.get("route") or "").strip(),
        "hash": str(survey.get("hash") or "").strip(),
        "content_preview": _short(survey_source.get("content_preview") or survey_source.get("page_text_preview") or "", 600),
        "field_summary": _field_summary(server_fields, survey_fields),
        "server_fields": server_fields,
        "survey_fields": survey_fields,
        "radio_groups": survey_source.get("radioGroups") or survey_source.get("radio_groups") or [],
        "tables": survey_source.get("tables") or survey_source.get("table_rows") or [],
        "picker_placeholders": survey_source.get("picker_placeholders") or [],
        "vuex": survey_source.get("vuex") or {},
        "api_calls": survey_source.get("apiCalls") or [],
    }


def _build_protocol_contract(snapshot_entry: Dict[str, Any], runtime: Dict[str, Any], sequence: Dict[str, Any], process_to_busi_comp: str) -> Dict[str, Any]:
    return {
        "jurisdiction": snapshot_entry.get("jurisdiction") or [],
        "observed_actions": _dedupe_strings(step.get("action") for step in runtime.get("steps") or []),
        "observed_steps": runtime.get("steps") or [],
        "expected_components": runtime.get("expected_components") or [],
        "process_to_busi_comp": process_to_busi_comp,
        "flow_data_sample": snapshot_entry.get("flow_data") or {},
        "link_data_sample": snapshot_entry.get("link_data") or {},
        "process_vo": snapshot_entry.get("process_vo") or {},
        "current_location_vo": snapshot_entry.get("current_location_vo") or {},
        "item_id_sample": snapshot_entry.get("item_id") or "",
        "sign_info_sample": str(snapshot_entry.get("sign_info") or ""),
        "sequence": sequence,
    }


def _build_error_assets(survey: Dict[str, Any], runtime: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "codes": runtime.get("codes") or [],
        "categories": runtime.get("categories") or [],
        "messages": _dedupe_strings([*(runtime.get("messages") or []), *(survey.get("error_messages") or [])]),
        "suggested_actions": runtime.get("suggested_actions") or [],
        "problems": runtime.get("problems") or [],
    }


def _build_runtime_assets(snapshot_entry: Dict[str, Any], runtime: Dict[str, Any], smart_record: Dict[str, Any]) -> Dict[str, Any]:
    latest_diagnosis = smart_record.get("latest_diagnosis") or {}
    return {
        "page_names": runtime.get("page_names") or [],
        "business_stage_names": runtime.get("business_stage_names") or [],
        "latest_flow_data": snapshot_entry.get("flow_data") or {},
        "latest_link_data": snapshot_entry.get("link_data") or {},
        "latest_diagnosis": latest_diagnosis if isinstance(latest_diagnosis, dict) else {},
        "recent_steps": runtime.get("steps") or [],
    }


def export_latest_node_assets(records_dir: Path = DEFAULT_RECORDS_DIR, assets_dir: Path = DEFAULT_ASSETS_DIR) -> Dict[str, Any]:
    records_dir = Path(records_dir)
    assets_dir = Path(assets_dir)
    node_assets_dir = assets_dir / "node_assets"

    phase2_record = _load_json(records_dir / "phase2_establish_latest.json")
    smart_record = _load_json(records_dir / "smart_register_latest.json")
    survey_index = _build_survey_index(records_dir)

    phase2_ctx = phase2_record.get("context_state") or {}
    smart_state = smart_record.get("last_phase2_state") or {}
    checkpoint = smart_record.get("checkpoint") or {}
    checkpoint_state = (checkpoint.get("context_state") or {}) if isinstance(checkpoint, dict) else {}

    phase2_snapshot = phase2_ctx.get("phase2_driver_snapshot") or {}
    smart_snapshot = smart_state.get("phase2_driver_snapshot") or {}
    checkpoint_snapshot = checkpoint_state.get("phase2_driver_snapshot") or {}
    snapshot_index = _build_snapshot_index(phase2_snapshot, smart_snapshot, checkpoint_snapshot)
    runtime_index = _build_runtime_index(phase2_record, smart_record)
    comp_sequence, process_to_busi_comp = _extract_sequence(phase2_snapshot, smart_snapshot, checkpoint_snapshot, phase2_record, smart_record)

    components = _dedupe_strings([
        *comp_sequence,
        *survey_index.keys(),
        *snapshot_index.keys(),
        *runtime_index.keys(),
    ])

    node_assets_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    manifest_nodes: List[Dict[str, Any]] = []

    for comp in components:
        survey = survey_index.get(comp) or {}
        snapshot_entry = snapshot_index.get(comp) or {}
        runtime = runtime_index.get(comp) or {}
        survey_quality = _survey_quality(survey)
        server_fields = _normalize_server_fields(snapshot_entry.get("field_list") or [])
        page_names = runtime.get("page_names") or []
        page_name = str(survey.get("label") or (page_names[0] if page_names else "")).strip()
        stage_names = runtime.get("business_stage_names") or []
        sequence_index = comp_sequence.index(comp) if comp in comp_sequence else -1
        previous_component = comp_sequence[sequence_index - 1] if sequence_index > 0 else ""
        next_component = comp_sequence[sequence_index + 1] if sequence_index >= 0 and sequence_index + 1 < len(comp_sequence) else ""
        sequence = {
            "index": sequence_index if sequence_index >= 0 else None,
            "previous_component": previous_component or None,
            "next_component": next_component or None,
            "comp_comb_arr": comp_sequence,
        }
        prompt_assets = _build_prompt_assets(survey, runtime, survey_quality["ui_capture_valid"])
        functions = _build_functions(snapshot_entry.get("jurisdiction") or [], survey, runtime, sequence, survey_quality["ui_capture_valid"])
        asset = {
            "schema": "ufo.node_asset.v1",
            "generated_at": generated_at,
            "comp_url": comp,
            "page_name": page_name,
            "business_stage_name": stage_names[0] if stage_names else "",
            "asset_quality": survey_quality,
            "functions": functions,
            "protocol_contract": _build_protocol_contract(snapshot_entry, runtime, sequence, process_to_busi_comp),
            "ui_assets": _build_ui_assets(survey, server_fields, survey_quality["ui_capture_valid"]),
            "prompt_assets": prompt_assets,
            "error_assets": _build_error_assets(survey, runtime),
            "runtime_assets": _build_runtime_assets(snapshot_entry, runtime, smart_record),
            "sources": {
                "survey_file": str(survey.get("_source_file") or ""),
                "phase2_record": str(records_dir / "phase2_establish_latest.json") if phase2_record else "",
                "smart_record": str(records_dir / "smart_register_latest.json") if smart_record else "",
            },
        }
        path = node_assets_dir / f"{comp}.json"
        path.write_text(json.dumps(asset, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest_nodes.append({
            "comp_url": comp,
            "page_name": page_name,
            "business_stage_name": stage_names[0] if stage_names else "",
            "functions": functions,
            "error_codes": asset["error_assets"]["codes"],
            "prompt_count": len(prompt_assets["messages"]) + len(prompt_assets["dialogs"]) + len(prompt_assets["blocking_prompts"]),
            "field_total": asset["ui_assets"]["field_summary"]["total"],
            "asset_file": str(path),
        })

    manifest = {
        "schema": "ufo.node_assets_manifest.v1",
        "generated_at": generated_at,
        "records_dir": str(records_dir),
        "assets_dir": str(assets_dir),
        "node_count": len(manifest_nodes),
        "nodes": manifest_nodes,
    }
    assets_dir.mkdir(parents=True, exist_ok=True)
    latest_manifest = assets_dir / "node_assets_latest.json"
    latest_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "manifest_path": str(latest_manifest),
        "node_count": len(manifest_nodes),
        "node_assets_dir": str(node_assets_dir),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records-dir", type=Path, default=DEFAULT_RECORDS_DIR)
    ap.add_argument("--assets-dir", type=Path, default=DEFAULT_ASSETS_DIR)
    args = ap.parse_args()
    result = export_latest_node_assets(records_dir=args.records_dir, assets_dir=args.assets_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
