#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build V2 dictionary DB from current survey artifacts + protocol knowledge."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from dict_v2_store import (
    begin_run,
    clear_v2_data,
    connect,
    end_run,
    init_schema,
    insert_dict_item,
    insert_operation_method,
    stats,
    upsert_api_spec,
)


ROOT = Path("G:/UFO/政务平台")
DICT_DIR = ROOT / "dashboard" / "data" / "records" / "dict_cache"
OUT_REPORT = ROOT / "dashboard" / "data" / "records" / "dict_v2_build_latest.json"


def _load(name: str) -> Dict[str, Any]:
    p = DICT_DIR / name
    return json.loads(p.read_text(encoding="utf-8"))


def _insert_ent_types(con, run_id: int) -> None:
    for fn, cat in [("queryNameEntType_type1_latest.json", "ent_type_type1"), ("queryNameEntType_type2_latest.json", "ent_type_type2")]:
        j = _load(fn)
        arr = ((j.get("data") or {}).get("busiData") or {}).get("pagetypes") or []
        for x in arr:
            if not isinstance(x, dict):
                continue
            insert_dict_item(
                con,
                category=cat,
                code=str(x.get("code") or ""),
                name=str(x.get("name") or ""),
                parent_code=str(x.get("parcode") or "") or None,
                tags=["step1", "主体类型"],
                tip_ok="主体类型已选择，可进入下一步并联动后续组织形式/名称规则。",
                tip_error="主体类型未选将停留当前页并出现必填校验。",
                recommendation="先确定 entType，再执行区划/组织形式/行业选择，减少分支误差。",
                source_api="/icpsp-api/v4/pc/common/synchrdata/queryNameEntType",
                source_file=fn,
                raw_json=x,
                run_id=run_id,
            )


def _insert_regions(con, run_id: int) -> None:
    fn = "queryRegcodeAndStreet_latest.json"
    j = _load(fn)
    arr = ((j.get("data") or {}).get("busiData")) or []
    for prov in arr:
        if not isinstance(prov, dict):
            continue
        pcode = str(prov.get("id") or "")
        insert_dict_item(
            con,
            category="region",
            code=pcode,
            name=str(prov.get("name") or ""),
            parent_code=None,
            tags=["区划", "省"],
            tip_ok="区划选择有效，名称前缀与后续查重范围可计算。",
            tip_error="未选区划会触发区划必填提示，无法稳定进入名称核查。",
            recommendation="查询时尽量使用目标区县代码，不要长期只用省级代码。",
            source_api="/icpsp-api/v4/pc/common/synchrdata/queryRegcodeAndStreet",
            source_file=fn,
            raw_json=prov,
            run_id=run_id,
        )
        for city in prov.get("children") or []:
            if not isinstance(city, dict):
                continue
            ccode = str(city.get("id") or "")
            insert_dict_item(
                con,
                category="region",
                code=ccode,
                name=str(city.get("name") or ""),
                parent_code=pcode,
                tags=["区划", "市"],
                source_api="/icpsp-api/v4/pc/common/synchrdata/queryRegcodeAndStreet",
                source_file=fn,
                raw_json=city,
                run_id=run_id,
            )


def _insert_organize(con, run_id: int) -> None:
    for fn, ent in [
        ("getOrganizeTypeCodeByEntTypeCircle_entType1100_latest.json", "1100"),
        ("getOrganizeTypeCodeByEntTypeCircle_entType4540_latest.json", "4540"),
    ]:
        j = _load(fn)
        arr = ((j.get("data") or {}).get("busiData")) or []
        for x in arr:
            if not isinstance(x, dict):
                continue
            insert_dict_item(
                con,
                category="organize",
                code=str(x.get("code") or ""),
                name=str(x.get("name") or ""),
                ent_type=ent,
                busi_type="01",
                tags=["组织形式", f"entType:{ent}"],
                tip_ok="组织形式已选，不再触发该字段必填错误。",
                tip_error="组织形式为空会出现字段红框并阻断下一步。",
                recommendation="组织形式必须与主体类型匹配；不要跨 entType 复用。",
                source_api="/icpsp-api/v4/pc/common/configdata/getOrganizeTypeCodeByEntTypeCircle",
                source_file=fn,
                raw_json=x,
                run_id=run_id,
            )


