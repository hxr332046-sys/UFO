"""导出政务平台协议化 API 的 OpenAI function calling schema（LLM tools）。

用法：
  python -m phase1_service.api.llm_function_schema > tools.json

LLM 拿到此 schema 后即可自主完成：
  - 登录/Token 管理（token/refresh/ensure + QR 扫码）
  - Phase 1 核名（precheck + register + supplement）
  - Phase 2 设立（register 25 步 + session 自愈 + 进度查询 + 断点续跑）
  - 办件管理（list / detail）
  - 字典查询（企业类型/行业/组织/区划/经营范围实时）
  - 系统配置（sysParam 快照/刷新）
  - 调试辅助（mitm 样本查询）

默认按需分组，LLM 可以按场景子集加载（LLM_TOOLS_BY_GROUP）。
"""
from __future__ import annotations

import json

# ============================================================
# 认证（6）
# ============================================================
_AUTH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "auth_status",
            "description": "检查当前 Authorization 令牌是否有效。probe=true 会实打一次上游接口验证。",
            "parameters": {
                "type": "object",
                "properties": {
                    "probe": {"type": "boolean", "default": False},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "auth_keepalive",
            "description": "执行一次 ping 保活（维持 token 活跃）。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "auth_token_refresh",
            "description": "静默续期 Authorization（~2秒，不扫码）。前提：之前扫码登录过且 SESSIONFORTYRZ cookie 未过期。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "auth_token_ensure",
            "description": "智能获取 token：现有有效 → existing；否则 refresh；都不行 → 返回 qr_needed 提示。推荐作为首选入口。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "auth_qr_start",
            "description": "生成扫码登录二维码，返回 sid + base64 图片。前端展示图，用户扫码后轮询 auth_qr_status。",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_type": {"type": "integer", "description": "1=个人（默认），2=法人", "default": 1, "enum": [1, 2]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "auth_qr_status",
            "description": "轮询扫码状态。success=True 时返回 Authorization；pending=True 表示还没扫；scanned 表示已扫码。",
            "parameters": {
                "type": "object",
                "properties": {
                    "sid": {"type": "string", "description": "auth_qr_start 返回的 sid"},
                },
                "required": ["sid"],
            },
        },
    },
]

# ============================================================
# Phase 1 名称登记（3）
# ============================================================
_PHASE1_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "phase1_precheck_name",
            "description": "预检企业字号是否含禁限用词（0ms 本地查，不消耗服务端配额）。应在 register 前调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name_mark": {"type": "string", "description": "企业字号（仅核心部分，如 '李陈梦'）"},
                    "remote": {"type": "boolean", "description": "是否额外调远端 bannedLexiconCalibration 实网校验", "default": False},
                },
                "required": ["name_mark"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "phase1_register",
            "description": "执行 7 步名称检查协议链，成功返回 busiId（Phase 1 Step 1）。约 5-10 秒。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name_mark": {"type": "string"},
                    "phase1_name_pre": {"type": "string", "description": "如 广西容县"},
                    "phase1_industry_code": {"type": "string", "description": "如 6513"},
                    "phase1_industry_name": {"type": "string", "description": "如 应用软件开发"},
                    "phase1_industry_special": {"type": "string", "description": "如 软件开发"},
                    "phase1_organize": {"type": "string", "description": "如 中心（个人独资）"},
                    "phase1_dist_codes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "区划代码三级数组，如 ['450000','450900','450921']",
                    },
                    "entType_default": {"type": "string", "description": "如 4540 / 1100"},
                    "authorization": {"type": "string", "description": "可选：32-hex ICPSP token"},
                },
                "required": ["name_mark", "phase1_industry_code", "phase1_industry_name",
                             "phase1_industry_special", "phase1_organize", "phase1_dist_codes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "phase1_supplement",
            "description": "Phase 1 Step 2+3：信息补充（股东/投资人）+ 名称正式提交。输入已通过 register 获取的 busi_id。",
            "parameters": {
                "type": "object",
                "properties": {
                    "busi_id": {"type": "string"},
                    "case": {"type": "object", "description": "case 对象，含投资人信息、认缴金额等"},
                    "authorization": {"type": "string"},
                },
                "required": ["busi_id", "case"],
            },
        },
    },
]

