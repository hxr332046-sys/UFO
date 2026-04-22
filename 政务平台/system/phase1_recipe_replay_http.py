#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
按录制 JSON 里 **已存在的** `/icpsp-api/` POST 顺序重放（用当前会话头）。

**不要求你再跑 CDP**：`--recipe auto`（默认）会优先选用仓库里**以前已成功**的录制，顺序为：
- `packet_listen_namecheck_once.json`（XHR hook：operationBusinessDataInfo + nameCheckRepeat）
- `stage1_replay_namecheck_operation.json`（mitm 成功 `operationBusinessDataInfo` 整包）
- `phase1_icpsp_recipe_latest.json`（CDP Network；可能只有 GET 时会被跳过）

- 默认 dry-run；`--execute` 才真实 POST（需 runtime_auth_headers / mitm 等有效 Authorization）。
- `busiId`：仍做浅层从上一响应回填顶层空字段。

用法:
  python system/phase1_recipe_replay_http.py
  python system/phase1_recipe_replay_http.py --recipe auto --execute
  python system/phase1_recipe_replay_http.py --recipe dashboard/data/records/packet_listen_namecheck_once.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

from icpsp_api_client import ICPSPClient  # noqa: E402

RECORDS = ROOT / "dashboard" / "data" / "records"
# 优先带完整 POST 体的历史录制；最后才用可能只有 GET 的 CDP recipe
RECIPE_CANDIDATES = [
    RECORDS / "packet_listen_namecheck_once.json",
    RECORDS / "stage1_replay_namecheck_operation.json",
    RECORDS / "phase1_icpsp_recipe_latest.json",
]
OUT = RECORDS / "phase1_recipe_replay_http_latest.json"
ICPSP_BASE = "https://zhjg.scjdglj.gxzf.gov.cn:9087"


def _path_from_icpsp_url(url: str) -> str:
    u = urlparse(url)
    return u.path or ""


def rows_from_any_recording(raw: Dict[str, Any]) -> tuple[List[Dict[str, Any]], str]:
    """
    统一抽出「时间序的 icpsp 请求行」，兼容：
    - phase1_icpsp_recipe.v1（icpsp_requests_chronological）
    - packet_listen_namecheck_once（XHR items）
    - stage1_replay_namecheck_operation（单条 mitm 成功体）
    """
    rows = raw.get("icpsp_requests_chronological")
    if isinstance(rows, list) and rows:
        return rows, "icpsp_recipe_v1"

    if "replay_request" in raw and isinstance(raw.get("replay_request"), dict):
        mitm = raw.get("picked_from_mitm") or {}
        url = str(mitm.get("url") or "").strip()
        body = (raw.get("replay_request") or {}).get("body")
        if url and "/icpsp-api/" in url and isinstance(body, dict):
            return (
                [
                    {
                        "ts": 0,
                        "method": "POST",
                        "url": url,
                        "postData_len": 0,
                        "post_json": body,
                    }
                ],
                "stage1_replay_namecheck_operation",
            )

    out: List[Dict[str, Any]] = []
    for step in raw.get("steps") or []:
        if not isinstance(step, dict):
            continue
        data = step.get("data") if isinstance(step.get("data"), dict) else {}
        for it in data.get("items") or []:
            if not isinstance(it, dict):
                continue
            if str(it.get("m") or "").upper() != "POST":
                continue
            u = str(it.get("u") or "")
            if "/icpsp-api/" not in u:
                continue
            url = u if u.startswith("http") else ICPSP_BASE + (u if u.startswith("/") else "/" + u)
            pd = str(it.get("body") or "")
            row: Dict[str, Any] = {"ts": it.get("ts"), "method": "POST", "url": url, "postData_len": len(pd)}
            try:
                row["post_json"] = json.loads(pd)
            except json.JSONDecodeError:
                row["postData_preview"] = pd[:4000]
            out.append(row)
    if out:
        return out, "packet_listen_namecheck_once"

    return [], "unknown"


def _post_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [r for r in rows if str(r.get("method") or "").upper() == "POST" and isinstance(r.get("post_json"), dict)]


def _pick_recipe_file(explicit: str) -> Path:
    e = (explicit or "").strip()
    if e.lower() in ("", "auto"):
        for p in RECIPE_CANDIDATES:
            if not p.is_file():
                continue
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            rows, _ = rows_from_any_recording(raw)
            if _post_rows(rows):
                return p
        raise FileNotFoundError(
            "auto：下列候选均无可用 POST JSON（或文件损坏）：" + ", ".join(str(p) for p in RECIPE_CANDIDATES)
        )
    p = Path(e)
    if not p.is_file():
        raise FileNotFoundError(f"recipe 文件不存在: {p}")
    return p


def _find_busi_id(obj: Any, depth: int = 0) -> Optional[str]:
    if depth > 8 or obj is None:
        return None
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "busiId" and v is not None and str(v).strip() and str(v).lower() != "null":
                return str(v).strip()
            got = _find_busi_id(v, depth + 1)
            if got:
                return got
    if isinstance(obj, list):
        for it in obj[:30]:
            got = _find_busi_id(it, depth + 1)
            if got:
                return got
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--recipe",
        type=str,
        default="auto",
        help="录制文件路径，或 auto=按顺序选用仓库内已有记录（无需再跑 CDP）",
    )
    ap.add_argument("--execute", action="store_true", help="真实发 POST（否则 dry-run）")
    args = ap.parse_args()

    try:
        recipe_path = _pick_recipe_file(args.recipe)
    except FileNotFoundError as e:
        print("ERROR:", e)
        return 2

    raw = json.loads(recipe_path.read_text(encoding="utf-8"))
    rows, fmt = rows_from_any_recording(raw)
    posts = _post_rows(rows)

    rec: Dict[str, Any] = {
        "schema": "ufo.phase1_recipe_replay.v1",
        "recipe": str(recipe_path),
        "recipe_format": fmt,
        "post_count": len(posts),
        "dry_run": not args.execute,
        "steps": [],
    }
    last_busi: Optional[str] = None
    client: Optional[ICPSPClient] = None
    if args.execute:
        client = ICPSPClient()

    for i, row in enumerate(posts):
        url = str(row.get("url") or "")
        body: Dict[str, Any] = dict(row.get("post_json") or {})
        path = _path_from_icpsp_url(url)
        if not path.startswith("/icpsp-api/"):
            rec["steps"].append({"i": i, "skip": True, "reason": "not_icpsp_path", "path": path})
            continue
        if last_busi and ("busiId" in body) and (body.get("busiId") in (None, "", "null")):
            body = dict(body)
            body["busiId"] = last_busi

        if not args.execute:
            rec["steps"].append(
                {
                    "i": i,
                    "path": path,
                    "body_keys": sorted(body.keys())[:40],
                    "busiId_in_body": body.get("busiId"),
                }
            )
            continue

        assert client is not None
        try:
            resp = client.post_json(path, body)
        except Exception as e:
            rec["steps"].append({"i": i, "path": path, "error": str(e)})
            break
        nb = _find_busi_id(resp)
        if nb:
            last_busi = nb
        rec["steps"].append(
            {
                "i": i,
                "path": path,
                "response_code": resp.get("code") if isinstance(resp, dict) else None,
                "picked_busiId_from_response": nb,
            }
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"saved": str(OUT), "steps": len(rec["steps"]), "execute": args.execute}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