def _insert_industries(con, run_id: int) -> None:
    for fn, ent in [
        ("getAllIndustryTypeCode_entType1100_range1_latest.json", "1100"),
        ("getAllIndustryTypeCode_entType4540_range1_latest.json", "4540"),
    ]:
        j = _load(fn)
        arr = ((j.get("data") or {}).get("busiData")) or []
        for x in arr:
            if not isinstance(x, dict):
                continue
            tags = ["行业"]
            if x.get("kindSign") is True:
                tags.append("行业大类")
            insert_dict_item(
                con,
                category="industry",
                code=str(x.get("code") or ""),
                name=str(x.get("name") or ""),
                parent_code=str(x.get("parent") or "") or None,
                ent_type=ent,
                busi_type="01",
                tags=tags,
                tip_ok="行业选择完成，名称核查可进入行业约束判断。",
                tip_error="行业/经营特点缺失会触发必填错误并阻断。",
                recommendation="存储时分离行业码(industry)与经营特点(indSpec)，查询时优先使用行业码。",
                source_api="/icpsp-api/v4/pc/common/configdata/getAllIndustryTypeCode",
                source_file=fn,
                raw_json=x,
                run_id=run_id,
            )


def _insert_name_need_modes(con, run_id: int) -> None:
    for fn, ent in [
        ("queryNameEntTypeCfgByEntType_1100_latest.json", "1100"),
        ("queryNameEntTypeCfgByEntType_4540_latest.json", "4540"),
    ]:
        j = _load(fn)
        v = ((j.get("data") or {}).get("busiData")) or ""
        modes = [x.strip() for x in str(v).split(",") if x.strip()]
        for m in modes:
            insert_dict_item(
                con,
                category="name_need_mode",
                code=m,
                name=f"mode_{m}",
                ent_type=ent,
                tags=["名称需求模式", "10/20/30"],
                tip_ok="名称需求模式有效，后续逻辑可按模式分支。",
                tip_error="模式缺失或不匹配会导致 UI 阻断/MessageBox。",
                recommendation="默认优先未申请路径，减少旧 nameId 相关干扰。",
                source_api="/icpsp-api/v4/pc/common/synchrdata/queryNameEntTypeCfgByEntType",
                source_file=fn,
                raw_json={"raw": v, "mode": m},
                run_id=run_id,
            )


def _seed_api_specs(con) -> None:
    upsert_api_spec(
        con,
        path="/icpsp-api/v4/pc/common/synchrdata/queryRegcodeAndStreet",
        method="GET",
        purpose="区划树（省市区街道）",
        request_template={"fromPage": "qykbdb"},
        response_keys=["data.busiData[].id", "name", "children"],
        error_patterns=["未登录/会话过期导致 401", "网络失败"],
        recommendation="用于构建 distCode 选择器，不要手填硬编码。",
    )
    upsert_api_spec(
        con,
        path="/icpsp-api/v4/pc/common/synchrdata/queryNameEntType",
        method="GET",
        purpose="主体类型选项",
        request_template={"type": "1 or 2"},
        response_keys=["data.busiData.pagetypes[].code", "name"],
        error_patterns=["返回空数组", "页面上下文未就绪"],
        recommendation="主体类型是后续规则主锚点。",
    )
    upsert_api_spec(
        con,
        path="/icpsp-api/v4/pc/common/configdata/getOrganizeTypeCodeByEntTypeCircle",
        method="GET",
        purpose="组织形式候选",
        request_template={"entType": "1100", "busType": "01"},
        response_keys=["data.busiData[].code", "name"],
        error_patterns=["entType 不匹配导致候选异常"],
        recommendation="组织形式必须和 entType 绑定。",
    )
    upsert_api_spec(
        con,
        path="/icpsp-api/v4/pc/common/configdata/getAllIndustryTypeCode",
        method="GET",
        purpose="行业字典（大类+叶子）",
        request_template={"busiType": "01", "entType": "1100", "range": "1"},
        response_keys=["data.busiData[].code", "name", "parent", "kindSign"],
        error_patterns=["数据量大，前端展示需分页/检索"],
        recommendation="先按 code 入库，UI 再做层级展示。",
    )
    upsert_api_spec(
        con,
        path="/icpsp-api/v4/pc/register/verifidata/bannedLexiconCalibration",
        method="GET",
        purpose="禁限用字词校验",
        request_template={"nameMark": "字号片段"},
        response_keys=["data.busiData.success", "tipStr", "tipKeyWords"],
        error_patterns=["success=false", "tipWay=2"],
        recommendation="先跑该接口，再跑名称库查重。",
    )
    upsert_api_spec(
        con,
        path="/icpsp-api/v4/pc/register/name/component/NameCheckInfo/nameCheckRepeat",
        method="POST",
        purpose="名称库查重与 stop 判定",
        request_template={
            "condition": "1",
            "busiType": "01",
            "entType": "1100",
            "name": "广西XX有限公司",
            "namePre": "广西",
            "nameMark": "XX",
            "distCode": "450000",
            "areaCode": "450000",
            "organize": "有限公司",
            "industry": "7519",
            "indSpec": "科技",
        },
        response_keys=["data.busiData.checkState", "checkResult", "modResult.resultFlag", "langStateCode"],
        error_patterns=["checkState=2", "resultFlag=2", "remark 包含 名称相同/相近"],
        recommendation="输出 stop + top_hit_reason 供业务侧解释。",
    )