# ============================================================
# Phase 2 设立登记（4）
# ============================================================
_PHASE2_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "phase2_register",
            "description": (
                "执行 Phase 2 设立登记协议链（25 步），可用 stop_after/start_from 控制范围。"
                "完整链路到云提交停点 PreSubmitSuccess。含幂等缓存 + session 自愈。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "case": {"type": "object", "description": "case 对象，参见 docs/case_有为风.json"},
                    "busi_id": {"type": "string", "description": "可选：已知 busiId 断点续跑"},
                    "name_id": {"type": "string", "description": "可选：对应 nameId"},
                    "authorization": {"type": "string"},
                    "start_from": {"type": "integer", "minimum": 1, "maximum": 25, "default": 1},
                    "stop_after": {"type": "integer", "minimum": 1, "maximum": 25, "default": 14},
                    "auto_phase1": {"type": "boolean", "description": "缺 busi_id 时是否自动跑 Phase 1", "default": False},
                },
                "required": ["case"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "phase2_session_recover",
            "description": "从 CDP 浏览器（9225 端口）同步 Authorization + cookies 到 Python 会话（扫码登录后用）。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "phase2_cache_stats",
            "description": "Phase 2 幂等缓存统计（便于观察命中率）。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "phase2_progress",
            "description": "查询办件当前 establish 位置（currCompUrl + status + busiCompComb）。断点续跑必备。",
            "parameters": {
                "type": "object",
                "properties": {
                    "busi_id": {"type": "string"},
                    "name_id": {"type": "string"},
                    "ent_type": {"type": "string", "default": "4540"},
                    "busi_type": {"type": "string", "default": "02_4"},
                },
                "required": ["busi_id", "name_id"],
            },
        },
    },
]

# ============================================================
# 办件管理（2）
# ============================================================
_MATTERS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "matters_list",
            "description": "列出当前用户的办件（我的办件）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {"type": "string", "default": "", "description": "按关键字过滤（企业名/法人等）"},
                    "page": {"type": "integer", "default": 1, "minimum": 1},
                    "size": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
                    "state": {"type": "string", "default": "", "description": "按 matterStateCode 过滤"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "matters_detail",
            "description": "单个办件详情（基本信息 + establish 当前位置）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "busi_id": {"type": "string"},
                    "name_id": {"type": "string", "description": "可选，不传会从列表推导"},
                },
                "required": ["busi_id"],
            },
        },
    },
]

# ============================================================
# 字典（6，本地 5 + 实时 1）
# ============================================================
_DICT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "phase1_dict_ent_types",
            "description": "获取企业类型（entType）字典。",
            "parameters": {"type": "object", "properties": {"level": {"type": "integer", "default": 1}}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "phase1_dict_industries",
            "description": "获取指定企业类型的行业字典。",
            "parameters": {
                "type": "object",
                "properties": {
                    "entType": {"type": "string"},
                    "busiType": {"type": "string", "default": "01"},
                },
                "required": ["entType"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "phase1_dict_organizes",
            "description": "获取指定企业类型的组织形式。",
            "parameters": {
                "type": "object",
                "properties": {
                    "entType": {"type": "string"},
                    "busiType": {"type": "string", "default": "01"},
                },
                "required": ["entType"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "phase1_dict_regions",
            "description": "获取行政区划树。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "phase1_dict_name_prefixes",
            "description": "获取字号前缀（区划 + 企业类型）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "distCode": {"type": "string"},
                    "entType": {"type": "string"},
                },
                "required": ["distCode", "entType"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "phase1_scope",
            "description": "经营范围查询（本地 Tier D 普查数据，快）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "entType": {"type": "string"},
                    "busiType": {"type": "string", "default": "01"},
                    "keyword": {"type": "string"},
                },
                "required": ["entType", "keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "phase1_scope_search",
            "description": "经营范围实时搜索（直连平台 busiterm/getThirdleveLBusitermList，保证最新字典）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "industry_code": {"type": "string", "description": "可选：如 6513"},
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 50},
                },
                "required": ["keyword"],
            },
        },
    },
]

