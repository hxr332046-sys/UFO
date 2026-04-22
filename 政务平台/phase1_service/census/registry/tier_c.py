"""Tier C：entType × 区划（distCode）维度。"""
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
    from .tier_b import _collect_ent_types as fn  # 复用 Tier B 的实现
    return fn(data_dir)


def _collect_dist_codes(data_dir: Path, max_level: int = 3) -> List[str]:
    """从 Tier A regcode_street_root 或 queryRegcodeAndStreet_latest 提取区划 code。
    max_level=3 意为 省/市/县三级；max_level=2 只到市级。"""
    p = data_dir / "dictionaries/regions/root.json"
    if not p.exists():
        # 退化到原有 dict_cache
        alt = data_dir.parent.parent / "dashboard/data/records/dict_cache/queryRegcodeAndStreet_latest.json"
        if alt.exists():
            p = alt
        else:
            return []
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        # 兼容 Tier A 落盘格式 (wrapper) 和 dict_cache 原始格式
        resp = d.get("data") if isinstance(d, dict) and "data" in d else d
        bd = extract_busi_data(resp) if isinstance(resp, dict) else resp
        if isinstance(d, dict) and "data" in d and isinstance(d["data"], dict):
            bd = extract_busi_data(d["data"])
        codes = _walk_regions(bd, 0, max_level)
        # dedup
        seen, out = set(), []
        for c in codes:
            if c not in seen:
                seen.add(c)
                out.append(c)
        return out
    except Exception as e:
        print(f"  [tier_c] parse regions failed: {e!r}")
        return []


def _walk_regions(node: Any, depth: int, max_level: int) -> List[str]:
    out: List[str] = []
    if depth >= max_level:
        return out
    if isinstance(node, list):
        for it in node:
            out.extend(_walk_regions(it, depth, max_level))
    elif isinstance(node, dict):
        code = node.get("id") or node.get("code") or node.get("regCode") or node.get("distCode")
        if code and isinstance(code, str) and code.isdigit():
            out.append(code)
        children = node.get("children")
        if children:
            out.extend(_walk_regions(children, depth + 1, max_level))
    return out


def run_tier_c(
    client: ICPSPClient,
    tier_c_config: Dict[str, Any],
    data_dir: Path,
    state: CensusState,
    pace: PaceConfig,
    *,
    force: bool = False,
    only_ent_types: List[str] | None = None,
    only_dist_codes: List[str] | None = None,
) -> None:
    ent_types = only_ent_types or _collect_ent_types(data_dir)
    max_level = int(tier_c_config.get("dist_level_max", 3))
    dist_codes = only_dist_codes or _collect_dist_codes(data_dir, max_level)

    if not ent_types or not dist_codes:
        raise RuntimeError(f"Tier C 无法启动：ent_types={len(ent_types)}, dist_codes={len(dist_codes)}")

    templates = tier_c_config.get("templates", [])
    total_combos = len(ent_types) * len(dist_codes) * len(templates)
    print(f"  [C] entTypes={len(ent_types)} × distCodes={len(dist_codes)} × templates={len(templates)} = {total_combos} 请求")
    if total_combos > 5000:
        print(f"  [!] 组合数 {total_combos} 过大，预计耗时 {total_combos * 2.5 / 3600:.1f}h。建议用 --limit 或限制 max_level。")

    i = 0
    for et in ent_types:
        for dc in dist_codes:
            for tpl in templates:
                i += 1
                job_id = tpl["id"]
                params = {k: v.replace("{entType}", et).replace("{distCode}", dc) for k, v in tpl["params_template"].items()}
                ckey = state.key(f"C:{job_id}", params)
                save_rel = tpl["save_as"].replace("{entType}", et).replace("{distCode}", dc)
                out_path = data_dir / save_rel

                if not force and ckey in state.completed:
                    if i % 50 == 0:
                        print(f"  [C {i}/{total_combos}] {job_id} et={et} dc={dc}  [skip]")
                    continue

                print(f"  [C {i}/{total_combos}] {job_id:15s} et={et} dc={dc}")
                started = time.time()
                resp = do_get(client, tpl["path"], params)
                dur_ms = int((time.time() - started) * 1000)

                if check_rate_limit(resp):
                    state.d0029_count += 1
                    print(f"     !! D0029 累计 {state.d0029_count}，冷却 {pace.d0029_cooldown_sec}s")
                    time.sleep(pace.d0029_cooldown_sec)
                    if state.d0029_count >= pace.d0029_retry_threshold:
                        raise RuntimeError("Tier C D0029 连续多次，中止")
                    continue

                code = str(resp.get("code") or "")
                if code != "00000":
                    state.failed[ckey] = {"job_id": f"C:{job_id}", "params": params, "resp_code": code, "ts": int(time.time())}
                    pace_sleep(pace)
                    continue

                save_payload(out_path, resp, {"job_id": f"C:{job_id}", "path": tpl["path"], "params": params, "dur_ms": dur_ms, "ts": int(time.time())})
                state.completed[ckey] = {"status": "ok", "saved_path": save_rel, "ts": int(time.time()), "dur_ms": dur_ms}
                state.total_requests += 1
                state.d0029_count = 0

                pace_sleep(pace)
