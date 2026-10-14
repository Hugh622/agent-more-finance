# -*- coding: utf-8 -*-
"""test_rules.py — P0 家族逻辑主体单测（方法学线 P1②：混合模式 logic 承载层验收件）"""
import numpy as np
import pytest

from bt_engine import rules_p0 as P
from bt_engine import rules_sizing as S
from bt_engine import rules_prefilter as F
from bt_engine import rules_bubble as B
from bt_engine import rules_risk as K
from bt_engine import rules_exit as E


# ── P0.C1 ────────────────────────────────────────────────────────────
def test_c1_v10_close_break():
    bl = np.array([100.0, 100.0, np.nan])
    close = np.array([100.3, 99.9, 200.0])
    out = P.c1_close_break(close, bl, buffer_pct=0.002)
    assert out.tolist() == [True, False, False]  # NaN 位不确认


def test_c1_v12_buffer_semantics():
    bl = np.array([100.0, 100.0])
    assert P.c1_close_break_v12(np.array([100.3]), bl[:1], 0.002)[0]   # >+0.2% 确认
    assert not P.c1_close_break_v12(np.array([100.19]), bl[:1], 0.002)[0]  # 未及缓冲
    assert not P.c1_close_break_v12(np.array([99.99]), bl[:1], 0.002)[0]


# ── P0.C2 ────────────────────────────────────────────────────────────
def test_c2_v10_binary():
    vol = np.array([150.0, 140.0])
    ma = np.array([100.0, 100.0])
    assert P.c2_volume_gate_v10(vol, ma, 1.5).tolist() == [True, False]  # 1.4× 不达标（旧版无半档）


def test_c2_v12_three_state_and_fail_floor():
    vol = np.array([155.0, 130.0, 95.0, 60.0])
    ma = np.array([100.0, 100.0, 100.0, 100.0])
    out = P.c2_volume_gate_v12(vol, ma, 1.5, 1.2, 1.0)
    assert [s for s in out] == ["full", "half", "fail", "fail"]  # 1.3→half；0.95→fail（<1.2 即不合格）
    # 边界：恰 1.5→full；恰 1.2→half；1.0<soft_floor→fail（fail_floor 语义并入 fail）
    edge = P.c2_volume_gate_v12(np.array([150.0, 120.0, 100.0]), np.full(3, 100.0), 1.5, 1.2, 1.0)
    assert [s for s in edge] == ["full", "half", "fail"]


# ── P0.C3 ────────────────────────────────────────────────────────────
def test_c3_three_day_two_hold():
    bl = 100.0
    # 确认日 idx1（off=0），其后 off=1..3 三日收盘 102,101,99：守位 2 日 ≥need=2 → 不失效
    close = np.array([99.0, 100.5, 102.0, 101.0, 99.0])
    held, failed = P.c3_three_day_two_hold(close, bl, day_offset=np.array([-1, 0, 1, 2, 3]),
                                           hold_days=3, need=2, buffer_pct=0.002)
    assert held.tolist() == [False, False, True, True, False]
    assert not failed[4]                       # 累计守位 2 日 ≥ need → 第3日不触发失效
    # 只有 1 日守位 → 偏移达 hold_days 日触发失效
    close2 = np.array([99.0, 100.5, 102.0, 99.0, 99.0])
    held2, failed2 = P.c3_three_day_two_hold(close2, bl, day_offset=np.array([-1, 0, 1, 2, 3]),
                                             hold_days=3, need=2, buffer_pct=0.002)
    assert held2.sum() == 1
    assert failed2[4]


# ── P0.E0 ────────────────────────────────────────────────────────────
def test_e0_v10_and_v12_window():
    dates = np.array(["2026-01-27", "2026-01-28", "2026-01-29", "2026-02-02"], dtype="datetime64[D]")
    dec = np.array(["2026-01-28"], dtype="datetime64[D]")
    m10 = P.e0_event_filter(dates, dec, window_td=1)
    assert m10.tolist() == [True, True, True, False]  # ±1 交易日
    m12 = P.e0_event_filter_v12(dates, dec, window_td=1, market="US")
    assert (m12 == m10).all()
    # market=None（退役版）不依赖日历；v12 美市日历缺口（周末跳过）由 trading_calendar 参数承载
    assert P.e0_event_filter(dates, dec, window_td=0).tolist() == [False, True, False, False]


