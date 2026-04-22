"""导出 Phase1 API 的 OpenAI function calling schema。

用法：
  python -m phase1_service.api.llm_function_schema > tools.json

LLM 拿到此 schema 后即可自主：
  1) 查字典选参数  2) 预检名字  3) 注册拿 busiId  4) 检查 auth 状态
"""
from __future__ import annotations

import json


PHASE1_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "phase1_precheck_name",
            "description": "预检企业字号是否含禁限用词。0ms 返回，不消耗服务端配额。应在 register 前调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name_mark": {
                        "type": "string",
                        "description": "企业字号（仅核心部分，如'李陈梦'，不含行政区划/行业/组织形式）"
                    },
                    "remote": {
                        "type": "boolean",
                        "description": "是否额外调远端 bannedLexiconCalibration 实网校验",
                        "default": False
                    }
                },
                "required": ["name_mark"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "phase1_register",
            "description": "执行 7 步名称检查协议链，拿到 busiId（名称登记 Step1 完成标志）。需约 5-10 秒。失败返回结构化错误码和建议。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name_mark": {"type": "string", "description": "字号，如 李陈梦"},
                    "phase1_name_pre": {"type": "string", "description": "名称前缀，如 广西容县"},
                    "phase1_industry_code": {"type": "string", "description": "行业代码，如 6513（从 dict/industries 获取）"},
                    "phase1_industry_name": {"type": "string", "description": "行业名称，如 应用软件开发"},
                    "phase1_industry_special": {"type": "string", "description": "行业特征，如 软件开发"},
                    "phase1_organize": {"type": "string", "description": "组织形式，如 中心（个人独资）（从 dict/organizes 获取）"},
                    "phase1_dist_codes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "区划代码三级数组，如 ['450000','450900','450921']（从 dict/regions 获取）"
                    },
                    "entType_default": {"type": "string", "description": "企业类型，如 4540=个独 1100=有限公司（从 dict/ent-types 获取）"},
                    "authorization": {"type": "string", "description": "可选：32-hex ICPSP 认证令牌"}
                },
                "required": ["name_mark", "phase1_industry_code", "phase1_industry_name",
                             "phase1_industry_special", "phase1_organize", "phase1_dist_codes"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "phase1_dict_ent_types",
            "description": "获取所有可用的企业类型（entType）。LLM 根据客户描述选对应代码。",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "phase1_dict_industries",
            "description": "获取指定企业类型的行业码列表。LLM 根据客户经营内容选行业。",
            "parameters": {
                "type": "object",
                "properties": {
                    "entType": {"type": "string", "description": "企业类型代码，如 4540"}
                },
                "required": ["entType"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "phase1_dict_organizes",
            "description": "获取指定企业类型的组织形式列表（厂/中心/商行/工作室...）",
            "parameters": {
                "type": "object",
                "properties": {
                    "entType": {"type": "string", "description": "企业类型代码"}
                },
                "required": ["entType"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "phase1_dict_regions",
            "description": "获取行政区划树（省/市/区/街道），用于构建 dist_codes。",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "phase1_scope",
            "description": "按关键词搜索经营范围条目（含行业码、经营描述、前置/后置审批标记）",
            "parameters": {
                "type": "object",
                "properties": {
                    "entType": {"type": "string"},
                    "keyword": {"type": "string", "description": "行业关键词，如 食品/软件开发"}
                },
                "required": ["entType", "keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "phase1_auth_status",
            "description": "检查当前 Authorization 令牌是否有效。probe=true 实网校验。",
            "parameters": {
                "type": "object",
                "properties": {
                    "probe": {"type": "boolean", "default": False}
                }
            }
        }
    },
]


def export() -> str:
    return json.dumps(PHASE1_TOOLS, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print(export())
