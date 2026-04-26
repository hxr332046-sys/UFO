"""Tier B：entType × busiType 维度的字典。"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from ._common import (
    CensusState,
    PaceConfig,
    check_rate_limit,
    do_get,
    extract_busi_data,
    pace_sleep,
    save_payload,
)
from icpsp_api_client import ICPSPClient  # type: ignore


def _collect_ent_types(data_dir: Path) -> List[str]:
    """从 Tier A 保存的 ent_types_type1.json 里提取所有 entType 代码。"""
    p = data_dir / "dictionaries/ent_types_type1.json"
    if not p.exists():
        return []
    try:
        wrapper = json.loads(p.read_text(encoding="utf-8"))
        resp = wrapper.get("data") or {}
        bd = extract_busi_data(resp)
        return _extract_codes_from_tree(bd)
    except Exception as e:
        print(f"  [tier_b] failed to parse ent_types_type1.json: {e!r}")
        return []


def _extract_codes_from_tree(node: Any) -> List[str]:
    """递归从层级树里收集所有叶子 code（以及可能作为可选 entType 的中间节点）。"""
    codes: List[str] = []
    if isinstance(node, list):
        for it in node:
            codes.extend(_extract_codes_from_tree(it))
    elif isinstance(node, dict):
        c = node.get("code") or node.get("entType") or node.get("id")
        if c and isinstance(c, str) and c.isdigit() and len(c) == 4:
            codes.append(c)
        for v in node.values():
            codes.extend(_extract_codes_from_tree(v))
    # 去重保持顺序
    seen = set()
    out = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def run_tier_b(
    client: ICPSPClient,
    tier_b_config: Dict[str, Any],
    data_dir: Path,
    state: CensusState,
    pace: PaceConfig,
    *,
    force: bool = False,
    only_ent_types: List[str] | None = None,
) -> None:
    ent_types = only_ent_types or _collect_ent_types(data_dir)
    if not ent_types:
        raise RuntimeError("Tier B 无法启动：ent_types_type1.json 未找到或解析失败（请先跑 Tier A）")

    busi_types = tier_b_config.get("busi_types", ["01"])
    templates = tier_b_config.get("templates", [])

    total_combos = len(ent_types) * len(busi_types) * len(templates)
    print(f"  [B] entTypes={len(ent_types)} × busiTypes={len(busi_types)} × templates={len(templates)} = {total_combos} 请求")

    i = 0
    for et in ent_types:
        for bt in busi_types:
            for tpl in templates:
                i += 1
                job_id = tpl["id"]
                params = {k: v.replace("{entType}", et).replace("{busiType}", bt) for k, v in tpl["params_template"].items()}
                ckey = state.key(f"B:{job_id}", params)
                save_rel = tpl["save_as"].replace("{entType}", et).replace("{busiType}", bt)
                out_path = data_dir / save_rel

                if not force and ckey in state.completed:
                    print(f"  [B {i}/{total_combos}] {job_id:20s} entType={et} bt={bt}  [skip]")
                    continue

                print(f"  [B {i}/{total_combos}] {job_id:20s} entType={et} bt={bt}  -> {save_rel}")
                started = time.time()
                resp = do_get(client, tpl["path"], params)
                dur_ms = int((time.time() - started) * 1000)

                if check_rate_limit(resp):
                    state.d0029_count += 1
                    print(f"     !! D0029 限流，累计 {state.d0029_count}，冷却 {pace.d0029_cooldown_sec}s ...")
                    time.sleep(pace.d0029_cooldown_sec)
                    if state.d0029_count >= pace.d0029_retry_threshold:
                        raise RuntimeError(f"Tier B D0029 连续 {state.d0029_count} 次，中止")
                    continue

                code = str(resp.get("code") or "")
                if code != "00000":
                    state.failed[ckey] = {"job_id": f"B:{job_id}", "params": params, "resp": resp, "ts": int(time.time())}
                    print(f"     X code={code} msg={resp.get('msg')}")
                    pace_sleep(pace)
                    continue

                save_payload(
                    out_path, resp,
                    {"job_id": f"B:{job_id}", "path": tpl["path"], "params": params, "dur_ms": dur_ms, "ts": int(time.time())},
                )
                state.completed[ckey] = {"status": "ok", "saved_path": save_rel, "ts": int(time.time()), "dur_ms": dur_ms}
                state.total_requests += 1
                state.d0029_count = 0
                print(f"     OK  {dur_ms}ms")

                pace_sleep(pace)
