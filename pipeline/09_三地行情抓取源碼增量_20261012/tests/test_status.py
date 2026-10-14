# -*- coding: utf-8 -*-
"""状态枚举契约测试 (E-P0-4: 缺失状态枚举化, 读侧安全解析)。"""
import pytest

from market_fetcher.status import DataStatus, QualityStatus, batch_quality


def test_datastatus_members():
    assert {s.value for s in DataStatus} == {
        "ok", "thin", "fail", "missing", "degraded",
        "verified", "insufficient", "skipped", "pending", "na"}


def test_datastatus_is_str_enum():
    assert DataStatus.OK == "ok"          # str 枚举, 值即落盘字符串
    assert DataStatus.MISSING.value == "missing"
    assert isinstance(DataStatus.OK, str)


def test_try_coerce_accepts_case_and_space():
    assert DataStatus.try_coerce("OK") is DataStatus.OK
    assert DataStatus.try_coerce("  degraded ") is DataStatus.DEGRADED
    assert DataStatus.try_coerce(DataStatus.FAIL) is DataStatus.FAIL


def test_try_coerce_unknown_returns_none():
    assert DataStatus.try_coerce("broken!!") is None
    assert DataStatus.try_coerce("") is None
    assert DataStatus.try_coerce(None) is None


def test_coerce_roundtrip_all_members():
    for s in DataStatus:
        assert DataStatus.try_coerce(s.value) is s


def test_qualitystatus_members_and_batch_quality():
    assert QualityStatus.GOOD == "good"
    assert QualityStatus.WARN == "warn"
    assert QualityStatus.BAD == "bad"
    assert batch_quality(10, 0, 0, 10) is QualityStatus.GOOD
    assert batch_quality(9, 1, 0, 10) is QualityStatus.WARN
    assert batch_quality(9, 0, 1, 10) is QualityStatus.BAD
    assert batch_quality(0, 0, 0, 0) is QualityStatus.BAD


def test_matrix_status_subset_in_enum():
    """覆盖矩阵枚举版允许值必须是 DataStatus 子集(E-P0-4 验收)。"""
    allowed = {"ok", "degraded", "missing", "na"}
    assert allowed <= {s.value for s in DataStatus}
