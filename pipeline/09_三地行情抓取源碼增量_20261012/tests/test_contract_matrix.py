# -*- coding: utf-8 -*-
"""覆盖矩阵枚举版契约测试 (E-P0-4 验收: 矩阵零空白语义; 值全在枚举域内)。"""
import csv
import os

from market_fetcher.status import DataStatus

MATRIX = ("/home/z/my-project/shared/pool_review_20261010/"
          "池子全清单_数据覆盖矩阵_20261010_枚举版v1.1.csv")
ALLOWED = {"ok", "degraded", "missing", "na"}


def _rows():
    with open(MATRIX, encoding="utf-8-sig") as f:
        return list(csv.reader(f))


def test_matrix_exists():
    assert os.path.isfile(MATRIX)


def test_matrix_zero_blank_cells():
    rows = _rows()
    blanks = [(i, j) for i, r in enumerate(rows[1:], 2)
              for j, c in enumerate(r) if not str(c).strip()]
    assert not blanks, f"仍有空白格(行,列): {blanks[:5]}"


def test_matrix_status_column_in_enum():
    rows = _rows()
    si = rows[0].index("数据状态")
    for r in rows[1:]:
        assert r[si] in ALLOWED, f"非法状态值: {r[si]}"


def test_allowed_is_datasource_enum_subset():
    assert ALLOWED <= {s.value for s in DataStatus}


def test_symbol_rows_have_date_semantics():
    rows = _rows()
    di, si = rows[0].index("最新日K"), rows[0].index("数据状态")
    for r in rows[1:]:
        if r[si] in ("ok", "degraded"):
            assert r[di].count("-") == 2, f"数据行日期异常: {r[di]}"
