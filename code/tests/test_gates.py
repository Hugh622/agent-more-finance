# -*- coding: utf-8 -*-
"""pytest 自检：闸门 / 仓位 / 状态机 / 条款库。"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from team_framework.rules.gates import (TradePlanInput, ThemeState, audit_plan,
                                        worst_verdict, Verdict)
from team_framework.rules.position_sizing import position_size, risk_reward
from team_framework.signals import phase_transition, score_to_phase
from team_framework.rules.clauses import official_clauses


def test_gate_block_on_theme_overrun():
    plan = TradePlanInput(
        geo_level="L0", theme_state=ThemeState.ALERT,
        total_equity=14.0, stock_total=10.0,
        single_positions={}, sector_exposure={},
        theme_total=15.0, hk_total=0.0)
    assert worst_verdict(audit_plan(plan)) is Verdict.BLOCK


def test_gate_pass_normal_plan():
    plan = TradePlanInput(
        geo_level="L1", theme_state=ThemeState.ALERT,
        total_equity=20.0, stock_total=12.0,
        single_positions={"CRWD": 4.0},
        sector_exposure={"网络安全": 8.0},
        theme_total=8.0, hk_total=0.0,
        atr_pct={"CRWD": 45.0})   # 年化波动率 45% → cap 8.9%，4% PASS
    assert worst_verdict(audit_plan(plan)) is not Verdict.BLOCK


def test_gate_geo_ceiling_blocks():
    plan = TradePlanInput(
        geo_level="L2", theme_state=ThemeState.ALERT,   # L2 天花板 40%
        total_equity=55.0, stock_total=20.0,
        single_positions={}, sector_exposure={}, theme_total=5.0, hk_total=0.0)
    assert worst_verdict(audit_plan(plan)) is Verdict.BLOCK


def test_position_sizing():
    assert position_size(45.0) == 8.89      # 12/(45×3)=8.89%
    assert position_size(20.0) == 15.0      # 12/60=20% → 封顶 15%
    assert risk_reward(100, 95, 115) == 3.0  # 3:1


def test_halfpoint_wobble_does_not_flip():
    tr = phase_transition(3.5, 4.5, score_to_phase(3.5))
    assert tr["phase"].value == "WATCH"
    assert "周五" in tr["action"]


def test_clauses_official_count():
    assert len(official_clauses()) >= 18
