#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""覆盖矩阵缺失状态枚举化 (E-P0-4: "矩阵零空白语义; 枚举写入契约测试")

输入: shared/pool_review_20261010/池子全清单_数据覆盖矩阵_20261010.csv
输出: 同目录 池子全清单_数据覆盖矩阵_20261010_枚举版v1.1.csv + reports JSON
规则(逐列语义, 空白格一律显式化):
  层级/池・代码・名称  空白 -> "na"          (池汇总行无标的字段, 非数据缺口)
  最新日K/最新收盘/K线行数  空白 -> "missing"(标的行应有数据而缺, 待回填)
  年检归属            空白 -> "na"
  数据备注            空白 -> "na"          (无备注=无信息, 非数据状态)
新增列 数据状态 ∈ DataStatus{ok,degraded,missing,na}:
  池汇总行(代码空白) -> na;
  标的行 -> missing(任一数据列缺失) / degraded(备注含 降级|缺|单源) / ok。
幂等可重跑; 原始文件不改动(只读)。
"""
import csv
import json
import os
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from market_fetcher import atomic_io  # noqa: E402

SRC = "/home/z/my-project/shared/pool_review_20261010/池子全清单_数据覆盖矩阵_20261010.csv"
OUT = "/home/z/my-project/shared/pool_review_20261010/池子全清单_数据覆盖矩阵_20261010_枚举版v1.1.csv"
DATA_COLS = ["最新日K", "最新收盘", "K线行数"]
FILL_RULE = {"层级/池": "na", "代码": "na", "名称": "na", "年检归属": "na",
             "数据备注": "na", "最新日K": "missing", "最新收盘": "missing",
             "K线行数": "missing"}
DEGRADED_HINTS = ("降级", "单源", "兜底")


def main() -> int:
    rows = list(csv.reader(open(SRC, encoding="utf-8-sig")))
    hdr, body = rows[0], rows[1:]
    fills = {hdr.index(c): FILL_RULE[c] for c in FILL_RULE if c in hdr}
    out_rows, stats = [], {"na": 0, "ok": 0, "missing": 0, "degraded": 0,
                           "pool_rows": 0, "symbol_rows": 0, "filled_cells": 0}
    for r in body:
        r = r + [""] * (len(hdr) - len(r))
        is_symbol = bool(r[hdr.index("代码")].strip())
        for i, fill in fills.items():
            if not r[i].strip():
                r[i] = fill
                stats["filled_cells"] += 1
        if is_symbol:
            stats["symbol_rows"] += 1
            data_blank = any(not r[hdr.index(c)].strip() or
                             r[hdr.index(c)].strip() == "missing"
                             for c in DATA_COLS)
            note = r[hdr.index("数据备注")]
            if data_blank:
                st = "missing"
            elif any(h in note for h in DEGRADED_HINTS):
                st = "degraded"
            else:
                st = "ok"
        else:
            stats["pool_rows"] += 1
            st = "na"
        stats[st] += 1
        r.append(st)  # 数据状态列
        out_rows.append(r)
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(hdr + ["数据状态"])
        w.writerows(out_rows)
    report = {"src": SRC, "out": OUT, "ts": datetime.now().isoformat(timespec="seconds"),
              "rows": len(body), "cols": len(hdr) + 1, **stats}
    atomic_io.atomic_write_json(report, os.path.join(
        BASE, "reports", "matrix_enum_20261011.json"))
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
