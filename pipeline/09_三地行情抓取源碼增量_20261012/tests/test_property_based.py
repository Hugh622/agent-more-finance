# -*- coding: utf-8 -*-
"""E-P2-2 测试金字塔批次2 · property-based 不变量测试(确定性种子, 零外部依赖)。
环境无 hypothesis → 采用固定种子随机性质循环(每性质 N 个生成案例), CI 稳定可重放。
种子=20261012; 修改种子视同金样本变更, 须走 supersedes。
"""
import json
import os
import random

import pandas as pd
import pytest

from market_fetcher.atomic_io import atomic_write_json
from market_fetcher.status import DataStatus
from scripts import data_layering as dl

SEED = 20261012
N_CASES = 25


def _rng():
    return random.Random(SEED)


# ---------- P1: atomic_write_json 任意负载往返一致 ----------
def _rand_payload(rng, depth=0):
    kind = rng.randrange(6 if depth < 3 else 3)
    if kind == 0:
        return rng.choice([None, True, False])
    if kind == 1:
        return rng.choice([0, -1, 3.14159, 1e-9, 123456789.5])
    if kind == 2:
        return rng.choice(["", "普通文本", "换行\n引号\"'与{花括号}", "🎉emoji"])
    if kind == 3:
        return []
    if kind == 4:
        return {}
    return [_rand_payload(rng, depth + 1) for _ in range(rng.randint(1, 4))] \
        if rng.random() < 0.5 else \
        {f"k{rng.randrange(1000)}": _rand_payload(rng, depth + 1) for _ in range(rng.randint(1, 4))}


def test_p1_atomic_write_json_roundtrip(tmp_path):
    rng = _rng()
    for i in range(N_CASES):
        payload = {"case": i, "data": _rand_payload(rng)}
        p = tmp_path / f"case_{i}.json"
        atomic_write_json(payload, str(p))
        assert json.loads(p.read_text(encoding="utf-8")) == payload, f"case {i} 往返失真"
    residues = [f for f in os.listdir(tmp_path) if ".tmp" in f]
    assert not residues, f"tmp 残留: {residues}"


# ---------- P2: kline_normalize 不变量 ----------
def _rand_kline(rng, n):
    rows = []
    for i in range(n):
        day = rng.randint(1, 28)
        base = rng.uniform(5, 500)
        rows.append({
            "date": f"2026-09-{day:02d}",
            "open": round(base * rng.uniform(0.98, 1.02), 4),
            "high": round(base * rng.uniform(1.0, 1.06), 4),
            "low": round(base * rng.uniform(0.94, 1.0), 4),
            "close": base if rng.random() > 0.1 else None,   # 10% 缺失
            "volume": rng.randint(0, 10**7),
            "code": "usXXX.OQ", "name": "随机标的",
            "fetched_at": "2026-10-12 00:00:00", "source": "test",
        })
    return pd.DataFrame(rows)


def test_p2_kline_normalize_invariants():
    rng = _rng()
    for i in range(N_CASES):
        src = _rand_kline(rng, rng.randint(3, 60))
        out = dl._transform_kline(src)
        assert (out["close"] > 0).all(), f"case {i} close 非正"
        assert out["date"].is_monotonic_increasing, f"case {i} 未按日期升序"
        assert out["close"].notna().all() and len(out) <= len(src)
        idem = dl._transform_kline(out.copy())
        pd.testing.assert_frame_equal(
            idem.reset_index(drop=True), out.reset_index(drop=True),
            check_dtype=False), f"case {i} 幂等性破坏"


# ---------- P3: wide_series_v1 融化不变量 ----------
def _rand_wide(rng, n_dates, n_series):
    dates = sorted(rng.sample(range(1, 28), min(n_dates, 27)))
    data = {"date": [f"2026-08-{d:02d}" for d in dates]}
    for s in range(n_series):
        data[f"s{s}"] = [round(rng.uniform(-5, 5), 4) if rng.random() > 0.15 else None
                         for _ in dates]
    for meta in ("fetched_at", "source", "grade"):
        data[meta] = ["meta"] * len(dates)
    return pd.DataFrame(data)


