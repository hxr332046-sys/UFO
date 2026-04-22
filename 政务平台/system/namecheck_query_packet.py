#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
包级名称可用性查询（不走 UI）：bannedLexiconCalibration + nameCheckRepeat。

输入尽量贴近前端请求体，输出结构化解释：
- ok / stop
- 命中条目（名称库冲突、限制用字等）
- 系统提示（tipStr / langStateCode）

用法：
  cd G:\\UFO\\政务平台
  .\\.venv-portal\\Scripts\\python.exe system\\namecheck_query_packet.py --dist 450000 --entType 1100 --name 广西星彤创科技有限公司 --industry 7519 --indSpec 科技 --organize 有限公司
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from icpsp_api_client import ICPSPClient


def _pick(d: Any, path: str, default: Any = None) -> Any:
    cur = d
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def _explain_repeat(resp: Dict[str, Any]) -> Dict[str, Any]:
    data = resp.get("data") if isinstance(resp.get("data"), dict) else {}
    busi = data.get("busiData") if isinstance(data.get("busiData"), dict) else {}
    check_state = busi.get("checkState")
    lang = busi.get("langStateCode") or _pick(busi, "modResult.langStateCodeCC")
    result_flag = _pick(busi, "modResult.resultFlag")
    hits = busi.get("checkResult") if isinstance(busi.get("checkResult"), list) else []
    top_hit = hits[0] if hits else None
    remark = top_hit.get("remark") if isinstance(top_hit, dict) else None
    same_name = False
    if isinstance(top_hit, dict):
        same_name = str(top_hit.get("remark") or "").find("名称相同") >= 0
    stop = (check_state == 2) or (result_flag == 2) or bool(same_name)
    return {
        "stop": bool(stop),
        "checkState": check_state,
        "langStateCode": lang,
        "resultFlag": result_flag,
        "top_remark": remark,
        "hit_count": len(hits),
        "hits_top3": hits[:3],
    }


def _explain_banned(resp: Dict[str, Any]) -> Dict[str, Any]:
    data = resp.get("data") if isinstance(resp.get("data"), dict) else {}
    busi = data.get("busiData") if isinstance(data.get("busiData"), dict) else {}
    return {
        "success": busi.get("success"),
        "tipWay": busi.get("tipWay"),
        "tipStr": busi.get("tipStr"),
        "tipKeyWords": busi.get("tipKeyWords"),
        "restLevel": _pick(busi, "bannedLexiconInfo.0.restLevel"),
        "restTypeName": _pick(busi, "bannedLexiconInfo.0.restTypeName"),
        "raw": busi,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--namePre", default="广西")
    ap.add_argument("--nameMark", default="")
    ap.add_argument("--dist", dest="distCode", default="450000")
    ap.add_argument("--area", dest="areaCode", default=None)
    ap.add_argument("--entType", default="1100")
    ap.add_argument("--busiType", default="01")
    ap.add_argument("--organize", default="有限公司")
    ap.add_argument("--industry", default="7519")
    ap.add_argument("--indSpec", default="科技")
    args = ap.parse_args()

    name = args.name.strip()
    name_mark = args.nameMark.strip() or (name.replace(args.namePre, "").replace(args.organize, "")[:6])
    area = args.areaCode or args.distCode

    c = ICPSPClient()

    # 1) 禁限用字词校验（按前端：nameMark 逐步输入；这里直接用完整字号）
    banned = c.get_json(
        "/icpsp-api/v4/pc/register/verifidata/bannedLexiconCalibration",
        {"nameMark": name_mark},
    )

    # 2) 名称库查重（核心）
    repeat_body = {
        "condition": "1",
        "busiId": None,
        "busiType": args.busiType,
        "entType": args.entType,
        "name": name,
        "namePre": args.namePre,
        "nameMark": name_mark,
        "distCode": args.distCode,
        "areaCode": area,
        "organize": args.organize,
        "industry": args.industry,
        "indSpec": args.indSpec,
        "hasParent": None,
        "jtParentEntName": "",
    }
    repeat = c.post_json("/icpsp-api/v4/pc/register/name/component/NameCheckInfo/nameCheckRepeat", repeat_body)

    out = {
        "input": {
            "name": name,
            "namePre": args.namePre,
            "nameMark": name_mark,
            "distCode": args.distCode,
            "areaCode": area,
            "entType": args.entType,
            "busiType": args.busiType,
            "organize": args.organize,
            "industry": args.industry,
            "indSpec": args.indSpec,
        },
        "bannedLexiconCalibration": {
            "code": banned.get("code"),
            "explain": _explain_banned(banned if isinstance(banned, dict) else {}),
        },
        "nameCheckRepeat": {
            "code": repeat.get("code") if isinstance(repeat, dict) else None,
            "explain": _explain_repeat(repeat if isinstance(repeat, dict) else {}),
        },
    }
    # overall
    stop = bool(_pick(out, "nameCheckRepeat.explain.stop")) or (not bool(_pick(out, "bannedLexiconCalibration.explain.success", True)))
    out["overall"] = {"ok": not stop, "stop": stop}

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

