#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一次 CDP 门户链任务的标准元数据：run_id、状态、事件摘要（ufo.gov_task_run.v1）。"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

GOV_TASK_RUN_SCHEMA = "ufo.gov_task_run.v1"

_INTERESTING_EXACT = frozenset(
    {
        "reached_yun_submit",
        "reached_guide_base",
        "abort_s08_stagnation_cap",
        "stopped_without_yun_submit",
        "blocked_need_login",
        "s08_exit_diagnostic",
        "aborted_cdp_or_eval",
        "try_activefuc_establish",
        "fallback_dom_click_establish",
        "snap_after_resume",
        "snap_after_portal_nav",
        "final_snap",
    }
)


def new_run_id() -> str:
    return str(uuid.uuid4())


def _brief_for_step(step_name: str, s: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    d = s.get("data")
    if step_name == "aborted_cdp_or_eval":
        err = s.get("error")
        return {"error": err} if err else None
    if not isinstance(d, dict):
        return None
    brief: Dict[str, Any] = {}
    for k in ("href", "hash", "l3_step_code", "hasYunSubmit", "likelyLoggedIn", "reason"):
        if k in d and d[k] is not None:
            brief[k] = d[k]
    if step_name.startswith("blocker_evidence_") or step_name.startswith("blocker_"):
        tag = d.get("tag")
        ui = d.get("ui")
        if isinstance(ui, dict):
            brief["ui_href"] = ui.get("href")
            brief["messageBox"] = (ui.get("messageBox") or "")[:200] or None
            brief["errors_head"] = (ui.get("errors") or [])[:3]
        if tag:
            brief["tag"] = tag
    return brief or None


def digest_steps_to_events(steps: Optional[List[Dict[str, Any]]], max_events: int = 120) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i, s in enumerate(steps or []):
        if len(out) >= max_events:
            break
        name = s.get("step")
        if not isinstance(name, str) or not name:
            continue
        if name in _INTERESTING_EXACT:
            pass
        elif name.startswith("milestone_") or name.startswith("before_primary_round_"):
            pass
        elif name.startswith("blocker_evidence_"):
            pass
        else:
            continue
        ev: Dict[str, Any] = {"i": i, "step": name}
        b = _brief_for_step(name, s)
        if b:
            ev["brief"] = b
        out.append(ev)
    return out


def _reached_core(steps: List[Dict[str, Any]]) -> bool:
    for s in steps:
        d = s.get("data")
        if not isinstance(d, dict):
            continue
        h = d.get("href")
        if isinstance(h, str) and "core.html" in h:
            return True
        sn = s.get("step")
        if isinstance(sn, str) and sn.startswith("before_primary_round_"):
            h2 = d.get("href")
            if isinstance(h2, str) and "core.html" in h2:
                return True
    return False


def finalize_task_model(rec: Dict[str, Any]) -> Dict[str, Any]:
    """依赖 rec 已含 steps、acceptance、run_id；在 build_acceptance 之后调用。"""
    steps = rec.get("steps") or []
    reached_yun = any(s.get("step") == "reached_yun_submit" for s in steps)
    reached_core = _reached_core(steps)
    run_err = rec.get("run_error")
    no_cdp = rec.get("error") == "no_cdp_page"
    if no_cdp or run_err:
        state = "failed"
    elif reached_yun:
        state = "completed"
    else:
        state = "partial"

    ac = rec.get("acceptance") or []
    ac_all = all(bool(x.get("ok")) for x in ac) if ac else True

    return {
        "schema": GOV_TASK_RUN_SCHEMA,
        "goal": "portal_chain_to_yun_submit_stop",
        "run_id": rec.get("run_id"),
        "state": state,
        "events": digest_steps_to_events(steps),
        "summary": {
            "reached_yun_submit": reached_yun,
            "reached_core": reached_core,
            "acceptance_all_ok": ac_all,
            "has_run_error": bool(run_err),
            "no_cdp_page": bool(no_cdp),
        },
    }