def test_p3_melt_wide_invariants():
    rng = _rng()
    for i in range(N_CASES):
        src = _rand_wide(rng, rng.randint(5, 28), rng.randint(2, 6))
        out = dl._transform_wide(src)
        assert not out.duplicated(["series_id", "date"]).any(), f"case {i} 键重复"
        assert out["value"].notna().all(), f"case {i} 含 NaN"
        assert set(out["series_id"]) <= {c for c in src.columns if c not in dl.META_COLS | {"date"}}
        n_valid = sum(src[c].notna().sum() for c in src.columns
                      if c not in dl.META_COLS | {"date"})
        assert len(out) == n_valid, f"case {i} 行数 != 有效单元格数"
        assert out[["date", "series_id"]].apply(tuple, axis=1).is_monotonic_increasing


# ---------- P4: bronze 幂等与变更检测 ----------
def test_p4_bronze_idempotent_and_tamper(tmp_path):
    rng = _rng()
    src, root = tmp_path / "src", tmp_path / "root"
    src.mkdir(); root.mkdir()
    for k in range(3):
        (src / f"f{k}.csv").write_text(
            "date,value\n2026-09-01,%.6f\n2026-09-02,%.6f\n" % (rng.uniform(0, 1), rng.uniform(0, 1)),
            encoding="utf-8")
    r1 = dl.promote_bronze(str(src), str(root), "t")
    assert all(a["state"] == "promoted" for a in r1)
    r2 = dl.promote_bronze(str(src), str(root), "t")
    assert all(a["state"] == "unchanged" for a in r2), "未变源二次晋升应 unchanged"
    (src / "f1.csv").write_text("date,value\n2026-09-01,0.999999\n", encoding="utf-8")
    r3 = dl.promote_bronze(str(src), str(root), "t")
    by = {os.path.basename(a["artifact"]): a["state"] for a in r3}
    assert by["f1.csv"] == "promoted" and by["f0.csv"] == "unchanged"


# ---------- P5: lineage 断链检测(篡改必报红) ----------
def test_p5_lineage_break_detection(tmp_path):
    src, root = tmp_path / "src", tmp_path / "root"
    src.mkdir(); root.mkdir()
    (src / "a.csv").write_text(
        "date,value\n2026-09-01,1.0\n2026-09-02,1.1\n2026-09-03,0.9\n", encoding="utf-8")
    dl.promote_bronze(str(src), str(root), "dom")
    dl.promote_silver(str(src), str(root), "dom")
    dl.promote_gold(str(root), "dom")
    assert dl.verify_lineage(str(root))["ok"] is True
    silver = root / "silver" / "dom" / "a.csv"
    silver.write_text(silver.read_text(encoding="utf-8") + "2026-09-04,999\n", encoding="utf-8")
    rep = dl.verify_lineage(str(root))
    assert rep["ok"] is False and rep["layers"]["silver"]["broken"], "篡改后必须断链报红"
    silver.write_text("date,value\n2026-09-01,1.0\n2026-09-02,1.1\n2026-09-03,0.9\n",
                      encoding="utf-8")
    assert dl.verify_lineage(str(root))["ok"] is True, "还原后应恢复绿灯"


# ---------- P6: 状态枚举零空白(缺失状态枚举化 E-P0-4 语义) ----------
def test_p6_status_enum_totality():
    rng = _rng()
    valid = {s.value for s in DataStatus}
    for _ in range(N_CASES):
        v = rng.choice(["ok", "MISSING", "Degraded", "na", "", "  ", "unknown_state",
                        None, 123, "fail", "thin", "verified", "skipped", "pending"])
        got = DataStatus.try_coerce(v)
        assert got is None or got.value in valid
        if isinstance(v, str) and v.strip().lower() in valid:
            assert got is not None and got.value == v.strip().lower()
    # 空白/未知绝不幻觉成 ok
    assert DataStatus.try_coerce("") is None
    assert DataStatus.try_coerce(None) is None
    assert DataStatus.try_coerce("   ") is None
    assert DataStatus.try_coerce("ok") == DataStatus.OK
