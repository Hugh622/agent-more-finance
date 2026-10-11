# -*- coding: utf-8 -*-
"""rules 子包：条款库 / 闸门 / 仓位公式。"""
from .clauses import CLAUSES, Clause, ClauseStatus, official_clauses, clauses_by_status
from .gates import GATES, CONCENTRATION, HK_FREEZE_LIMIT, audit_plan, TradePlanInput, GateResult, Verdict, worst_verdict
from . import position_sizing
from .position_sizing import (VOL_TARGET_ANNUAL, position_size, max_loss, risk_reward,
                              scale_out_plan, IncomeScenario, INCOME_SCENARIOS)

__all__ = [
    "CLAUSES", "Clause", "ClauseStatus", "official_clauses", "clauses_by_status",
    "GATES", "CONCENTRATION", "HK_FREEZE_LIMIT", "audit_plan", "TradePlanInput",
    "GateResult", "Verdict", "worst_verdict",
    "position_sizing", "VOL_TARGET_ANNUAL", "position_size", "max_loss", "risk_reward",
    "scale_out_plan", "IncomeScenario", "INCOME_SCENARIOS",
]
