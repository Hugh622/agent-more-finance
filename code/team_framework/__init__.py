# -*- coding: utf-8 -*-
"""team_framework —— 多 Agent 投研团队：框架/流程/规则代码化内核 v1.3。

包定位（外部评审者请先读 README）：
  - 量化腿 zip = 全档案合集（原始材料）
  - 宏观腿增补包 = 组织层文档
  - 本包 = 规则与流程的【可运行代码化】：条款库/五闸审计/仓位公式/
    状态机/复盘评分均可 import 或 CLI 运行，评审者可直接改参数跑测试。
"""
__version__ = "1.3.0"

from .config import THREE_MARKETS, Horizon, Market, ENG_STANDARDS
from .roles import ROLES, USER_ROLE, COLLAB_MODES, THIRD_PARTY_SOP
from .workflow import L_LAYERS, PoolRules, DELIVERABLES, E_FLOW
from .signals import SIGNALS_V2, score_to_phase, phase_transition, Phase
from .playbook import IRON_RULES, FOUR_STATES, TRAFFIC_LIGHT, SLIDING_MA_PRINCIPLE
from .verdict import THREE_RULERS, FOUR_STAGE_MACHINE, PLAN_FIVE_ELEMENTS, FINAL_REVIEW_CHECKLIST
from .rules.clauses import CLAUSES, official_clauses, ClauseStatus
from .rules.gates import GATES, audit_plan, TradePlanInput, Verdict, worst_verdict
from .rules.position_sizing import position_size, max_loss, risk_reward, scale_out_plan, INCOME_SCENARIOS
from .review import score_reviews, ReviewItem, REVIEW_MECHANISM
from .calendar_schedule import NODES, next_nodes, pending_decisions
from .archive_map import ARCHIVE_MAP, LEDGER_SPEC, OBSERVER_LIST_SPEC

__all__ = [
    "THREE_MARKETS", "Horizon", "Market", "ENG_STANDARDS",
    "ROLES", "USER_ROLE", "COLLAB_MODES", "THIRD_PARTY_SOP",
    "L_LAYERS", "PoolRules", "DELIVERABLES", "E_FLOW",
    "SIGNALS_V2", "score_to_phase", "phase_transition", "Phase",
    "IRON_RULES", "FOUR_STATES", "TRAFFIC_LIGHT", "SLIDING_MA_PRINCIPLE",
    "THREE_RULERS", "FOUR_STAGE_MACHINE", "PLAN_FIVE_ELEMENTS", "FINAL_REVIEW_CHECKLIST",
    "CLAUSES", "official_clauses", "ClauseStatus",
    "GATES", "audit_plan", "TradePlanInput", "Verdict", "worst_verdict",
    "position_size", "max_loss", "risk_reward", "scale_out_plan", "INCOME_SCENARIOS",
    "score_reviews", "ReviewItem", "REVIEW_MECHANISM",
    "NODES", "next_nodes", "pending_decisions",
    "ARCHIVE_MAP", "LEDGER_SPEC", "OBSERVER_LIST_SPEC",
]
