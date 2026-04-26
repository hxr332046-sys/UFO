"""单元测试：phase2_enums 的业务语言→code 映射。

覆盖所有 helper 的：
- 本地化中文 → code
- code 本身 → code（透传）
- 未知值 → 默认值（不抛异常）
"""
from __future__ import annotations

import pytest

from phase2_enums import (  # type: ignore
    ent_type,
    cer_type,
    sex_code,
    house_to_bus,
    use_mode,
    politics_visage,
    is_organ,
    inv_type,
    inv_form_type,
    should_invest_way,
    business_mode_gt,
    norm_add_flag,
    yes_no_01,
    material_code_for_property,
)


class TestEntType:
    def test_chinese(self):
        assert ent_type("个人独资") == "4540"
        assert ent_type("有限责任公司") == "1100"

    def test_passthrough_code(self):
        assert ent_type("4540") == "4540"
        assert ent_type("1151") == "1151"

    def test_unknown_fallback(self):
        assert ent_type("不存在的类型") == "4540"  # default
        assert ent_type(None) == "4540"
        assert ent_type("") == "4540"

    def test_custom_default(self):
        assert ent_type("不存在", default="1151") == "1151"


class TestCerType:
    def test_id_card(self):
        assert cer_type("身份证") == "10"
        assert cer_type("居民身份证") == "10"
        assert cer_type("10") == "10"

    def test_passport(self):
        assert cer_type("护照") == "14"

    def test_fallback(self):
        assert cer_type(None) == "10"


class TestSexCode:
    def test_male(self):
        assert sex_code("男") == "1"
        assert sex_code("1") == "1"

    def test_female(self):
        assert sex_code("女") == "2"
        assert sex_code("2") == "2"

    def test_fallback(self):
        assert sex_code(None) == "1"


class TestHouseToBus:
    def test_yes(self):
        assert house_to_bus("是") == "1"

    def test_no(self):
        assert house_to_bus("否") == "0"

    def test_default_no(self):
        assert house_to_bus(None) == "0"


class TestUseMode:
    @pytest.mark.parametrize("label,code", [
        ("自有产权", "01"),
        ("租赁", "02"),
        ("借用", "03"),
        ("其他", "04"),
    ])
    def test_all(self, label, code):
        assert use_mode(label) == code


class TestPoliticsVisage:
    def test_qz(self):
        assert politics_visage("群众") == "13"

    def test_dy(self):
        assert politics_visage("党员") == "01"
        assert politics_visage("中共党员") == "01"

    def test_fallback_qz(self):
        assert politics_visage(None) == "13"


class TestIsOrgan:
    def test_no(self):
        assert is_organ("否") == "02"
        assert is_organ("否(自然人代理)") == "02"
        assert is_organ(None) == "02"
        assert is_organ("") == "02"

    def test_yes(self):
        assert is_organ("是") == "01"
        assert is_organ("01") == "01"


class TestInvType:
    def test_natural(self):
        assert inv_type("自然人") == "1"

    def test_corp(self):
        assert inv_type("企业法人") == "2"


class TestMaterialCodeForProperty:
    def test_self_owned(self):
        assert material_code_for_property("01") == "175"

    def test_rental(self):
        assert material_code_for_property("02") == "176"

    def test_borrowed(self):
        assert material_code_for_property("03") == "177"

    def test_default(self):
        assert material_code_for_property("99") == "176"  # fallback 租赁


class TestYesNo01:
    def test_yes(self):
        assert yes_no_01("是") == "1"

    def test_no(self):
        assert yes_no_01("否") == "0"


class TestBusinessModeGT:
    def test_general(self):
        assert business_mode_gt("一般") == "10"
        assert business_mode_gt(None) == "10"


class TestNormAddFlag:
    def test_standard(self):
        assert norm_add_flag("标准") == "01"

    def test_nonstandard(self):
        assert norm_add_flag("非标") == "02"
