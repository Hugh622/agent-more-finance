# -*- coding: utf-8 -*-
"""engine.py — 事件驱动回测核心（P2 最低规格：point-in-time 指标、next_tradable_bar 入场、
C23 收市口径触发、三地分参成本、诚实分层报告）。单标的向量化预计算＋逐 bar 事件循环。
成交约定（P1③ 规格锚定，预注册不可事后切换）：
  · 触发一律收盘确认（C23）
  · 入场：确认日 T 的下一可成交 bar 收盘价成交（entry_effective=next_tradable_bar）
  · 退出：触发日 T 当日收盘成交（收盘竞价/MOC 流程内可执行，计入滑点）
  · E0@1.2.0 承载分工（预注册声明）：EXP-001/002 单笔层=事件窗禁新入场；
    减仓语义（只减不加的『减』）于 EXP-003 组合层以 1/3 减仓全口径承载
"""
import numpy as np
import pandas as pd

from . import cost as costmod
from . import rules_exit, rules_p0


def prep_indicators(df, breakout_window):
    """point-in-time 指标：rolling 后整体 shift 不做——prior_high/vol_ma20/MA 已用 shift(1) 对齐，
    即 t 日引用的是 t-1 及更早的信息，杜绝未来函数。"""
    out = df.copy()
    out["prior_high"] = df["high"].shift(1).rolling(breakout_window, min_periods=breakout_window).max()
    out["vol_ma20"] = df["volume"].shift(1).rolling(20, min_periods=20).mean()
    out["ma10"] = df["close"].shift(1).rolling(10, min_periods=10).mean()
    out["ma20"] = df["close"].shift(1).rolling(20, min_periods=20).mean()
    out["ma50"] = df["close"].shift(1).rolling(50, min_periods=50).mean()
    ret = df["close"].pct_change()
    out["rvol20"] = ret.shift(1).rolling(20, min_periods=20).std() * np.sqrt(250)
    return out


def run_single(df, market, exit_mode="p0", breakout_window=20, buffer_pct=0.002,
               vol_gate=1.5, vol_soft_floor=1.2, e0_block=True, e0_mask=None,
               stress=1.0, counterfactual=False):
    """单标的逐 bar 事件循环，返回交易列表（单位口径，减半按 0.5/0.5 加权计 R）。
    exit_mode: 'p0'（EXP-001 预注册退出=C11 止损＋C3 三日二守失效＋窗尾强制平）
               或 ma_slide_exit 的 arm 名（EXP-002 退出政策族，减半事件加权）
    counterfactual=True: MA20 回踩收复入场（EXP-001 基准反事实），退出同 p0"""
    d = prep_indicators(df, breakout_window)
    dates = pd.DatetimeIndex(d["date"])
    close = d["close"].to_numpy(float)
    high = d["high"].to_numpy(float)
    low = d["low"].to_numpy(float)
    vol = d["volume"].to_numpy(float)
    prior_high = d["prior_high"].to_numpy(float)
    vol_ma20 = d["vol_ma20"].to_numpy(float)
    ma10, ma20, ma50 = d["ma10"].to_numpy(float), d["ma20"].to_numpy(float), d["ma50"].to_numpy(float)
    n = len(d)
    c_buy = costmod.side_cost(market, "buy", stress)
    c_sell = costmod.side_cost(market, "sell", stress)
    offs = np.arange(n)

    if counterfactual:
        touch = np.isfinite(ma20) & (low <= ma20)
        reclaim = np.isfinite(ma20) & (close > ma20)
        sig = touch & reclaim
    else:
        sig = rules_p0.c1_close_break(close, prior_high, buffer_pct)
    if e0_block and e0_mask is not None:
        sig = sig & (~e0_mask)

    c2 = rules_p0.c2_volume_gate(vol, vol_ma20, vol_gate, vol_soft_floor) if not counterfactual \
        else np.where(np.isfinite(vol_ma20), "full", "fail")

    trades = []
    i = 0
    warmup = 55
    while i < n:
        if i < warmup or not (sig[i] and c2[i] in ("full", "half") and i + 1 < n):
            i += 1
            continue
        e_i = i + 1
        stop = rules_exit.c11_hard_stop(close[e_i])
        r_dist = close[e_i] - stop
        if r_dist <= 0:
            i += 1
            continue
        _, failed_all = rules_p0.c3_three_day_hold(close, prior_high, offs - i,
                                                   hold_days=3, buffer_pct=buffer_pct)
        arm_act = None if exit_mode == "p0" else rules_exit.ma_slide_exit(exit_mode, close, ma10, ma20, ma50)
        entry = close[e_i] * (1.0 + c_buy)
        half_cut = (c2[i] == "half")
        remaining, exit_px = 1.0, 0.0  # exit_px 加权聚合
        exit_i, reason = None, None
        mfe_x, mae_x = 0.0, 0.0
        j = e_i + 1
        while j < n:
            mfe_x = max(mfe_x, (high[j] - close[e_i]) / r_dist)
            mae_x = min(mae_x, (low[j] - close[e_i]) / r_dist)
            if arm_act is not None:
                a = arm_act[j]
                if a == "clear":
                    exit_px += close[j] * (1.0 - c_sell) * remaining
                    exit_i, reason = j, f"MA_CLEAR_{exit_mode}"
                    break
                if a == "half" and remaining > 0.5:
                    exit_px += close[j] * (1.0 - c_sell) * 0.5
                    remaining = 0.5
                j += 1
                continue
            if close[j] < stop:
                exit_px = close[j] * (1.0 - c_sell) * remaining
                exit_i, reason = j, "C11_STOP"
                break
            if failed_all[j]:
                exit_px = close[j] * (1.0 - c_sell) * remaining
                exit_i, reason = j, "C3_FAIL"
                break
            j += 1
        if exit_i is None:
            exit_px = close[n - 1] * (1.0 - c_sell) * remaining
            exit_i, reason = n - 1, "WINDOW_END"
        r_gross = (close[exit_i] - close[e_i]) / r_dist
        r_net = (exit_px - entry) / r_dist
        trades.append({
            "market": market, "entry_date": str(dates[e_i].date()),
            "exit_date": str(dates[exit_i].date()), "entry_px": close[e_i],
            "exit_px": close[exit_i], "r_dist": r_dist, "r_gross": r_gross, "r_net": r_net,
            "mfe_r": mfe_x, "mae_r": mae_x, "exit_reason": reason,
            "half_entry": half_cut, "hold_days": exit_i - e_i,
        })
        i = exit_i + 1  # 单标的单仓不重叠（预注册口径）
    return trades


def bootstrap_ci_mean(x, n_boot=1000, ci=0.90, seed=42):
    """bootstrap 均值置信区间（EXP-2026-001 判决件；种子 42 预注册）"""
    x = np.asarray([v for v in x if np.isfinite(v)], dtype=float)
    if len(x) == 0:
        return (np.nan, np.nan, 0)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    means = x[idx].mean(axis=1)
    lo, hi = np.quantile(means, [(1 - ci) / 2, 1 - (1 - ci) / 2])
    return (float(lo), float(hi), len(x))
