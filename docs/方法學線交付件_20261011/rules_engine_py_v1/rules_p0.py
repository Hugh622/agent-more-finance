# -*- coding: utf-8 -*-
"""rules_p0.py — P0 确认制家族逻辑主体（注册册 rules_registry_20261011.yaml 的 logic_ref 落点）
参数一律由调用方传入（来自注册册 parameters 字段），本模块不硬编码业务参数。
时序契约（C23 收市口径 + R-1）：所有确认以收盘价判定；盘中越位只发预警不作确认。
"""
import numpy as np
import pandas as pd


def c1_close_break(close, breakout_level, buffer_pct):
    """P0.C1@1.0.0 收盘越位确认：close > 前高突破位 × (1+buffer) 才确认；盘中越位不作数。
    close/breakout_level: np.ndarray（breakout_level=前 N 日最高价，已 shift 1）"""
    close = np.asarray(close, dtype=float)
    bl = np.asarray(breakout_level, dtype=float)
    out = np.zeros(len(close), dtype=bool)
    ok = np.isfinite(close) & np.isfinite(bl)
    out[ok] = close[ok] > bl[ok] * (1.0 + float(buffer_pct))
    return out


def c1_close_break_v12(close, breakout_level, buffer_pct, session=None):
    """P0.C1@1.2.0 美市收盘明文修订（23/5）：确认价=16:00 ET OCP（正式收盘竞价 print）；
    23×5 隔夜段『T』条件打印不具确认资格。session 数组取值 'R'(常规)/'T'(隔夜)；
    本引擎消费的日K为常规段复合 OCP bar，session 传入时 'T' 行一律拒绝确认。"""
    base = c1_close_break(close, breakout_level, buffer_pct)
    if session is None:
        return base
    sess = np.asarray(session)
    return base & (sess != "T")


def c2_volume_gate(volume, vol_ma20, vol_gate=1.5, vol_soft_floor=1.2, vol_fail_floor=1.0):
    """P0.C2@1.2.0 量能闸：≥vol_gate → 'full'；[vol_soft_floor, vol_gate) → 'half'（确认维持仓位减半观察）；
    <vol_soft_floor → 'fail'；跌破 vol_fail_floor 属硬失效（R9 底线，语义并入 fail）。
    返回 np.ndarray[object]，warmup 段（vol_ma20 缺失）= 'fail'。"""
    vol = np.asarray(volume, dtype=float)
    ma = np.asarray(vol_ma20, dtype=float)
    out = np.full(len(vol), "fail", dtype=object)
    ok = np.isfinite(vol) & np.isfinite(ma) & (ma > 0)
    ratio = np.full(len(vol), np.nan)
    ratio[ok] = vol[ok] / ma[ok]
    out[ok & (ratio >= vol_gate)] = "full"
    out[ok & (ratio >= vol_soft_floor) & (ratio < vol_gate)] = "half"
    return out


def c3_three_day_hold(close, breakout_level, day_offset, hold_days=3, need=2, buffer_pct=0.002):
    """P0.C3@1.2.0 三日二守：突破确认后 hold_days 个交易日内 ≥need 日收于突破位×(1+buffer) 上方。
    day_offset: 突破确认日到当前 bar 的交易日偏移（0=确认日本身，entry 在确认日次 bar）。
    返回 (守位布尔数组, 失效日布尔数组)：失效=偏移已达 hold_days 且窗口内累计守位数<need。
    判定窗=确认后第 1..hold_days 个交易日（确认日本身不计）；单次确认事件调用一次。"""
    close = np.asarray(close, dtype=float)
    bl = np.asarray(breakout_level, dtype=float)
    off = np.asarray(day_offset)
    above = np.isfinite(close) & np.isfinite(bl) & (close > bl * (1.0 + float(buffer_pct)))
    held = above & (off >= 1) & (off <= hold_days)
    held_count = int(held.sum())          # 同一确认事件内累计守位数
    failed = (off == hold_days) & (held_count < int(need))
    return held, failed


