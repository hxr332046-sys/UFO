"""pytest 通用 fixtures。

所有测试文件自动 import 这个 conftest。

- 把项目根 + system/ 加入 sys.path（让 test 能 import phase2_protocol_driver 等）
- 提供通用 fixtures：case_youweifeng, empty_case
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "system"))


@pytest.fixture(scope="session")
def project_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def case_youweifeng(project_root: Path) -> dict:
    """加载 docs/case_有为风.json 作为标准 4540 个独 case。"""
    case_path = project_root / "docs" / "case_有为风.json"
    return json.loads(case_path.read_text(encoding="utf-8"))


@pytest.fixture
def empty_case() -> dict:
    """最小空 case，用于测试 fallback 默认值。"""
    return {}


@pytest.fixture
def minimal_case() -> dict:
    """只含必需字段的最小 case。"""
    return {
        "entType_default": "4540",
        "name_mark": "测试",
        "phase1_industry_code": "6513",
        "phase1_industry_name": "应用软件开发",
        "phase1_industry_special": "软件开发",
        "phase1_organize": "中心（个人独资）",
        "phase1_dist_codes": ["450000", "450900", "450921"],
        "phase1_check_name": "测试（广西容县）软件开发中心（个人独资）",
        "company_name_phase1_normalized": "测试（广西容县）软件开发中心（个人独资）",
        "person": {
            "name": "张三",
            "mobile": "13800138000",
            "id_no": "110101199001010011",
        },
    }
