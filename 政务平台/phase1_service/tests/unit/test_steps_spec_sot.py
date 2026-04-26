"""单元测试：STEPS_SPEC 单一事实源不被重复定义/漂移。

防止下次有人：
- 在 adapter 里偷偷再加一份 steps_spec
- 只改 driver 忘改 adapter / 只改 adapter 忘改 driver

这个测试就是安全网。
"""
from __future__ import annotations

import pytest


def test_driver_spec_has_25_steps():
    import phase2_protocol_driver as drv  # type: ignore
    spec = drv.get_steps_spec()
    assert len(spec) == 25


def test_driver_spec_steps_contiguous_1_to_25():
    import phase2_protocol_driver as drv  # type: ignore
    spec = drv.get_steps_spec()
    numbers = [s[0] for s in spec]
    assert numbers == list(range(1, 26))


def test_driver_spec_all_callable():
    import phase2_protocol_driver as drv  # type: ignore
    for i, name, fn, opt in drv.get_steps_spec():
        assert callable(fn), f"step {i} {name} not callable"


def test_optional_set_exactly_13_and_17():
    """step 13 YbbSelect（D0021 optional）和 step 17 MemberPool list（失败不中断）是 optional。"""
    import phase2_protocol_driver as drv  # type: ignore
    optional_nums = {s[0] for s in drv.get_steps_spec() if s[3]}
    assert optional_nums == {13, 17}


def test_adapter_passthrough_identical():
    """adapter 返回的 spec 与 driver 完全一致（SSOT 铁律）。"""
    import phase2_protocol_driver as drv  # type: ignore
    from phase1_service.api.core.phase2_adapter import _load_driver, _get_steps_spec

    driver_spec = drv.get_steps_spec()
    adapter_spec = _get_steps_spec(_load_driver())
    assert adapter_spec == driver_spec


def test_get_steps_spec_returns_copy():
    """get_steps_spec() 返回的应该是拷贝 — 调用方改动不影响原始 STEPS_SPEC。"""
    import phase2_protocol_driver as drv  # type: ignore
    a = drv.get_steps_spec()
    b = drv.get_steps_spec()
    assert a is not b  # 两次调用返回不同 list
    # 原始 STEPS_SPEC 没被污染
    a.append("恶意追加")
    c = drv.get_steps_spec()
    assert len(c) == 25


@pytest.mark.parametrize("i,expected_name_prefix", [
    (1, "name/loadCurrentLocationInfo"),
    (8, "name/submit"),
    (11, "matters/operate"),
    (14, "establish/BasicInfo/loadBusinessDataInfo"),
    (15, "establish/BasicInfo/operationBusinessDataInfo"),
    (25, "establish/PreSubmitSuccess/loadBusinessDataInfo"),
])
def test_step_names_anchor(i, expected_name_prefix):
    """锁定关键步的名称，防止误改。"""
    import phase2_protocol_driver as drv  # type: ignore
    spec = drv.get_steps_spec()
    actual_name = spec[i - 1][1]
    assert actual_name.startswith(expected_name_prefix), \
        f"step {i}: got {actual_name!r}, expected prefix {expected_name_prefix!r}"


# ════════════════════════════════════════════════════════════════════
# 1151 有限责任公司 28 步协议链测试
# ════════════════════════════════════════════════════════════════════


def test_1151_spec_has_28_steps():
    import phase2_protocol_driver as drv  # type: ignore
    spec = drv.get_steps_spec("1151")
    assert len(spec) == 28


def test_1151_spec_steps_contiguous_1_to_28():
    import phase2_protocol_driver as drv  # type: ignore
    spec = drv.get_steps_spec("1151")
    numbers = [s[0] for s in spec]
    assert numbers == list(range(1, 29))


def test_1151_spec_all_callable():
    import phase2_protocol_driver as drv  # type: ignore
    for i, name, fn, opt in drv.get_steps_spec("1151"):
        assert callable(fn), f"step {i} {name} not callable"


def test_1151_optional_set_13_and_17():
    """1151: step 13 YbbSelect 和 step 17 MemberPool list 是 optional。"""
    import phase2_protocol_driver as drv  # type: ignore
    optional_nums = {s[0] for s in drv.get_steps_spec("1151") if s[3]}
    assert optional_nums == {13, 17}


def test_1151_adapter_passthrough():
    """adapter 返回的 1151 spec 与 driver 完全一致。"""
    import phase2_protocol_driver as drv  # type: ignore
    from phase1_service.api.core.phase2_adapter import _load_driver, _get_steps_spec

    driver_spec = drv.get_steps_spec("1151")
    adapter_spec = _get_steps_spec(_load_driver(), ent_type="1151")
    assert adapter_spec == driver_spec


@pytest.mark.parametrize("i,expected_name_prefix", [
    (1, "name/loadCurrentLocationInfo"),
    (15, "establish/BasicInfo/operationBusinessDataInfo"),
    (16, "establish/MemberPost/operationBusinessDataInfo [save,1151"),
    (19, "establish/ComplementInfo/operationBusinessDataInfo [save,1151"),
    (20, "establish/Rules/operationBusinessDataInfo [save,1151"),
    (28, "establish/PreSubmitSuccess/loadBusinessDataInfo"),
])
def test_1151_step_names_anchor(i, expected_name_prefix):
    """锁定 1151 关键步的名称。"""
    import phase2_protocol_driver as drv  # type: ignore
    spec = drv.get_steps_spec("1151")
    step = next(s for s in spec if s[0] == i)
    assert step[1].startswith(expected_name_prefix), \
        f"step {i}: got {step[1]!r}, expected prefix {expected_name_prefix!r}"


def test_1151_shares_phase1_steps_with_4540():
    """Steps 1-15 应该与 4540 完全一致（函数引用相同）。"""
    import phase2_protocol_driver as drv  # type: ignore
    spec_4540 = drv.get_steps_spec()
    spec_1151 = drv.get_steps_spec("1151")
    for s4, s1 in zip(spec_4540[:15], spec_1151[:15]):
        assert s4[0] == s1[0], f"step number mismatch: {s4[0]} vs {s1[0]}"
        assert s4[2] is s1[2], f"step {s4[0]}: function mismatch"
