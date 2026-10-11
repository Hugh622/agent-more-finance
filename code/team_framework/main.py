# -*- coding: utf-8 -*-
"""CLI 入口：python -m team_framework.main [overview|gates|calendar|selftest]"""
from __future__ import annotations
import sys

from .rules.gates import TradePlanInput, ThemeState, audit_plan, worst_verdict, Verdict
from .signals import phase_transition, score_to_phase
from .rules.clauses import ClauseStatus, official_clauses
from .calendar_schedule import next_nodes, pending_decisions


def overview() -> None:
    from . import (ROLES, THREE_MARKETS, L_LAYERS, SIGNALS_V2, IRON_RULES,
                   CLAUSES, GATES, ARCHIVE_MAP, __version__)
    print(f"team_framework v{__version__} —— 五 Agent 投研团队·框架代码化内核\n")
    print("【组织】")
    for r in ROLES:
        print(f"  [{r.layer}] {r.title}: {r.responsibilities[0]}")
    print("  " + "-" * 40)
    print(f"【覆盖】三地市场: {', '.join(m.value for m in THREE_MARKETS)}")
    print("【分层】")
    for k, v in L_LAYERS.items():
        print(f"  {k}: {v}")
    print(f"【条款库】v1.3 共 {len(CLAUSES)} 条（正式 {len(official_clauses())} 条）")
    print(f"【五闸】{', '.join(g.code for g in GATES)}  →  详见 gates.audit_plan()")
    print(f"【十信号】{', '.join(s.code for s in SIGNALS_V2)}")
    print(f"【铁律】{len(IRON_RULES)} 条（收盘确认制/限价不追高/只减不加窗/单笔≤0.5% …）")
    print("【档案库】")
    for f in ARCHIVE_MAP:
        print(f"  {f.path}: {f.desc}")
    print("\n自检: python -m team_framework.main selftest")


def demo_gates() -> None:
    """示例：一个拟议计划过五闸审计。"""
    plan = TradePlanInput(
        geo_level="L1", theme_state=ThemeState.ALERT,
        total_equity=31.0, stock_total=13.0,
        single_positions={"NVDA": 6.0, "CRWD": 4.0, "GLDM": 3.0},
        sector_exposure={"半导体": 30.0, "网络安全": 8.0, "黄金": 3.0},
        theme_total=8.0, hk_total=0.0,
        atr_pct={"NVDA": 38.0, "CRWD": 45.0, "GLDM": 15.0},  # 年化波动率%
    )
    results = audit_plan(plan)
    print("五闸审计示例（NVDA 6% + CRWD 4% + GLDM 3%）:")
    for r in results:
        print(f"  [{r.verdict.value}] {r.gate}: {r.detail}")
    print(f"  ⇒ 总裁决: {worst_verdict(results).value}")


def show_calendar() -> None:
    print("未来节点:")
    for node in next_nodes(n=8):
        print(f"  {node.day} [{node.kind}] {node.event}  {node.decision_point}")


def selftest() -> None:
    print("== 自检 ==")
    # 1) 五闸 BLOCK 案例
    bad = TradePlanInput(
        geo_level="L1", theme_state=ThemeState.ALERT,
        total_equity=36.0, stock_total=33.0,
        single_positions={"XYZ": 6.0},
        sector_exposure={"半导体": 45.0},
        theme_total=15.0, hk_total=8.0,
        atr_pct={"XYZ": 30.0})   # 年化波动率 30% → cap 13.3%，6% PASS；闸由合计与板块触发
    res = audit_plan(bad)
    assert worst_verdict(res) is Verdict.BLOCK, "超限计划必须 BLOCK"
    print("  [OK] 五闸审计：超限计划判 BLOCK")
    # 2) 仓位公式
    from .rules.position_sizing import position_size
    assert position_size(45.0) == 8.89, "年化波动 45% → 8.89%"
    assert position_size(20.0) == 15.0, "低波动 → 封顶15%"
    try:
        position_size(None)
        raise AssertionError("缺 ATR 应拒绝套公式")
    except ValueError:
        print("  [OK] 仓位公式：波动率目标制 + 缺数据拒绝")
    # 3) 状态机
    tr = phase_transition(3.5, 4.5, score_to_phase(3.5))
    assert tr["phase"].value == "WATCH", "半分摆动不得翻转状态闸"
    print("  [OK] 十信号仲裁：半分摆动不翻转（9/28 判例）")
    # 4) 条款库
    n_official = len(official_clauses())
    assert n_official >= 18, f"正式条款数量异常: {n_official}"
    print(f"  [OK] 条款库：正式条款 {n_official} 条")
    print("全部自检通过。")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "overview"
    {"overview": overview, "gates": demo_gates,
     "calendar": show_calendar, "selftest": selftest}.get(cmd, overview)()


if __name__ == "__main__":
    main()
