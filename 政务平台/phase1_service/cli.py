#!/usr/bin/env python
"""Phase1 CLI — LLM 或人工可直接命令行调用。

用法：
  # 预检名字
  python -m phase1_service.cli precheck 李陈梦
  python -m phase1_service.cli precheck 美美的

  # 注册（从 case JSON 文件）
  python -m phase1_service.cli register --case docs/case_广西容县李陈梦.json

  # 查字典
  python -m phase1_service.cli dict ent-types
  python -m phase1_service.cli dict industries --entType 4540
  python -m phase1_service.cli dict organizes --entType 4540
  python -m phase1_service.cli dict regions

  # 查经营范围
  python -m phase1_service.cli scope --entType 4540 --keyword 软件开发

  # 检查 auth
  python -m phase1_service.cli auth [--probe]

  # 导出 LLM function schema
  python -m phase1_service.cli schema
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

DEFAULT_BASE = "http://127.0.0.1:8800"


def _post(base: str, path: str, body: dict) -> dict:
    r = requests.post(f"{base}{path}", json=body, timeout=30)
    return r.json()


def _get(base: str, path: str, params: dict | None = None) -> dict:
    r = requests.get(f"{base}{path}", params=params or {}, timeout=15)
    return r.json()


def cmd_precheck(args):
    result = _post(args.base, "/api/phase1/precheck_name", {
        "name_mark": args.name_mark,
        "remote": args.remote,
    })
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("verdict") != "ok":
        sys.exit(1)


def cmd_register(args):
    case_path = Path(args.case)
    if not case_path.exists():
        print(f"ERROR: case file not found: {case_path}", file=sys.stderr)
        sys.exit(2)
    case = json.loads(case_path.read_text(encoding="utf-8"))
    body = {"case": case}
    if args.auth:
        body["authorization"] = args.auth
    result = _post(args.base, "/api/phase1/register", body)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("success"):
        sys.exit(1)


def cmd_dict(args):
    if args.dict_type == "ent-types":
        result = _get(args.base, "/api/phase1/dict/ent-types")
    elif args.dict_type == "industries":
        result = _get(args.base, f"/api/phase1/dict/industries/{args.entType}")
    elif args.dict_type == "organizes":
        result = _get(args.base, f"/api/phase1/dict/organizes/{args.entType}")
    elif args.dict_type == "regions":
        result = _get(args.base, "/api/phase1/dict/regions")
    else:
        print(f"Unknown dict type: {args.dict_type}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_scope(args):
    result = _get(args.base, "/api/phase1/scope", {
        "entType": args.entType,
        "busiType": args.busiType,
        "keyword": args.keyword,
    })
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_auth(args):
    params = {"probe": "true"} if args.probe else {}
    result = _get(args.base, "/api/phase1/auth/status", params)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("valid"):
        sys.exit(1)


def cmd_schema(args):
    from phase1_service.api.llm_function_schema import export
    print(export())


def main():
    parser = argparse.ArgumentParser(prog="phase1_service.cli", description="Phase1 名称登记 CLI")
    parser.add_argument("--base", default=DEFAULT_BASE, help="API base URL")
    sub = parser.add_subparsers(dest="command", required=True)

    # precheck
    p = sub.add_parser("precheck", help="名字预检")
    p.add_argument("name_mark", help="企业字号")
    p.add_argument("--remote", action="store_true", help="启用远程校验")
    p.set_defaults(func=cmd_precheck)

    # register
    p = sub.add_parser("register", help="执行 7 步注册")
    p.add_argument("--case", required=True, help="case JSON 路径")
    p.add_argument("--auth", help="32-hex Authorization")
    p.set_defaults(func=cmd_register)

    # dict
    p = sub.add_parser("dict", help="查字典")
    p.add_argument("dict_type", choices=["ent-types", "industries", "organizes", "regions"])
    p.add_argument("--entType", default="4540")
    p.set_defaults(func=cmd_dict)

    # scope
    p = sub.add_parser("scope", help="查经营范围")
    p.add_argument("--entType", default="4540")
    p.add_argument("--busiType", default="01")
    p.add_argument("--keyword", required=True)
    p.set_defaults(func=cmd_scope)

    # auth
    p = sub.add_parser("auth", help="检查认证状态")
    p.add_argument("--probe", action="store_true")
    p.set_defaults(func=cmd_auth)

    # schema
    p = sub.add_parser("schema", help="导出 LLM function calling schema")
    p.set_defaults(func=cmd_schema)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
