# -*- coding: utf-8 -*-
"""rules_bubble.py — 泡沫監測家族邏輯主體（註冊冊 C17/C18/C19 的 logic_ref 落點）
參數一律由調用方傳入（來自註冊冊 parameters 欄位），本模組不硬編碼業務參數。
C17 的 L1-L10 信號定義留存在註冊冊 parameters.l_signals（明文主冊），本模組只做
「分數→檔位→主題倉上限→行動清單」的狀態機映射；判分本身（週評）為流程類職責。
"""
import numpy as np

# C17 檔位映射（重標定版 2026-09-27 定稿；score→(檔名, 主題倉上限, 行動)）
C17_TIERS = [
    (8.0,  "PARABOLIC_END", 0.02, ["只准減不准加"]),
    (6.0,  "LATE",          0.08, ["只留 leader", "止加倉", "拋物線減半"]),
    (4.0,  "ALERT",         0.12, ["禁新開拋物線股"]),
    (-np.inf, "NORMAL",     0.20, []),
]


def c17_state_machine(score, jump_signals=None, current_tier="NORMAL"):
    """C17@1.0.0 十信號泡沫狀態機：score（允許半檔，如 3.5）→ 檔位＋主題倉上限。
    jump_signals: L1/L5/L9 中由❌轉✅的信號列表——任兩條齊跳 → 檔位即時上調一級
    （jump_rule，快於週評節奏）；僅允許向上跳，不回跳（回跳走週評）。
    返回 dict(tier, cap, actions, jumped)。score 為 None（未評分）→ 維持 current_tier。"""
    if score is None:
        for hi, name, cap, acts in C17_TIERS:
            if name == current_tier:
                return {"tier": name, "cap": cap, "actions": acts, "jumped": False}
        return {"tier": current_tier, "cap": None, "actions": [], "jumped": False}
    tier, cap, acts = None, None, None
    for hi, name, c, a in C17_TIERS:
        if score >= hi:
            tier, cap, acts = name, c, a
            break
    jumped = False
    if jump_signals and len(set(jump_signals) & {"L1", "L5", "L9"}) >= 2:
        order = ["NORMAL", "ALERT", "LATE", "PARABOLIC_END"]
        idx = min(order.index(tier) + 1, len(order) - 1)
        tier = order[idx]
        for hi, name, c, a in C17_TIERS:
            if name == tier:
                cap, acts = c, a
                break
        jumped = True
    return {"tier": tier, "cap": cap, "actions": acts, "jumped": jumped}


def c18_realtime_gates(close, ma50, ma200, high_200dma_reach, roc_6m, roc_12m,
                       updown_vol_ratio_20d, t3_streak_days,
                       t1_parabolic_reach=0.60, t2_roc_half=0.5,
                       t3_ratio_max=0.7, t3_streak_min=5):
    """C18@1.0.0 即時觸發閘 T1-T3（即時執行不等週評；T4 為現行閘重申不佔編號，本函數不承載）：
      T1 拋物線閘：高於 200DMA 曾達 +t1_parabolic_reach 以上，其後收穿 50MA→減半；收穿 200DMA→清（主題倉部分）
      T2 背離閘：指數新高而 12m ROC < t2_roc_half×6m ROC → 主題倉減半（指數新高由調用方狀態承載，此處判 ROC 條件）
      T3 派發閘：20 日量比 < t3_ratio_max 連續 t3_streak_min 日＋收穿 50MA → 減半
    返回 dict(t1, t2, t3, worst)：每閘為 'clear'/'half'/None；worst=最嚴動作（衝突取嚴）。
    once_only（同一觸發事件只執行一次、不疊加）由調用方以已執行事件集承載。"""
    close = float(close); ma50 = float(ma50); ma200 = float(ma200)
    t1 = None
    if np.isfinite(high_200dma_reach) and high_200dma_reach >= t1_parabolic_reach:
        if np.isfinite(close) and np.isfinite(ma200) and close < ma200:
            t1 = "clear"
        elif np.isfinite(close) and np.isfinite(ma50) and close < ma50:
            t1 = "half"
    t2 = None
    if (np.isfinite(roc_6m) and np.isfinite(roc_12m)
            and roc_6m > 0 and roc_12m < t2_roc_half * roc_6m):
        t2 = "half"
    t3 = None
    if (np.isfinite(updown_vol_ratio_20d) and np.isfinite(t3_streak_days)
            and updown_vol_ratio_20d < t3_ratio_max and t3_streak_days >= t3_streak_min
            and np.isfinite(close) and np.isfinite(ma50) and close < ma50):
        t3 = "half"
    rank = {"half": 1, "clear": 2}
    worst = max([g for g in (t1, t2, t3) if g], key=lambda g: rank[g], default=None)
    return {"t1": t1, "t2": t2, "t3": t3, "worst": worst}


def c19_post_burst(days_since_burst, days_since_trough=None,
                   dead_cat_days=45, reentry_min_days=53):
    """C19@1.0.0 爆破後右側回補＋倖存者濾網（時間閘部分）：
      距爆破 < dead_cat_days（45 日）內的反彈一律按「死貓跳」處理——禁止回補；
      距谷底 ≥ reentry_min_days（53 日）＋右側三確認（收盤站上 200DMA＋3-10 日回踩不破二守；
      倖存者濾網三條件由調用方按 parameters.survivor_filter 裁定）→ 准首批回補（≤目標倉 1/3）。
    返回 dict(phase, allow_reentry, note)。"""
    if days_since_burst is None:
        return {"phase": "no_burst", "allow_reentry": False, "note": "無爆破記錄"}
    if days_since_burst < dead_cat_days:
        return {"phase": "dead_cat_window", "allow_reentry": False,
                "note": f"爆破後 {days_since_burst} 日 < {dead_cat_days}：反彈按死貓跳處理，禁回補"}
    dt = days_since_trough if days_since_trough is not None else days_since_burst
    if dt >= reentry_min_days:
        return {"phase": "reentry_eligible", "allow_reentry": True,
                "note": f"距谷底 {dt} 日 ≥ {reentry_min_days}：右側三批劇本首批准（≤目標倉1/3，二守確認後）"}
    return {"phase": "cooling", "allow_reentry": False,
            "note": f"已過死貓窗但距谷底 {dt} 日 < {reentry_min_days}：繼續觀察"}