def _seed_operation_methods(con) -> None:
    insert_operation_method(
        con,
        step_code="S01",
        step_name="主体类型选择",
        preconditions=["已登录", "进入设立登记入口"],
        action_desc="选择 entType（1100/9100/4540/9600/fzjg）",
        expected_desc="页面可继续，后续组织形式/名称模式联动",
        error_desc="不选择会阻断下一步并触发必填提示",
        recommendation="先定 entType 再执行其他选择项",
        related_apis=["/icpsp-api/v4/pc/common/synchrdata/queryNameEntType"],
    )
    insert_operation_method(
        con,
        step_code="S02",
        step_name="区划选择",
        preconditions=["主体类型已选择"],
        action_desc="选择 distCode/areaCode（省市区）",
        expected_desc="可进入名称检查页并计算名称前缀",
        error_desc="区划为空触发红框与提示",
        recommendation="查询时优先使用目标区县代码",
        related_apis=["/icpsp-api/v4/pc/common/synchrdata/queryRegcodeAndStreet", "/icpsp-api/v4/pc/common/synchrdata/queryNamePrefix"],
    )
    insert_operation_method(
        con,
        step_code="S03",
        step_name="组织形式与行业选择",
        preconditions=["entType 已知", "区划已选"],
        action_desc="选择 organize + industry + indSpec",
        expected_desc="名称核查条件完整，可提交查重",
        error_desc="组织形式或行业为空会阻断",
        recommendation="组织形式按 entType 字典过滤，行业优先存 code",
        related_apis=[
            "/icpsp-api/v4/pc/common/configdata/getOrganizeTypeCodeByEntTypeCircle",
            "/icpsp-api/v4/pc/common/configdata/getAllIndustryTypeCode",
        ],
    )
    insert_operation_method(
        con,
        step_code="S04",
        step_name="名称可用性判定",
        preconditions=["名称参数完整"],
        action_desc="先 bannedLexiconCalibration，再 nameCheckRepeat",
        expected_desc="返回 overall.ok/stop + 原因",
        error_desc="禁限用词或名称库冲突导致 stop",
        recommendation="按原因提供替代建议（换字号/组织形式/行业特征）",
        related_apis=[
            "/icpsp-api/v4/pc/register/verifidata/bannedLexiconCalibration",
            "/icpsp-api/v4/pc/register/name/component/NameCheckInfo/nameCheckRepeat",
        ],
    )


def main() -> None:
    con = connect()
    init_schema(con)
    clear_v2_data(con)
    run_id = begin_run(con, run_tag=f"dict_v2_{time.strftime('%Y%m%d_%H%M%S')}", source="dict_cache + protocol seeding", note="V2 framework bootstrap")
    _insert_ent_types(con, run_id)
    _insert_regions(con, run_id)
    _insert_organize(con, run_id)
    _insert_industries(con, run_id)
    _insert_name_need_modes(con, run_id)
    _seed_api_specs(con)
    _seed_operation_methods(con)
    con.commit()
    end_run(con, run_id)
    st = stats(con)
    payload = {"run_id": run_id, "stats": st}
    OUT_REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved:", OUT_REPORT)
    print(json.dumps(st, ensure_ascii=False))


if __name__ == "__main__":
    main()

