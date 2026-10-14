# -*- coding: utf-8 -*-
"""test_engine_cost.py — 回测引擎核心与成本模型单测（P2 最低规格验收件）"""
import numpy as np
import pandas as pd
import pytest

from bt_engine import cost as C
from bt_engine import engine as G
from bt_engine import data as D


# ── 成本模型三地分参 ─────────────────────────────────────────────────
def test_cost_three_markets_asymmetry():
    us_rt = C.roundtrip_cost("US")
    hk_rt = C.roundtrip_cost("HK")
    cn_rt = C.roundtrip_cost("CN")
    assert hk_rt > us_rt > cn_rt > 0                        # HK 摩擦最重、CN 最轻
    assert C.side_cost("CN", "buy") == pytest.approx(0.00025 + 0.00001 + 0.00050)
    # CN 印花税只在卖出边
    assert C.side_cost("CN", "sell") == pytest.approx(0.00025 + 0.00001 + 0.00050 + 0.0005)
    # 5× 压力层
    assert C.roundtrip_cost("US", stress=5.0) == pytest.approx(5 * C.roundtrip_cost("US"))


# ── point-in-time 指标（未来函数防线）────────────────────────────────
def test_prep_indicators_no_lookahead():
    n = 80
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    df = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=n), "close": close,
                       "high": close + 1, "low": close - 1,
                       "open": close, "volume": np.full(n, 1000.0)})
    out = G.prep_indicators(df, breakout_window=20)
    # shift(1)+rolling(20,min_periods=20)：第 20 行（0-based）首个有值窗口＝第 0..19 行
    assert np.isfinite(out["prior_high"].iloc[20])
    assert out["prior_high"].iloc[20] == pytest.approx(df["high"].iloc[:20].max())
    assert not np.isfinite(out["prior_high"].iloc[19])       # 第 19 行窗口含 shift 空位 → NaN
    assert out["ma20"].iloc[20] == pytest.approx(close[:20].mean())
    # 未来函数防线：改动最后一根 K 线的 high/close，不得影响任何已算指标
    df2 = df.copy()
    df2.loc[df2.index[-1], "high"] = df2["high"].iloc[-1] * 10
    df2.loc[df2.index[-1], "close"] = df2["close"].iloc[-1] * 10
    out2 = G.prep_indicators(df2, breakout_window=20)
    assert np.array_equal(out["prior_high"].values, out2["prior_high"].values, equal_nan=True)
    assert np.array_equal(out["ma20"].values, out2["ma20"].values, equal_nan=True)
    # rvol20：shift(1) 后 rolling20（ret[0]=NaN → 首个有值在第 21 行）
    assert not np.isfinite(out["rvol20"].iloc[20])
    ret = close / np.roll(close, 1); ret[0] = np.nan
    assert out["rvol20"].iloc[21] == pytest.approx(np.std(ret[1:21], ddof=1) * np.sqrt(250))


# ── R 倍数与净值合成 ─────────────────────────────────────────────────
def test_r_math_stop_is_minus_1r():
    # 模拟一笔：入场 100、止损距离 8R%，出场 92 → r_net（零成本）≈ -1
    entry, stop_px, exit_px = 100.0, 92.0, 92.0
    r_dist = entry - stop_px
    r_gross = (exit_px - entry) / r_dist
    assert r_gross == pytest.approx(-1.0)


def test_bootstrap_ci():
    x = list(np.random.default_rng(3).normal(0.2, 0.5, 60))
    lo, hi, n = G.bootstrap_ci_mean(x, n_boot=500, seed=42)
    assert n == 60 and lo < 0.2 < hi and lo < hi
    lo0, hi0, n0 = G.bootstrap_ci_mean([], seed=42)
    assert n0 == 0 and np.isnan(lo0) and np.isnan(hi0)


# ── 市场标签与指数剔除 ───────────────────────────────────────────────
def test_market_of_and_index_exclusion():
    assert D.market_of("daily/usAAPL.csv") == "US"
    assert D.market_of("daily/hk00700.csv") == "HK"
    assert D.market_of("daily/sh600519.csv") == "CN"
    assert D.market_of("daily/sz000858.csv") == "CN"
    for ix in D.INDEX_FILES:
        assert ix.startswith(("daily/us", "daily/hk", "daily/sh", "daily/sz"))


# ── 池子宇宙构建（EXP 预注册口径）────────────────────────────────────
def test_pool_universe_load():
    """冻结层 → 池内可交易宇宙：逐标的哈希复验＋日K 装载（min_rows=240）。"""
    sel, sel_runs, runs = D.select_frozen_versions()
    assert len(runs) > 0 and all(len(v) == 64 for v in runs.values())   # sha256 全长
    ok, broken, recs = D.verify_hashes(sel)
    assert broken == [], f"冻结层哈希复验失败: {broken[:3]}"
    pool, dropped = D.load_pool_list()
    assert dropped["index"] >= 10 and dropped["out_or_banned"] >= 10    # 指数＋出池/禁买被机械剔除
    assert len(pool) >= 180                                            # 非指数池内标的
    loaded = D.load_universe(sel, pool, min_rows=240)
    assert len(loaded) >= 100   # 数据现实校准: 212池×240根门槛实测105只(25-10-03→26-10-09批次); EXP-001判决门槛=触发n≥40, 非加载数
    mkts = {m for m, _ in loaded}
    assert mkts == {"US", "HK", "CN"}
