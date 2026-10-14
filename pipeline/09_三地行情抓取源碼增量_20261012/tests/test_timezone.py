# -*- coding: utf-8 -*-
"""E-P2 批次2: 时区纪律单测(UTC 存储约定 / DST 不硬编码 / HKT 固定偏移)
=================================================================
约定(全库一致): 管道与分层产物时间戳一律归一为 UTC ISO8601(+00:00);
naive 输入按 UTC 解释(应用层约定, 代理层无法 SET SESSION 的既定补位);
DST 转换必须走 zoneinfo, 禁止任何硬编码偏移——本测试用纽约冬/夏令时
双锚点防回归。
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from scripts.data_layering import _to_utc_iso


def test_naive_input_interpreted_as_utc():
    s = pd.Series(["2026-09-12 17:18:29"])
    out = _to_utc_iso(s)
    assert out.iloc[0] == "2026-09-12T17:18:29+00:00"


def test_aware_input_converted_to_utc():
    s = pd.Series(["2026-09-12 17:18:29+08:00"])  # HKT 傍晚
    assert _to_utc_iso(s).iloc[0] == "2026-09-12T09:18:29+00:00"


def test_bad_timestamp_becomes_null_not_crash():
    s = pd.Series(["not-a-date", "2026-09-12 17:18:29"])
    out = _to_utc_iso(s)
    assert pd.isna(out.iloc[0])
    assert out.iloc[1] == "2026-09-12T17:18:29+00:00"


def test_dst_boundary_no_hardcoded_offset():
    """纽约夏令时切换双锚: 2026-03-08 进入 EDT(UTC-4), 2026-12-01 回 EST(UTC-5)。
    若实现硬编码 -5, 夏令时样本将错 1 小时。"""
    ny = ZoneInfo("America/New_York")
    s = pd.Series([datetime(2026, 3, 9, 12, 0, tzinfo=ny),   # DST 内(周一切换后)
                   datetime(2026, 12, 1, 12, 0, tzinfo=ny)])  # 标准时
    out = _to_utc_iso(s)
    assert out.iloc[0] == "2026-03-09T16:00:00+00:00"  # 12:00 EDT = 16:00 UTC
    assert out.iloc[1] == "2026-12-01T17:00:00+00:00"  # 12:00 EST = 17:00 UTC


def test_hkt_fixed_offset_no_dst():
    """香港无夏令时: 全年固定 +8。冬夏两样本同验。"""
    hk = ZoneInfo("Asia/Hong_Kong")
    s = pd.Series([datetime(2026, 1, 15, 16, 40, tzinfo=hk),   # 冬: ah_eod 收盘锚
                   datetime(2026, 7, 15, 16, 40, tzinfo=hk)])  # 夏: 同锚
    out = _to_utc_iso(s)
    assert out.iloc[0] == "2026-01-15T08:40:00+00:00"
    assert out.iloc[1] == "2026-07-15T08:40:00+00:00"


def test_series_output_all_utc_aware():
    s = pd.Series(["2026-01-01 00:00:00", "2026-06-30 23:59:59",
                   "2026-10-10 13:27:05"])
    out = _to_utc_iso(s)
    assert out.str.endswith("+00:00").all()