def e0_event_mask(dates, decision_dates, window_td=1, market="US", trading_calendar=None):
    """P0.E0@1.2.0 事件窗：FOMC 决议日 ±window_td 交易日 只减不加。
    锚定规则（决议公布时点锚定，三地日历对齐）：
      · US：决议日当日本地交易日；若非交易日→顺延下一交易日。
      · HK/CN：决议公布于美东 14:00 ET＝当地凌晨 → 锚定到决议日之后的第一个本地交易日。
    返回该标的日历上的布尔掩码（窗口内 True）。
    decision_dates: 可迭代 'YYYY-MM-DD'；dates: 该标的交易日序列（DatetimeIndex 或 str 序列）"""
    d = pd.DatetimeIndex(pd.to_datetime(pd.Series(list(dates))))
    local = pd.DatetimeIndex(sorted(d))
    if trading_calendar is not None:
        local = pd.DatetimeIndex(sorted(pd.to_datetime(pd.Series(list(trading_calendar)))))
    anchors = []
    for ds in decision_dates:
        dd = pd.Timestamp(ds)
        # 锚定模式：US（及退役版 v1.0.0 的 market=None）取「首个 >= 决议日」本地交易日；
        # HK/CN（v1.2.0 分市锚定）决议公布于美东凌晨 → 取「首个 > 决议日」本地交易日。
        if market in ("HK", "CN"):
            nxt = local[local > dd]
        else:
            nxt = local[local >= dd]
        anchor = nxt[0] if len(nxt) else None
        if anchor is not None:
            anchors.append(anchor)
    mask = np.zeros(len(d), dtype=bool)
    pos = {ts: i for i, ts in enumerate(local)}
    for a in anchors:
        i = pos.get(a)
        if i is None:
            continue
        lo, hi = max(0, i - window_td), min(len(local) - 1, i + window_td)
        # 窗口按「本地交易日索引」而非自然日
        for k in range(lo, hi + 1):
            ts = local[k]
            idx = np.searchsorted(d, ts)
            if idx < len(d) and d[idx] == ts:
                mask[idx] = True
    return mask


def e1_whipsaw_filter(ma5, ma10, ma20, atr14, adx14=None, adx_threshold=20):
    """P0.E1@1.0.0 环境过滤器：MA5/10/20 高低差 < 1×ATR14 → 缠绕停做突破类 setup；
    ADX14 > adx_threshold 且均线发散解除才恢复。本函数实现缠绕+ADX 双条件；
    EXP-2026-001/002 预注册未挂载 E1（rule_ids 不含），此处仅注册册 logic 承载＋单测。"""
    ma5, ma10, ma20, atr = map(lambda x: np.asarray(x, dtype=float), (ma5, ma10, ma20, atr14))
    span = np.fmax(ma5, np.fmax(ma10, ma20)) - np.fmin(ma5, np.fmin(ma10, ma20))
    entangled = np.isfinite(span) & np.isfinite(atr) & (atr > 0) & (span < atr)
    if adx14 is None:
        return ~entangled  # True=允许开新突破 setup
    adx = np.asarray(adx14, dtype=float)
    return (~entangled) & (np.isfinite(adx) & (adx > adx_threshold) | ~np.isfinite(adx) & ~entangled)


# ───────────────────────── 名称契约对齐层（注册册 logic_ref ↔ 引擎调用名，2026-10-12 P1② 定稿补） ─────────────────────────

def c2_volume_gate_v10(volume, vol_ma20, vol_gate=1.5):
    """P0.C2@1.0.0（退役版，仅历史链承载）：量比 ≥ vol_gate → full，否则 none。无半档、无失效档。"""
    ratio = np.asarray(volume, dtype=float) / np.asarray(vol_ma20, dtype=float)
    out = np.isfinite(ratio) & (ratio >= float(vol_gate))
    return out


