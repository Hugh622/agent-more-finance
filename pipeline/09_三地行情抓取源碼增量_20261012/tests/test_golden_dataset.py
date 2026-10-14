# -*- coding: utf-8 -*-
"""P2-2 测试金字塔 · 批次1: 金准数据集测试 (golden dataset)
=========================================================
定位: 金字塔中层的"金准"级 —— 钉死小样本真实数据 + 期望输出指纹,
防止引擎改动后语义漂移而单元测试仍绿（单元测真 / 金准测稳）。
金准样本: tests/golden/*.csv + GOLDEN_MANIFEST.json (sha256 钉死)。
"""
import hashlib
import importlib.util
import json
import os

import pandas as pd
import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(BASE, "tests", "golden")
MANIFEST = os.path.join(GOLDEN, "GOLDEN_MANIFEST.json")


def _engine():
    """以模块路径加载契约引擎(与 tests/test_contracts.py 同源, 单一事实)。"""
    spec = importlib.util.spec_from_file_location(
        "test_contracts_engine", os.path.join(BASE, "tests", "test_contracts.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _golden_entries():
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)["entries"]


# ── 1. 金准样本自身完整性（样本被手改即红）────────────────────
@pytest.mark.parametrize("e", _golden_entries(), ids=lambda e: e["file"])
def test_golden_sample_unmodified(e):
    p = os.path.join(GOLDEN, e["file"])
    assert os.path.isfile(p), f"金准样本缺失: {e['file']}"
    data = open(p, "rb").read()
    assert hashlib.sha256(data).hexdigest() == e["sha256"], \
        f"金准样本指纹漂移(被改动?): {e['file']}"
    rows = len([l for l in data.decode("utf-8-sig").splitlines() if l.strip()]) - 1
    assert rows == e["rows"]


# ── 2. 契约引擎对金准样本必须零违规（引擎回归锚）──────────────
def test_contract_engine_zero_violation_on_golden():
    eng = _engine()
    fed = os.path.join(GOLDEN, "fedfunds_golden.csv")
    cpath = os.path.join(BASE, "contracts", "contract_fred_rates.json")
    errs = eng._check_file(eng._load(cpath), fed)
    assert errs == [], f"契约引擎在金准样本上出现违规: {errs[:5]}"


# ── 3. 金准样本内容不变性（同内容两次读取逐值相等）────────────
def test_golden_dataframe_stable():
    p = os.path.join(GOLDEN, "fedfunds_golden.csv")
    a = pd.read_csv(p, encoding="utf-8-sig")
    b = pd.read_csv(p, encoding="utf-8-sig")
    pd.testing.assert_frame_equal(a, b)
    assert list(a.columns)[:3] == ["date", "value", "series_id"]


# ── 4. manifest v2 对金准 fixture 的数据指纹稳定（引擎级金准）──
def test_manifest_v2_data_fingerprint_golden(tmp_path):
    from market_fetcher import manifest_v2
    # 最小 fixture: data_root 内两个小 csv, manifest 引用之
    dr = tmp_path / "data"
    dr.mkdir()
    (dr / "a.csv").write_text("date,value\n2026-10-09,1.5\n", encoding="utf-8")
    (dr / "b.csv").write_text("date,value\n2026-10-09,2.5\n", encoding="utf-8")
    manifest = {"type": "kline_batch", "files": [
        {"path": "a.csv", "status": "ok"},
        {"path": "b.csv", "status": "ok"}]}
    built = manifest_v2.build_v2(manifest, str(dr), base=str(tmp_path))
    recs = {e["path"]: e["sha256"] for e in built["data_files"]}
    expect = {
        "a.csv": hashlib.sha256(b"date,value\n2026-10-09,1.5\n").hexdigest(),
        "b.csv": hashlib.sha256(b"date,value\n2026-10-09,2.5\n").hexdigest()}
    assert recs == expect, "manifest v2 数据指纹与金准期望不符"
    # 篡改一个字节 → 指纹必须变
    (dr / "b.csv").write_text("date,value\n2026-10-09,2.6\n", encoding="utf-8")
    built2 = manifest_v2.build_v2(manifest, str(dr), base=str(tmp_path))
    recs2 = {e["path"]: e["sha256"] for e in built2["data_files"]}
    assert recs2["b.csv"] != recs["b.csv"] and recs2["a.csv"] == recs["a.csv"]