# ── P0.E1 / R6 ───────────────────────────────────────────────────────
def test_e1_entanglement():
    ma = np.array([10.0, 10.0, 10.0])
    out = P.e1_environment_filter(ma, ma, ma, np.array([0.1]))  # span=0 < atr → 缠绕 → 停做
    assert not out[0]
    out2 = P.e1_environment_filter(np.array([12.0]), np.array([10.0]), np.array([8.0]),
                                   np.array([0.5]))  # span=4 > atr → 发散 → 允许
    assert out2[0]


# ── R2 ───────────────────────────────────────────────────────────────
def test_r2_probe_confirm_two_stage():
    assert P.r2_probe_confirm(True, "full")["action"] == "top_up"
    assert P.r2_probe_confirm(True, "half")["action"] == "probe"
    assert P.r2_probe_confirm(False, "full")["action"] == "abort"  # 收盘不确认→试仓即止损


# ── D3 ───────────────────────────────────────────────────────────────
def test_d3_overnight_fail_stats():
    st = P.d3_overnight_fail_stats([1, 0, 1, 1], [1, 0, 0, 1])
    assert st == {"n_cross": 3, "n_fail": 2, "fail_rate": pytest.approx(2 / 3)}


# ── C5 / R8（仓位家族）───────────────────────────────────────────────
def test_c5_hysteresis():
    assert S.c5_vol_coefficient(85, 1.0) == 0.6          # ≥80 降
    assert S.c5_vol_coefficient(70, 0.6) == 0.6          # 60-80 区间保持现状
    assert S.c5_vol_coefficient(55, 0.6) == 1.0          # ≤60 恢复
    arr = S.c5_vol_coefficient(np.array([90, 70, 50]), np.array([1.0, 1.0, 0.6]))
    assert arr.tolist() == [0.6, 1.0, 1.0]


def test_r8_four_conditions():
    ok, failed = S.r8_dip_adding(0.02, 25, 2.5, 100000, 1.3)
    assert ok and failed == []
    _, failed = S.r8_dip_adding(-0.01, 25, 2.5, 100000, 1.3)   # 斜率向下
    assert "f1_trend_filter" in failed
    _, failed = S.r8_dip_adding(0.02, 35, 2.5, 100000, 1.3)    # RSI 未超卖
    assert "f2_oversold" in failed
    _, failed = S.r8_dip_adding(0.02, 25, 2.5, 0, 1.3)         # 预算用尽
    assert "f3_budget_cap" in failed
    _, failed = S.r8_dip_adding(0.02, 25, 2.5, 100000, 1.1)    # 收復量不足
    assert "f4_invalidation" in failed


# ── C10（前置过滤器）────────────────────────────────────────────────
def test_c10_stage2_full_pass():
    ok, d = F.c10_stage2(close=110.0, ma50=100.0, ma150=95.0, ma200=90.0, ma200_1m_ago=88.0,
                         high_52w=120.0, low_52w=70.0, rs_ok=True)
    assert ok and d["rs_checked"]
    # 回落幅度 8.3%≤25% 且离低点 57%≥30%
    ok2, _ = F.c10_stage2(80.0, 100.0, 95.0, 90.0, 88.0, 120.0, 70.0)  # close<ma50 → fail
    assert not ok2
    ok3, d3 = F.c10_stage2(90.0, 80.0, 70.0, 60.0, 59.0, 120.0, 70.0)   # 离低点 28.6%<30% → fail
    assert not ok3 and d3["off_low_52w"] < 0.30


# ── C17/C18/C19（泡沫家族）──────────────────────────────────────────
def test_c17_tiers():
    r = B.c17_state_machine(3.5)
    assert r["tier"] == "NORMAL" and r["cap"] == 0.20
    r = B.c17_state_machine(4.5)
    assert r["tier"] == "ALERT" and r["cap"] == 0.12
    r = B.c17_state_machine(9.0)
    assert r["tier"] == "PARABOLIC_END" and r["cap"] == 0.02 and "只准減不准加" in r["actions"][0]
    r = B.c17_state_machine(None, current_tier="LATE")
    assert r["tier"] == "LATE"  # 未评分维持现状


def test_c17_jump_rule():
    r = B.c17_state_machine(3.5, jump_signals=["L1", "L5"])
    assert r["tier"] == "ALERT" and r["jumped"]  # 任两条齐跳即时上调
    r2 = B.c17_state_machine(3.5, jump_signals=["L1"])
    assert not r2["jumped"] and r2["tier"] == "NORMAL"


