# -*- coding: utf-8 -*-
"""rules_exit.py — 退出家族逻辑主体（EXP-2026-002 退出政策族＋C11/R3/D2 注册册承载）"""
import numpy as np
import pandas as pd


def c11_hard_stop(entry_price, technical_stop=None, floor_pct=0.08):
    """C11@1.0.0 个股止损硬顶：stop = max(技术证伪位, 入场×(1-floor_pct))。
    technical_stop 为 None 时取入场×0.92。返回每笔的止损价。"""
    hard = float(entry_price) * (1.0 - float(floor_pct))
    if technical_stop is None:
        return hard
    return max(float(technical_stop), hard)


def c11_stop_cap(entry_price, technical_stop=None, floor_pct=0.08):
    """C11@1.0.0（注册册 logic_ref 名＝c11_stop_cap；引擎内部沿用 c11_hard_stop 主名）。"""
    return c11_hard_stop(entry_price, technical_stop, floor_pct)


def ma_slide_exit(mode, close, ma10, ma20, ma50):
    """EXP-2026-002 退出政策族（预注册 arms，逐 bar 状态机）：
      mode='ma20_2consec'：close<MA20 → 减半；连续 2 日 close<MA20 → 清余
      mode='ma20_ma50'   ：close<MA20 → 减半；close<MA50 → 清余
      mode='ma10_ma20'   ：close<MA10 → 减半；close<MA20 → 清余
      mode='ma_only'     ：close<MA20 → 清仓（无确认纯均线持有）
    返回动作数组：'hold'/'half'/'clear'（从持仓在场的第一个 bar 起逐 bar 判定；
    MA 缺失段 → 'hold'（不因 warmup 误杀））"""
    close = np.asarray(close, dtype=float)
    n = len(close)
    act = np.array(["hold"] * n, dtype=object)

    def _set(mask, a):
        act[mask] = a

    below = lambda ma: np.isfinite(close) & np.isfinite(ma) & (close < ma)
    if mode == "ma_only":
        _set(below(ma20), "clear")
        return act
    if mode == "ma20_2consec":
        b20 = below(ma20)
        two = b20[:-1] & b20[1:]
        _set(b20, "half")
        _set(np.r_[False, two], "clear")
        return act
    if mode == "ma20_ma50":
        _set(below(ma20), "half")
        _set(below(ma50), "clear")
        return act
    if mode == "ma10_ma20":
        _set(below(ma10), "half")
        _set(below(ma20), "clear")
        return act
    raise ValueError(f"unknown exit arm: {mode}")


def r3_scale_out(entry_price, r_dist, high_since_entry):
    """R3@1.0.0 分批止盈：确认后上涨 ≥1R 平 50%，余仓止损上移至成本价（不许移返）。
    high_since_entry: 入场以来最高价数组。返回 (scale_out_bool, stop_to_cost_bool)"""
    entry_price = float(entry_price)
    r_dist = float(r_dist)
    h = np.asarray(high_since_entry, dtype=float)
    scale = np.isfinite(h) & (h >= entry_price + r_dist)
    return scale, scale  # 一旦 scale_out 触发，余仓 stop=成本（调用方保持状态不回退）


def d2_atr_trail(entry_price, close, atr14, r_dist, activate_r=2.0, trail_mult=2.0):
    """D2@1.0.0 余仓右尾延长：浮盈 ≥ activate_r×R 启动 trail_mult×ATR14 追踪止损（观察项，
    EXP-2026-002 预注册 arms 未含——按注册册 status=registered 仅承载逻辑＋单测）。"""
    entry_price = float(entry_price); r_dist = float(r_dist)
    c = np.asarray(close, dtype=float); a = np.asarray(atr14, dtype=float)
    activated = np.isfinite(c) & (c >= entry_price + activate_r * r_dist)
    trail_level = entry_price + activate_r * r_dist - trail_mult * a
    ok = activated & np.isfinite(a)
    lvl = np.where(ok, trail_level, np.nan)
    return lvl  # 逐 bar 追踪止损位（NaN=未激活）