# ============================================================
# 系统参数（3）
# ============================================================
_SYSTEM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "sysparam_snapshot",
            "description": "读本地 sysParam 快照（含 aesKey / RSA 公钥等 958 条系统参数）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {"type": "string", "description": "逗号分隔的 key 过滤"},
                    "mask_keys": {"type": "boolean", "default": True, "description": "对长字段折叠显示"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sysparam_key",
            "description": "按 key 查单条 sysParam（不 mask）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "如 aesKey / numberEncryptPublicKey"},
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sysparam_refresh",
            "description": "调上游 getAllSysParam 实时刷新本地快照（若 aesKey 等密钥变化会通过 important_keys_changed 返回）。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

# ============================================================
# 调试辅助（3）
# ============================================================
_DEBUG_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "debug_mitm_samples",
            "description": "查 mitm 记录中匹配的样本（按 URL pattern / opeType / code 过滤）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "api_pattern": {"type": "string", "description": "URL 关键词，如 BasicInfo/operationBusinessDataInfo"},
                    "opeType": {"type": "string", "description": "可选：save / special"},
                    "code": {"type": "string", "description": "可选：00000 / A0002"},
                    "limit": {"type": "integer", "default": 5, "minimum": 1, "maximum": 50},
                },
                "required": ["api_pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "debug_mitm_latest",
            "description": "最新一条匹配的 mitm 样本（含完整 req_body + resp_body）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "api_pattern": {"type": "string"},
                    "only_success": {"type": "boolean", "default": True},
                },
                "required": ["api_pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "debug_mitm_stats",
            "description": "mitm 抓包统计（总记录数/方法分布/top codes/top APIs）。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

# ============================================================
# 汇总
# ============================================================
LLM_TOOLS_BY_GROUP = {
    "auth": _AUTH_TOOLS,          # 6
    "phase1": _PHASE1_TOOLS,       # 3
    "phase2": _PHASE2_TOOLS,       # 4
    "matters": _MATTERS_TOOLS,     # 2
    "dict": _DICT_TOOLS,           # 7
    "system": _SYSTEM_TOOLS,       # 3
    "debug": _DEBUG_TOOLS,         # 3
}

# 全部 28 个工具（auth 6 + phase1 3 + phase2 4 + matters 2 + dict 7 + system 3 + debug 3）
PHASE1_TOOLS = [tool for group in LLM_TOOLS_BY_GROUP.values() for tool in group]

# 按"最小可用集"推荐（LLM 最常用的 8 个）
CORE_TOOLS = (
    _AUTH_TOOLS[3:4]           # auth_token_ensure
    + _PHASE1_TOOLS[:2]          # precheck + register
    + _PHASE1_TOOLS[2:]          # supplement
    + _PHASE2_TOOLS[:1]          # phase2_register
    + _PHASE2_TOOLS[3:]          # phase2_progress
    + _MATTERS_TOOLS             # list + detail
)


def export(group: str = "all") -> str:
    """导出 JSON。group 可选：all / auth / phase1 / phase2 / matters / dict / system / debug / core"""
    if group == "all":
        data = PHASE1_TOOLS
    elif group == "core":
        data = CORE_TOOLS
    elif group in LLM_TOOLS_BY_GROUP:
        data = LLM_TOOLS_BY_GROUP[group]
    else:
        raise ValueError(f"unknown group: {group}")
    return json.dumps(data, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import sys as _sys
    g = _sys.argv[1] if len(_sys.argv) > 1 else "all"
    print(export(g))