def test_c18_gates():
    g = B.c18_realtime_gates(close=99.0, ma50=100.0, ma200=95.0, high_200dma_reach=1.65,
                             roc_6m=0.40, roc_12m=0.10, updown_vol_ratio_20d=0.6, t3_streak_days=5)
    assert g["t1"] == "half" and g["t2"] == "half" and g["t3"] == "half"
    assert g["worst"] == "half"
    g2 = B.c18_realtime_gates(close=94.0, ma50=100.0, ma200=95.0, high_200dma_reach=1.65,
                              roc_6m=0.40, roc_12m=0.10, updown_vol_ratio_20d=0.6, t3_streak_days=5)
    assert g2["t1"] == "clear" and g2["worst"] == "clear"  # 抛物线后收破 200DMA → 清（主題倉部分）
    g3 = B.c18_realtime_gates(close=101.0, ma50=100.0, ma200=95.0, high_200dma_reach=1.30,
                              roc_6m=0.40, roc_12m=0.30, updown_vol_ratio_20d=0.9, t3_streak_days=1)
    assert g3["worst"] is None  # 无触发


def test_c19_post_burst():
    assert not B.c19_post_burst(30, None)["allow_reentry"]       # 死貓跳窗
    assert not B.c19_post_burst(50, 50)["allow_reentry"]         # 已过窗但未到 53 日
    assert B.c19_post_burst(60, 58)["allow_reentry"]             # 谷底 58 日 → 准首批


# ── R1（风控闸）─────────────────────────────────────────────────────
def test_r1_daily_loss_gate():
    g = K.r1_daily_loss_gate(-0.025, 0)
    assert g["triggered_today"] and not g["allow_new_entry"] and not g["forced_week_off"]
    g2 = K.r1_daily_loss_gate(0.01, 0)
    assert g2["allow_new_entry"]
    g3 = K.r1_daily_loss_gate(-0.021, 1)
    assert g3["forced_week_off"] and not g3["allow_new_entry"]   # 连续 2 日 → 休市一周
    g4 = K.r1_daily_loss_gate(0.005, 1)                          # 昨日触闸今未触 → 不延续
    assert g4["allow_new_entry"] and not g4["forced_week_off"]


# ── C11/R3/D2/退出族 ─────────────────────────────────────────────────
def test_c11_stop_cap():
    assert E.c11_stop_cap(100.0) == pytest.approx(92.0)                       # 无技术位 → -8%
    assert E.c11_stop_cap(100.0, technical_stop=95.0) == pytest.approx(95.0)  # 技术位更严 → 取技术位
    assert E.c11_stop_cap(100.0, technical_stop=90.0) == pytest.approx(92.0)  # 技术位更松 → 取硬顶


def test_r3_scale_out_once():
    scale, _ = E.r3_scale_out(entry_price=100.0, r_dist=5.0, high_since_entry=np.array([104.0, 105.0, 106.0]))
    assert scale.tolist() == [False, True, True]  # 浮盈≥2R=110 → 一经触发不回退


def test_ma_slide_exit_arms():
    close = np.array([101.0, 99.0, 98.0, 97.0])
    ma10 = np.array([100.0, 100.0, 100.0, 100.0])
    ma20 = np.array([100.0, 100.0, 100.0, 100.0])
    ma50 = np.array([98.5, 98.5, 98.5, 98.5])   # 第1日close=99>98.5只破MA20; 第3日97<98.5破MA50
    a1 = E.ma_slide_exit("ma20_2consec", close, ma10, ma20, ma50)
    assert a1[1] == "half" and a1[2] == "clear" and a1[3] == "clear"  # 连续 2 日破 MA20 → 第2日清余
    a2 = E.ma_slide_exit("ma20_ma50", close, ma10, ma20, ma50)
    assert a2[1] == "half" and a2[2] == "clear" and a2[3] == "clear"  # 破MA20→half; 破MA50→clear
    a2b = E.ma_slide_exit("ma20_ma50", close, ma10, ma20, np.array([100.0]*4))
    assert a2b[1] == "clear"                                          # 同bar双破 → clear优先(最强动作)
    # 场景C: 第1日只破MA10不破MA20(99.5>99.2), 第2日双破→clear
    c3 = np.array([101.0, 99.5, 99.0, 98.0])
    a3 = E.ma_slide_exit("ma10_ma20", c3, np.array([100.0]*4), np.array([99.2]*4), ma50)
    assert a3[1] == "half" and a3[2] == "clear"
    a4 = E.ma_slide_exit("ma_only", close, ma10, ma20, ma50)
    assert a4[1] == "clear"                                          # 破 MA20 即清（无确认基准）
