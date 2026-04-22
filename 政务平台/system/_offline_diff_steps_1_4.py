"""
纯离线对比：driver 构造的 step 1-4 请求体 与 mitm 备份里真实浏览器发的 step 1-4 请求体。
找出字段级差异，帮助判断 SESSION 状态机是否一致。

不发任何请求。只读磁盘。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "system"))

from phase1_protocol_driver import (  # noqa: E402
    API_BANNED_LEXICON,
    API_CHECK_ESTABLISH_NAME,
    API_LOAD_CURRENT_LOCATION,
    API_NC_LOAD,
    DriverContext,
    step_check_establish_name,
    step_load_current_location,
    step_namecheck_load,
    step_banned_lexicon,
)


class _IntBody(Exception):
    def __init__(self, method: str, path: str, body_or_params: Any):
        self.method = method
        self.path = path
        self.body_or_params = body_or_params


class _InterceptClient:
    """调用 post_json / get_json 时不发请求，而是抛出异常把 body/params 透出来。"""

    def post_json(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        raise _IntBody("POST", path, body)

    def get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise _IntBody("GET", path, params or {})


def _intercept_body(step_fn, c: DriverContext) -> Dict[str, Any]:
    try:
        step_fn(_InterceptClient(), c)
    except _IntBody as e:
        return {"method": e.method, "path": e.path, "body_or_params": e.body_or_params}
    return {"error": "step function did not call client"}

OUT = ROOT / "dashboard/data/records/_offline_diff_steps_1_4.json"


def _load_case() -> DriverContext:
    case = json.loads((ROOT / "docs/case_广西容县李陈梦.json").read_text(encoding="utf-8"))
    return DriverContext.from_case(case)


def _load_mitm_samples() -> Dict[str, List[Dict[str, Any]]]:
    """按 api path 分组收集 mitm 备份里的请求样本（只保留 POST 且 req_body 非空）。"""
    buckets: Dict[str, List[Dict[str, Any]]] = {
        API_CHECK_ESTABLISH_NAME: [],
        API_LOAD_CURRENT_LOCATION: [],
        API_NC_LOAD: [],
        API_BANNED_LEXICON: [],
    }
    mitm = ROOT / "dashboard/data/records/mitm_ufo_flows_backup_20260421_231343.jsonl"
    if not mitm.exists():
        return buckets
    with mitm.open("r", encoding="utf-8", errors="replace") as f:
        for ln, line in enumerate(f, 1):
            try:
                rec = json.loads(line)
            except Exception:
                continue
            url = str(rec.get("url") or "")
            path = url.split("?")[0].replace("https://zhjg.scjdglj.gxzf.gov.cn:9087", "")
            if path not in buckets:
                continue
            method = str(rec.get("method") or "").upper()
            if method == "GET":
                # GET 请求无 body，只看 query 参数（针对 bannedLexicon 这种 GET）
                from urllib.parse import parse_qs, urlparse
                q = parse_qs(urlparse(url).query)
                # parse_qs 返回 list，转成 single-value dict（drop "t"=timestamp）
                params = {k: (v[0] if isinstance(v, list) else v) for k, v in q.items() if k != "t"}
                buckets[path].append({"line": ln, "body": params, "method": "GET"})
                continue
            if method != "POST":
                continue
            req_body = rec.get("req_body") or ""
            if not req_body:
                continue
            try:
                body = json.loads(req_body) if isinstance(req_body, str) else req_body
            except Exception:
                continue
            buckets[path].append({"line": ln, "body": body, "method": "POST"})
    return buckets


def _diff(driver_body: Dict[str, Any], sample_body: Dict[str, Any]) -> Dict[str, Any]:
    dk = set(driver_body.keys())
    sk = set(sample_body.keys())
    diff: Dict[str, Any] = {
        "only_in_driver": sorted(dk - sk),
        "only_in_sample": sorted(sk - dk),
        "value_diff": {},
    }
    for k in sorted(dk & sk):
        if driver_body[k] != sample_body[k]:
            diff["value_diff"][k] = {
                "driver": driver_body[k],
                "sample": sample_body[k],
            }
    return diff


def main() -> int:
    c = _load_case()
    # 用拦截 client 捕获每个 step 实际发出的 body（保证和 driver 运行时一致）
    driver_bodies_raw = {
        API_CHECK_ESTABLISH_NAME: _intercept_body(step_check_establish_name, c),
        API_LOAD_CURRENT_LOCATION: _intercept_body(step_load_current_location, c),
        API_NC_LOAD: _intercept_body(step_namecheck_load, c),
        API_BANNED_LEXICON: _intercept_body(step_banned_lexicon, c),
    }
    # 解包：提取 body_or_params
    driver_bodies: Dict[str, Any] = {
        path: rec.get("body_or_params") for path, rec in driver_bodies_raw.items()
    }
    mitm_buckets = _load_mitm_samples()

    report: Dict[str, Any] = {"schema": "offline_diff_steps_1_4.v1", "steps": {}}
    for path, driver_body in driver_bodies.items():
        samples = mitm_buckets.get(path) or []
        rec = {
            "api": path,
            "driver_body": driver_body,
            "sample_count": len(samples),
            "sample_line_hint": [s["line"] for s in samples[:5]],
            "sample_body_first": samples[0]["body"] if samples else None,
            "diff_vs_first_sample": _diff(driver_body, samples[0]["body"]) if samples else None,
        }
        report["steps"][path] = rec

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== step1-4 body 离线 diff ===")
    for path, rec in report["steps"].items():
        name = path.rsplit("/", 1)[-1]
        print(f"\n--- {name}  (mitm 样本数={rec['sample_count']}) ---")
        if not rec["sample_count"]:
            print("  [跳过] 备份里找不到此 api 的真实样本")
            continue
        d = rec["diff_vs_first_sample"]
        print(f"  only_in_driver : {d['only_in_driver']}")
        print(f"  only_in_sample : {d['only_in_sample']}")
        if d["value_diff"]:
            print("  value_diff:")
            for k, v in d["value_diff"].items():
                dv = json.dumps(v["driver"], ensure_ascii=False)
                sv = json.dumps(v["sample"], ensure_ascii=False)
                print(f"    {k}")
                print(f"      driver : {dv[:140]}")
                print(f"      sample : {sv[:140]}")
        else:
            print("  value_diff : (none)")

    print(f"\nsaved: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