def c2_volume_gate_v12(volume, vol_ma20, vol_gate=1.5, vol_soft_floor=1.2, vol_fail_floor=1.0):
    """P0.C2@1.2.0 现行版（=c2_volume_gate 主名）；显式别名供注册册 logic_ref 直指。"""
    return c2_volume_gate(volume, vol_ma20, vol_gate, vol_soft_floor, vol_fail_floor)


def c3_three_day_two_hold(close, breakout_level, day_offset, hold_days=3, need=2, buffer_pct=0.002):
    """P0.C3@1.0.0（注册册名；引擎内部沿用 c3_three_day_hold 主名）。"""
    return c3_three_day_hold(close, breakout_level, day_offset, hold_days, need, buffer_pct)


def e0_event_filter(dates, decision_dates, window_td=1):
    """P0.E0@1.0.0（退役版，仅历史链承载）：决议日 ±window_td 交易日 内 → True（单市场、无日历分市）。"""
    return e0_event_mask(dates, decision_dates, window_td=window_td, market=None, trading_calendar=None)


def e0_event_filter_v12(dates, decision_dates, window_td=1, market="US", trading_calendar=None):
    """P0.E0@1.2.0 现行版（=e0_event_mask 主名，三地日历分市）；显式别名供注册册 logic_ref 直指。"""
    return e0_event_mask(dates, decision_dates, window_td=window_td,
                         market=market, trading_calendar=trading_calendar)


def r2_probe_confirm(close_confirmed, volume_state, probe_frac=1.0 / 3.0,
                     topup_gate=("c1_close", "c2_full")):
    """R2@1.0.0 试仓 1/3＋收盘确认两段制：
      盘中越线 → 只建试仓（probe_frac=1/3，止损即设）——用仓位换时间；
      收盘确认（close_confirmed=C1 收盘越位 True）且量能 full（volume_state='full'）→ 补足标准仓（top-up）；
      收盘不确认 → 试仓即止损，不得「再等等」（else 分支明文）。
    返回 dict(action, size_frac)：action ∈ {'probe','top_up','abort'}。"""
    c1_ok = bool(close_confirmed)
    c2_ok = (volume_state == "full")
    if c1_ok and c2_ok:
        return {"action": "top_up", "size_frac": 1.0,
                "note": "收盘 C1 越位＋C2 full：试仓补足标准仓"}
    if c1_ok and "c2_full" not in topup_gate:
        return {"action": "top_up", "size_frac": 1.0, "note": "收盘确认（量能档放宽）"}
    if c1_ok:
        return {"action": "probe", "size_frac": float(probe_frac),
                "note": "收盘越位但量能不足：维持试仓（半档观察）"}
    return {"action": "abort", "size_frac": 0.0,
            "note": "收盘不确认：试仓即止损，唔准再等等"}


def d3_overnight_fail_stats(crossed_buf, closed_back_below):
    """D3@1.0.0 隔夜假突破统计（23/5 新制：越线收回只记不动，60 日后检讨假突破频率）：
      crossed_buf: 盘中/开盘越「突破位＋0.2%缓冲」布尔序列；
      closed_back_below: 同日收盘收回线下布尔序列。
    返回 dict(n_cross, n_fail, fail_rate)——n_fail=越线且收回（隔夜假突破），fail_rate 供 60 日检讨。"""
    c = np.asarray(crossed_buf, dtype=bool)
    b = np.asarray(closed_back_below, dtype=bool)
    n_cross = int(c.sum())
    n_fail = int((c & b).sum())
    return {"n_cross": n_cross, "n_fail": n_fail,
            "fail_rate": (n_fail / n_cross) if n_cross else float("nan")}


def e1_environment_filter(ma5, ma10, ma20, atr14, adx14=None, adx_threshold=20):
    """P0.E1@1.0.0（注册册 logic_ref 名＝e1_environment_filter；主名 e1_whipsaw_filter 缠绕过滤器）。"""
    return e1_whipsaw_filter(ma5, ma10, ma20, atr14, adx14, adx_threshold)
