# -*- coding: utf-8 -*-
"""闸门体系（五闸＋天花板＋主题状态机）——可运行校验逻辑。

体系哲学：框架只加纪律不加自由；任何破闸须用户明示＋正式修订版。
数字为框架层默认值；行情触发的「当前闸值」以纸面执行台账为准。
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Verdict(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class Gate:
    code: str
    name: str
    limit: float            # 上限（% 权益）
    desc: str


# ---------------------------------------------------------------------------
# 五闸默认值（台账 v1.1 口径；事件触发后动态收紧）
# ---------------------------------------------------------------------------
GATES: tuple = (
    Gate("G-geo",  "地缘天花板（L0-L3）", 75.0,
         "L0绿75 / L1黄60 / L2橙40 / L3红≤20；等级跃迁48h内调仓，L2起优先压港股"),
    Gate("G-stock","个股合计闸", 28.0, "个股闸=总闸×70%；短中期与主题仓共用"),
    Gate("G-single","单标的闸", 12.0,
         "标准=12%÷(ATR%×3) 封顶15%；高波动≤4%；加密烈度封顶≤2%"),
    Gate("G-theme","主题仓闸（C17）", 12.0,
         "NORMAL≤20 / ALERT≤12 / LATE≤8 / END 0-2；AI十信号驱动"),
    Gate("G-total", "总权益执行闸", 36.0,
         "L2 环境执行上限（天花板40%内再留缓冲）；10Y三日>5.05%→降32-35%"),
)


# 防御链常数（闸内子结构，全部百分比单位）
HK_FREEZE_LIMIT: float = 5.0      # 港仓冻结 ≤5%（恒指 MA20 未收复）
CONCENTRATION: dict = {"core": 30.0, "core_per": 12.0, "satellite": 15.0,
                       "satellite_per": 8.0, "single_sector": 40.0,
                       "ai_two_sectors": 50.0}


# ---------------------------------------------------------------------------
# 地缘等级映射
# ---------------------------------------------------------------------------
GEO_CEILING = {"L0": 75.0, "L1": 60.0, "L2": 40.0, "L3": 20.0}
GEO_HEDGE = {"L0": 0.0, "L1": 10.0, "L2": 25.0, "L3": 40.0}
GEO_PRIORITY = ("港股", "A股", "美股")   # L2 起减仓优先序


# ---------------------------------------------------------------------------
# 主题状态机（C17）
# ---------------------------------------------------------------------------
class ThemeState(str, Enum):
    NORMAL = "NORMAL"
    ALERT = "ALERT"
    LATE = "LATE"
    END = "END"


THEME_CAP = {ThemeState.NORMAL: 20.0, ThemeState.ALERT: 12.0,
             ThemeState.LATE: 8.0, ThemeState.END: 2.0}


# ---------------------------------------------------------------------------
# 可运行校验器
# ---------------------------------------------------------------------------
@dataclass
class TradePlanInput:
    """一份待审的交易计划（纸面推演用）。"""
    geo_level: str                     # "L0".."L3"
    theme_state: ThemeState
    total_equity: float                # 拟执行总权益 %
    stock_total: float                 # 个股合计 %
    single_positions: dict             # {标的: 仓位%}
    sector_exposure: dict              # {板块: 仓位%}
    theme_total: float = 0.0           # 主题仓合计 %
    hk_total: float = 0.0              # 港股合计 %
    hedge_ratio: float = 0.0           # 对冲比例 %
    atr_pct: dict = field(default_factory=dict)  # {标的: ATR%}


@dataclass
class GateResult:
    gate: str
    verdict: Verdict
    detail: str


def _position_cap(atr_pct: Optional[float]) -> float:
    """单标的理论仓位上限：12%÷(年化波动率%×3) 封顶 15%。

    atr_pct 为百分比单位（如 45 表示年化波动率 45%）。
    例：45% → 12/(0.45×3) = 8.89%；20% → 20% 触顶 → 15%。
    """
    if not atr_pct or atr_pct <= 0:
        return 12.0
    return min(12.0 / ((atr_pct / 100.0) * 3.0), 15.0)


def audit_plan(plan: TradePlanInput) -> tuple:
    """跑五闸＋结构约束，返回 GateResult 列表。"""
    results = []
    ceiling = GEO_CEILING.get(plan.geo_level, 40.0)

    # 1) 地缘天花板
    if plan.total_equity > ceiling:
        results.append(GateResult("G-geo", Verdict.BLOCK,
                      f"总权益 {plan.total_equity}% 超地缘天花板 {ceiling}%（{plan.geo_level}）"))
    else:
        results.append(GateResult("G-geo", Verdict.PASS,
                      f"总权益 {plan.total_equity}% ≤ 天花板 {ceiling}%"))

    # 2) 对冲比例随等级
    hedge_min = GEO_HEDGE.get(plan.geo_level, 25.0)
    if plan.hedge_ratio + 1e-9 < hedge_min:
        results.append(GateResult("G-hedge", Verdict.WARN,
                      f"{plan.geo_level} 建议对冲 ≥{hedge_min}%，当前 {plan.hedge_ratio}%"))
    else:
        results.append(GateResult("G-hedge", Verdict.PASS, "对冲预算达标"))

    # 3) 个股合计闸
    if plan.stock_total > 28.0:
        results.append(GateResult("G-stock", Verdict.BLOCK,
                      f"个股合计 {plan.stock_total}% 超 28% 闸"))
    else:
        results.append(GateResult("G-stock", Verdict.PASS, "个股合计在闸内"))

    # 4) 主题状态机
    theme_cap = THEME_CAP[plan.theme_state]
    if plan.theme_total > theme_cap:
        results.append(GateResult("G-theme", Verdict.BLOCK,
                      f"主题仓 {plan.theme_total}% 超 {plan.theme_state.value} 档上限 {theme_cap}%"))
    else:
        results.append(GateResult("G-theme", Verdict.PASS,
                      f"主题仓 {plan.theme_total}% ≤ {theme_cap}%"))

    # 5) 单标的：仓位公式＋4% 高波动线
    for ticker, w in plan.single_positions.items():
        cap = _position_cap(plan.atr_pct.get(ticker))
        if w > cap:
            results.append(GateResult(f"G-single:{ticker}", Verdict.BLOCK,
                          f"{ticker} {w}% 超公式上限 {cap:.2f}%（ATR={plan.atr_pct.get(ticker, 'n/a')}）"))
        elif w > 4.0 and (plan.atr_pct.get(ticker) or 0) > 4.0:
            results.append(GateResult(f"G-single:{ticker}", Verdict.WARN,
                          f"{ticker} 高波动标的 {w}% 超 4% 线"))
        else:
            results.append(GateResult(f"G-single:{ticker}", Verdict.PASS, f"{w}% 在限内"))

    # 6) 板块集中度
    for sector, w in plan.sector_exposure.items():
        if w > CONCENTRATION["single_sector"]:
            results.append(GateResult(f"G-sector:{sector}", Verdict.BLOCK,
                          f"板块 {sector} {w}% 超 40% 单板块上限"))

    # 7) 港仓冻结
    if plan.hk_total > HK_FREEZE_LIMIT:
        results.append(GateResult("G-hk", Verdict.BLOCK,
                      f"港仓 {plan.hk_total}% 超冻结线 {HK_FREEZE_LIMIT}%（恒指未收复 MA20）"))
    else:
        results.append(GateResult("G-hk", Verdict.PASS, "港仓在冻结额度内"))

    return results


def worst_verdict(results) -> Verdict:
    order = {Verdict.PASS: 0, Verdict.WARN: 1, Verdict.BLOCK: 2}
    return max((r.verdict for r in results), key=lambda v: order[v])
