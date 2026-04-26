#!/usr/bin/env python
"""政务平台协议化 CLI — 覆盖 27 个 FastAPI 端点。

用法总览（python -m phase1_service.cli <command>）：

  # 认证
  auth-status [--probe]                                     # 检查 token
  auth-keepalive                                            # ping 保活
  auth-refresh                                              # 静默续期（2 秒）
  auth-ensure                                               # 智能获取 token
  auth-qr-start [--user-type 1]                             # 生成二维码
  auth-qr-status --sid <sid>                                # 轮询扫码状态

  # Phase 1 核名
  precheck <name_mark> [--remote]                           # 名字预检
  register --case <path> [--auth <token>]                   # 7 步核名
  supplement --busi-id <id> --case <path>                   # 信息补充+提交

  # Phase 2 设立
  phase2-register --case <path> [--busi-id] [--name-id] [--start-from] [--stop-after] [--auto-phase1]
  phase2-session-recover                                    # CDP → Python session
  phase2-progress --busi-id --name-id [--ent-type] [--busi-type]
  phase2-cache-stats                                        # 幂等缓存统计

  # 办件管理
  matters-list [--search] [--page] [--size] [--state]
  matters-detail --busi-id [--name-id]

  # 字典（本地 + 实时）
  dict {ent-types|industries|organizes|regions|name-prefixes} [--entType ...] [--distCode ...]
  scope --entType --keyword [--busiType]                    # 本地经营范围
  scope-search --keyword [--industry-code] [--limit]        # 实时搜索

  # 系统参数
  sysparam-snapshot [--keys K1,K2] [--no-mask]
  sysparam-key <key>                                        # 单 key 查询
  sysparam-refresh                                          # 从平台刷新

  # 调试辅助
  mitm-samples --api-pattern <X> [--opeType] [--code] [--limit]
  mitm-latest --api-pattern <X> [--only-success]
  mitm-stats

  # 通用
  call <METHOD> <PATH> [--json <body>]                      # 直接调任意端点
  schema [--group auth|phase1|phase2|...|core]              # 导出 LLM tools
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

DEFAULT_BASE = "http://127.0.0.1:8800"


# ─── HTTP helpers ───

def _post(base: str, path: str, body: dict | None = None) -> dict:
    r = requests.post(f"{base}{path}", json=body or {}, timeout=60)
    try:
        return r.json()
    except Exception:
        return {"_status": r.status_code, "_text": r.text[:500]}


def _get(base: str, path: str, params: dict | None = None) -> dict:
    r = requests.get(f"{base}{path}", params=params or {}, timeout=30)
    try:
        return r.json()
    except Exception:
        return {"_status": r.status_code, "_text": r.text[:500]}


def _print(result: dict) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _load_case(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"ERROR: case file not found: {p}", file=sys.stderr)
        sys.exit(2)
    return json.loads(p.read_text(encoding="utf-8"))


def _fail_if(cond: bool) -> None:
    if cond:
        sys.exit(1)


# ─── Auth ───

def cmd_auth_status(a):
    r = _get(a.base, "/api/phase1/auth/status", {"probe": "true"} if a.probe else {})
    _print(r)
    _fail_if(not r.get("valid"))


def cmd_auth_keepalive(a):
    _print(_post(a.base, "/api/phase1/auth/keepalive"))


def cmd_auth_refresh(a):
    r = _post(a.base, "/api/auth/token/refresh")
    _print(r)
    _fail_if(not r.get("success"))


def cmd_auth_ensure(a):
    r = _post(a.base, "/api/auth/token/ensure")
    _print(r)
    _fail_if(not r.get("success"))


def cmd_auth_qr_start(a):
    r = _post(a.base, f"/api/auth/qr/start?user_type={a.user_type}")
    # 隐藏 base64 长字串
    if isinstance(r.get("qr_image_base64"), str):
        n = len(r["qr_image_base64"])
        r = {**r, "qr_image_base64": f"<base64 len={n}>"}
    _print(r)
    if r.get("sid"):
        print(f"\n[hint] 轮询命令: python -m phase1_service.cli auth-qr-status --sid {r['sid']}")


def cmd_auth_qr_status(a):
    r = _get(a.base, "/api/auth/qr/status", {"sid": a.sid})
    _print(r)
    _fail_if(not r.get("success") and not r.get("pending"))


# ─── Phase 1 ───

def cmd_precheck(a):
    r = _post(a.base, "/api/phase1/precheck_name", {"name_mark": a.name_mark, "remote": a.remote})
    _print(r)
    _fail_if(r.get("verdict") != "ok")


def cmd_register(a):
    body = {"case": _load_case(a.case)}
    if a.auth:
        body["authorization"] = a.auth
    r = _post(a.base, "/api/phase1/register", body)
    _print(r)
    _fail_if(not r.get("success"))


def cmd_supplement(a):
    body = {"busi_id": a.busi_id, "case": _load_case(a.case)}
    if a.auth:
        body["authorization"] = a.auth
    r = _post(a.base, "/api/phase1/supplement", body)
    _print(r)
    _fail_if(not r.get("success"))


# ─── Phase 2 ───

def cmd_phase2_register(a):
    body = {
        "case": _load_case(a.case),
        "start_from": a.start_from,
        "stop_after": a.stop_after,
        "auto_phase1": a.auto_phase1,
    }
    if a.busi_id:
        body["busi_id"] = a.busi_id
    if a.name_id:
        body["name_id"] = a.name_id
    if a.auth:
        body["authorization"] = a.auth
    r = _post(a.base, "/api/phase2/register", body)
    _print(r)
    _fail_if(not r.get("success"))


def cmd_phase2_session_recover(a):
    _print(_post(a.base, "/api/phase2/session/recover"))


def cmd_phase2_progress(a):
    params = {"busi_id": a.busi_id, "name_id": a.name_id,
              "ent_type": a.ent_type, "busi_type": a.busi_type}
    r = _get(a.base, "/api/phase2/progress", params)
    _print(r)
    _fail_if(not r.get("success"))


def cmd_phase2_cache_stats(a):
    _print(_get(a.base, "/api/phase2/cache/stats"))


# ─── Matters ───

def cmd_matters_list(a):
    params = {"search": a.search, "page": a.page, "size": a.size, "state": a.state}
    r = _get(a.base, "/api/matters/list", params)
    _print(r)
    _fail_if(not r.get("success"))


def cmd_matters_detail(a):
    params = {"busi_id": a.busi_id}
    if a.name_id:
        params["name_id"] = a.name_id
    r = _get(a.base, "/api/matters/detail", params)
    _print(r)
    _fail_if(not r.get("success"))


# ─── Dict ───

def cmd_dict(a):
    dt = a.dict_type
    if dt == "ent-types":
        r = _get(a.base, "/api/phase1/dict/ent-types", {"level": a.level})
    elif dt == "industries":
        r = _get(a.base, f"/api/phase1/dict/industries/{a.entType}", {"busiType": a.busiType})
    elif dt == "organizes":
        r = _get(a.base, f"/api/phase1/dict/organizes/{a.entType}", {"busiType": a.busiType})
    elif dt == "regions":
        r = _get(a.base, "/api/phase1/dict/regions")
    elif dt == "name-prefixes":
        r = _get(a.base, f"/api/phase1/dict/name-prefixes/{a.distCode}/{a.entType}")
    else:
        print(f"Unknown dict type: {dt}", file=sys.stderr)
        sys.exit(2)
    _print(r)


def cmd_scope(a):
    r = _get(a.base, "/api/phase1/scope", {"entType": a.entType, "busiType": a.busiType, "keyword": a.keyword})
    _print(r)


def cmd_scope_search(a):
    params = {"keyword": a.keyword, "limit": a.limit}
    if a.industry_code:
        params["industry_code"] = a.industry_code
    r = _get(a.base, "/api/phase1/scope/search", params)
    _print(r)
    _fail_if(not r.get("success"))


# ─── System ───

def cmd_sysparam_snapshot(a):
    params = {"mask_keys": str(not a.no_mask).lower()}
    if a.keys:
        params["keys"] = a.keys
    r = _get(a.base, "/api/system/sysparam/snapshot", params)
    _print(r)


def cmd_sysparam_key(a):
    r = _get(a.base, f"/api/system/sysparam/key/{a.key}")
    _print(r)
    _fail_if(not r.get("success"))


def cmd_sysparam_refresh(a):
    r = _post(a.base, "/api/system/sysparam/refresh")
    _print(r)
    _fail_if(not r.get("success"))


# ─── Debug ───

def cmd_mitm_samples(a):
    params = {"api_pattern": a.api_pattern, "limit": a.limit}
    if a.opeType:
        params["opeType"] = a.opeType
    if a.code:
        params["code"] = a.code
    _print(_get(a.base, "/api/debug/mitm/samples", params))


def cmd_mitm_latest(a):
    _print(_get(a.base, "/api/debug/mitm/latest",
                 {"api_pattern": a.api_pattern, "only_success": str(a.only_success).lower()}))


def cmd_mitm_stats(a):
    _print(_get(a.base, "/api/debug/mitm/stats"))


# ─── Generic & Schema ───

def cmd_call(a):
    """通用端点调用：cli call GET /api/phase2/cache/stats  /  cli call POST /api/auth/token/ensure"""
    method = a.method.upper()
    body = None
    if a.json_str:
        body = json.loads(a.json_str)
    if method == "GET":
        r = _get(a.base, a.path)
    elif method == "POST":
        r = _post(a.base, a.path, body)
    else:
        print(f"Unsupported method: {method}", file=sys.stderr)
        sys.exit(2)
    _print(r)


def cmd_schema(a):
    from phase1_service.api.llm_function_schema import export
    print(export(a.group))


# ─── argparse 布线 ───

def _build_parser():
    p = argparse.ArgumentParser(prog="phase1_service.cli", description="政务平台协议化 CLI（27 端点）")
    p.add_argument("--base", default=DEFAULT_BASE)
    sub = p.add_subparsers(dest="command", required=True)

    # auth
    sp = sub.add_parser("auth-status"); sp.add_argument("--probe", action="store_true"); sp.set_defaults(func=cmd_auth_status)
    sp = sub.add_parser("auth-keepalive"); sp.set_defaults(func=cmd_auth_keepalive)
    sp = sub.add_parser("auth-refresh"); sp.set_defaults(func=cmd_auth_refresh)
    sp = sub.add_parser("auth-ensure"); sp.set_defaults(func=cmd_auth_ensure)
    sp = sub.add_parser("auth-qr-start"); sp.add_argument("--user-type", type=int, default=1, choices=[1, 2]); sp.set_defaults(func=cmd_auth_qr_start)
    sp = sub.add_parser("auth-qr-status"); sp.add_argument("--sid", required=True); sp.set_defaults(func=cmd_auth_qr_status)

    # phase 1
    sp = sub.add_parser("precheck"); sp.add_argument("name_mark"); sp.add_argument("--remote", action="store_true"); sp.set_defaults(func=cmd_precheck)
    sp = sub.add_parser("register"); sp.add_argument("--case", required=True); sp.add_argument("--auth"); sp.set_defaults(func=cmd_register)
    sp = sub.add_parser("supplement"); sp.add_argument("--busi-id", required=True, dest="busi_id"); sp.add_argument("--case", required=True); sp.add_argument("--auth"); sp.set_defaults(func=cmd_supplement)

    # phase 2
    sp = sub.add_parser("phase2-register")
    sp.add_argument("--case", required=True)
    sp.add_argument("--busi-id", dest="busi_id")
    sp.add_argument("--name-id", dest="name_id")
    sp.add_argument("--start-from", dest="start_from", type=int, default=1)
    sp.add_argument("--stop-after", dest="stop_after", type=int, default=14)
    sp.add_argument("--auto-phase1", dest="auto_phase1", action="store_true")
    sp.add_argument("--auth")
    sp.set_defaults(func=cmd_phase2_register)

    sp = sub.add_parser("phase2-session-recover"); sp.set_defaults(func=cmd_phase2_session_recover)

    sp = sub.add_parser("phase2-progress")
    sp.add_argument("--busi-id", dest="busi_id", required=True)
    sp.add_argument("--name-id", dest="name_id", required=True)
    sp.add_argument("--ent-type", dest="ent_type", default="4540")
    sp.add_argument("--busi-type", dest="busi_type", default="02_4")
    sp.set_defaults(func=cmd_phase2_progress)

    sp = sub.add_parser("phase2-cache-stats"); sp.set_defaults(func=cmd_phase2_cache_stats)

    # matters
    sp = sub.add_parser("matters-list")
    sp.add_argument("--search", default=""); sp.add_argument("--page", type=int, default=1)
    sp.add_argument("--size", type=int, default=10); sp.add_argument("--state", default="")
    sp.set_defaults(func=cmd_matters_list)

    sp = sub.add_parser("matters-detail")
    sp.add_argument("--busi-id", dest="busi_id", required=True); sp.add_argument("--name-id", dest="name_id")
    sp.set_defaults(func=cmd_matters_detail)

    # dict
    sp = sub.add_parser("dict")
    sp.add_argument("dict_type", choices=["ent-types", "industries", "organizes", "regions", "name-prefixes"])
    sp.add_argument("--entType", default="4540"); sp.add_argument("--busiType", default="01")
    sp.add_argument("--distCode", default=""); sp.add_argument("--level", type=int, default=1)
    sp.set_defaults(func=cmd_dict)

    sp = sub.add_parser("scope")
    sp.add_argument("--entType", default="4540"); sp.add_argument("--busiType", default="01"); sp.add_argument("--keyword", required=True)
    sp.set_defaults(func=cmd_scope)

    sp = sub.add_parser("scope-search")
    sp.add_argument("--keyword", required=True); sp.add_argument("--industry-code", dest="industry_code")
    sp.add_argument("--limit", type=int, default=20)
    sp.set_defaults(func=cmd_scope_search)

    # system
    sp = sub.add_parser("sysparam-snapshot")
    sp.add_argument("--keys"); sp.add_argument("--no-mask", action="store_true", dest="no_mask")
    sp.set_defaults(func=cmd_sysparam_snapshot)

    sp = sub.add_parser("sysparam-key"); sp.add_argument("key"); sp.set_defaults(func=cmd_sysparam_key)

    sp = sub.add_parser("sysparam-refresh"); sp.set_defaults(func=cmd_sysparam_refresh)

    # debug
    sp = sub.add_parser("mitm-samples")
    sp.add_argument("--api-pattern", dest="api_pattern", required=True)
    sp.add_argument("--opeType"); sp.add_argument("--code"); sp.add_argument("--limit", type=int, default=5)
    sp.set_defaults(func=cmd_mitm_samples)

    sp = sub.add_parser("mitm-latest")
    sp.add_argument("--api-pattern", dest="api_pattern", required=True)
    sp.add_argument("--only-success", dest="only_success", action="store_true", default=True)
    sp.set_defaults(func=cmd_mitm_latest)

    sp = sub.add_parser("mitm-stats"); sp.set_defaults(func=cmd_mitm_stats)

    # generic
    sp = sub.add_parser("call")
    sp.add_argument("method", choices=["GET", "POST", "get", "post"])
    sp.add_argument("path")
    sp.add_argument("--json", dest="json_str", help="JSON body string")
    sp.set_defaults(func=cmd_call)

    sp = sub.add_parser("schema")
    sp.add_argument("--group", default="all", choices=["all", "auth", "phase1", "phase2", "matters", "dict", "system", "debug", "core"])
    sp.set_defaults(func=cmd_schema)

    return p


def main():
    args = _build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
