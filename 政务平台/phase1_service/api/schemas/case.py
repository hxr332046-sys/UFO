"""请求体 schema。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class Phase1Case(BaseModel):
    """第一阶段 case：最小集合。"""

    # 业务核心
    name_mark: str = Field(..., description="字号，如 李陈梦", min_length=1, max_length=20)
    phase1_name_pre: str = Field(default="广西容县", description="名称前缀，如 广西容县")
    phase1_industry_code: str = Field(..., description="行业代码，如 6513")
    phase1_industry_name: str = Field(..., description="行业名称，如 应用软件开发")
    phase1_industry_special: str = Field(..., description="行业特征，如 软件开发")
    phase1_organize: str = Field(..., description="组织形式，如 中心（个人独资）")
    phase1_dist_codes: List[str] = Field(..., description="区划 code 三级数组，如 [450000,450900,450921]")
    phase1_check_name: Optional[str] = Field(default=None, description="完整企业名（可选，留空则按规则拼）")

    # 企业类型
    entType_default: str = Field(default="4540", description="企业类型代码，如 4540 = 个独")
    busiType_default: str = Field(default="02_4", description="业务类型，如 02_4")

    # 其他
    phase1_main_business_desc: Optional[str] = Field(default=None, description="主要经营描述")


class RegisterRequest(BaseModel):
    case: Phase1Case
    authorization: Optional[str] = Field(
        default=None,
        description="ICPSP 32-hex Authorization；留空则服务器从最新抓包里自动拾取（仅调试用）",
    )


class DictionaryQuery(BaseModel):
    entType: Optional[str] = None
    busiType: Optional[str] = Field(default="01")
    distCode: Optional[str] = None


class BusinessScopeQuery(BaseModel):
    entType: str
    busiType: str = "01"
    keyword: str = Field(..., description="行业特征关键词，如 '软件开发' / '食品'")
