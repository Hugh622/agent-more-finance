# -*- coding: utf-8 -*-
"""rules_sizing.py — 倉位家族邏輯主體（註冊冊 C5/R8 的 logic_ref 落點）
參數一律由調用方傳入（來自註冊冊 parameters 欄位），本模組不硬編碼業務參數。
"""
import numpy as np


def c5_vol_coefficient(vol_percentile, current_coeff=1.0,
                       pctl_high=80, coeff_high=0.6, pctl_restore=60):
    """C5@1.0.0 波動率分位→倉位係數（滯回狀態機）：
    20 日實現波動率分位 ≥ pctl_high → 係數降為 coeff_high；
    回落至 ≤ pctl_restore → 恢復 1.0；中間區間保持現狀（防在閾值附近抖動）。
    vol_percentile: 標量或數組（0-100）；current_coeff: 上一狀態係數（數組時逐元素）。"""
    p = np.asarray(vol_percentile, dtype=float)
    cur = np.asarray(current_coeff, dtype=float)
    out = np.where(p >= pctl_high, float(coeff_high), cur)
    out = np.where(p <= pctl_restore, 1.0, out)
    return out if out.ndim else float(out)


def r8_dip_adding(ma200_slope, rsi14, stretch_atr20, budget_remaining, reclaim_volume_ratio,
                  rsi_max=30.0, stretch_min_atr=2.0, reclaim_vol_min=1.2):
    """R8@1.0.0 左側加碼四件套（全部為真才准加碼，缺一即 0）：
    f1 趨勢過濾：200 天線斜率 > 0（向下只 DCA 不加碼）；
    f2 超賣：RSI14 < rsi_max 且偏離 50 天線 > stretch_min_atr×ATR20（stretch_atr20 由調用方預算）；
    f3 預算封頂：年度左側預算餘額 > 0；
    f4 企穩確認：跌穿後收復且量 ≥ reclaim_vol_min×（確認先生效，非掛單等價）。
    返回 (allow: bool, failed: list)。"""
    failed = []
    f1 = bool(np.isfinite(ma200_slope) and ma200_slope > 0)
    if not f1: failed.append("f1_trend_filter")
    f2 = bool(np.isfinite(rsi14) and np.isfinite(stretch_atr20)
              and rsi14 < rsi_max and stretch_atr20 > stretch_min_atr)
    if not f2: failed.append("f2_oversold")
    f3 = bool(np.isfinite(budget_remaining) and budget_remaining > 0)
    if not f3: failed.append("f3_budget_cap")
    f4 = bool(np.isfinite(reclaim_volume_ratio) and reclaim_volume_ratio >= reclaim_vol_min)
    if not f4: failed.append("f4_invalidation")
    return (f1 and f2 and f3 and f4), failed
