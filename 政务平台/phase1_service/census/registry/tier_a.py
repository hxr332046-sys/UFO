"""Tier A：无参数字典。每个接口只需一次请求。"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List

from ._common import (
    CensusState,
    PaceConfig,
    check_rate_limit,
    do_get,
    pace_sleep,
    save_payload,
)
from icpsp_api_client import ICPSPClient  # type: ignore


def run_tier_a(
    client: ICPSPClient,
    plan_items: List[Dict[str, Any]],
    data_dir: Path,
    state: CensusState,
    pace: PaceConfig,
    *,
    force: bool = False,
) -> None:
    """遍历 Tier A 清单，落盘每个接口响应到 data_dir 下。"""
    total = len(plan_items)
    for i, item in enumerate(plan_items, 1):
        job_id = item["id"]
        params = item.get("params") or {}
        ckey = state.key(job_id, params)
        if not force and ckey in state.completed:
            print(f"  [A {i}/{total}] {job_id:30s} [skip] already done")
            continue

        out_path = data_dir / item["save_as"]
        print(f"  [A {i}/{total}] {job_id:30s} GET {item['path']}  -> {item['save_as']}")
        started = time.time()
        resp = do_get(client, item["path"], params)
        dur_ms = int((time.time() - started) * 1000)

        if check_rate_limit(resp):
            state.d0029_count += 1
            print(f"     !! D0029 限流，累计 {state.d0029_count}；冷却 {pace.d0029_cooldown_sec}s ...")
            time.sleep(pace.d0029_cooldown_sec)
            if state.d0029_count >= pace.d0029_retry_threshold:
                raise RuntimeError(f"Tier A: D0029 连续 {state.d0029_count} 次，中止普查")
            continue

        code = str(resp.get("code") or "")
        if code != "00000":
            state.failed[ckey] = {"job_id": job_id, "params": params, "resp": resp, "ts": int(time.time())}
            print(f"     X 失败: code={code} msg={resp.get('msg')}")
            continue

        save_payload(
            out_path,
            resp,
            {"job_id": job_id, "path": item["path"], "params": params, "dur_ms": dur_ms, "ts": int(time.time())},
        )
        state.completed[ckey] = {"status": "ok", "saved_path": str(out_path.relative_to(data_dir.parent)), "ts": int(time.time()), "dur_ms": dur_ms}
        state.total_requests += 1
        state.d0029_count = 0  # 成功一次就清 0
        print(f"     OK  {dur_ms}ms")

        pace_sleep(pace)
