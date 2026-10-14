# -*- coding: utf-8 -*-
"""rules_prefilter.py — Stage 2 前置過濾器邏輯主體（註冊冊 C10 的 logic_ref 落點）
參數一律由調用方傳入（來自註冊冊 parameters 欄位），本模組不硬編碼業務參數。
"""
import numpy as np


def c10_stage2(close, ma50, ma150, ma200, ma200_1m_ago, high_52w, low_52w, rs_ok=None):
    """C10@1.0.0 Stage 2 前置過濾器（Weinstein 四階段二階確認，44 標的池套用）：
    全部條件為真 → 該標的進入金字塔加倉許可狀態（Stage 2 許可）：
      ① close > 50/150/200MA（三線之上）
      ② MA150 > MA200 且 200MA 一個月前至今上行（ma200 > ma200_1m_ago）
      ③ 距 52 周低點 ≥ +30%（off_low_52w）且距 52 周高點回落 ≤ 25%（off_high_52w_max）
      ④ RS 相對強度「高」（rs_ok 由調用方按其 RS 口徑預算傳入；None=跳過該項並在返回中標注）
    輸入均可為標量或同長數組；返回 (pass: bool/ndarray, detail: dict)。"""
    close, ma50, ma150, ma200 = map(lambda x: np.asarray(x, dtype=float), (close, ma50, ma150, ma200))
    h52, l52 = np.asarray(high_52w, dtype=float), np.asarray(low_52w, dtype=float)
    m200_prev = np.asarray(ma200_1m_ago, dtype=float)

    above = (close > ma50) & (close > ma150) & (close > ma200)
    rising = (ma150 > ma200) & (ma200 > m200_prev)
    off_low = close / l52 - 1.0
    off_high = 1.0 - close / h52
    range_ok = (off_low >= 0.30) & (off_high <= 0.25)
    core = above & rising & range_ok & (np.isfinite(close) & np.isfinite(ma50)
                                        & np.isfinite(ma150) & np.isfinite(ma200)
                                        & np.isfinite(h52) & np.isfinite(l52) & np.isfinite(m200_prev))
    if rs_ok is None:
        out, detail = core, {"rs_checked": False}
    else:
        out = core & np.asarray(rs_ok, dtype=bool)
        detail = {"rs_checked": True}
    detail["off_low_52w"] = off_low if off_low.ndim else float(off_low)
    detail["off_high_52w"] = off_high if off_high.ndim else float(off_high)
    return out, detail
