# -*- coding: utf-8 -*-
"""rules_risk.py — 賬戶級風控邏輯主體（註冊冊 R1 的 logic_ref 落點）
參數一律由調用方傳入（來自註冊冊 parameters 欄位），本模組不硬編碼業務參數。
"""
import numpy as np


def r1_daily_loss_gate(daily_pnl_pct, consecutive_stop_days=0,
                       daily_loss_stop=-0.02, consecutive_max=2):
    """R1@1.0.0 賬戶級日虧損閘：
      當日虧損 ≤ daily_loss_stop（-2%）→ 即日停新倉（持倉照常管理，非清倉令）；
      連續 consecutive_max（2）個交易日觸閘 → 強制休市一週＋覆盤報告後恢復（休市期仍停新倉）；
      未觸閘的下一交易日自動重置（連續計數清零由調用方在日初執行）。
    daily_pnl_pct: 當日盈虧佔權益比（-0.03=-3%）；consecutive_stop_days: 已連續觸閘天數（含昨日之前）。
    返回 dict(allow_new_entry, triggered_today, forced_week_off, note)。"""
    today = bool(np.isfinite(daily_pnl_pct) and daily_pnl_pct <= daily_loss_stop)
    consec = int(consecutive_stop_days) + (1 if today else 0)
    week_off = consec >= consecutive_max
    if week_off:
        note = f"連續 {consec} 日觸閘 ≥ {consecutive_max}：強制休市一週，覆盤報告後恢復"
    elif today:
        note = "當日觸閘：即日停新倉（持倉照常管理）；明日自動重置計數"
    else:
        note = "未觸閘：新倉照常"
    return {"allow_new_entry": not (today or week_off),
            "triggered_today": today,
            "forced_week_off": week_off,
            "note": note}
