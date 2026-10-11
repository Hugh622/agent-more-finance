# -*- coding: utf-8 -*-
"""仓位与风控公式库（波动率目标制）——可运行。

核心公式：
  单标的目标仓位 = min( 年化波动目标 12% ÷ (ATR% × 3), 15% )
  起手单元     = 家庭月收入 × 5%（收入锚定制，三档假设 60K/80K/100K）
  最大亏损     = 投入 × 止损距离%
"""
from dataclasses import dataclass
from typing import Optional

VOL_TARGET_ANNUAL: float = 12.0      # 年化波动目标 %
ATR_MULTIPLIER: float = 3.0
SINGLE_CAP: float = 15.0             # 单标的上限 %
HIGH_VOL_SINGLE_CAP: float = 4.0     # 高波动标的单仓上限 %
STARTING_UNIT_PCT: float = 5.0       # 起手单元 = 家庭月收入 5%
THEME_MONTHLY_CAP: float = 10.0      # 主题仓首月 ≤ 月收入 10%
TOTAL_MONTHLY_CAP: float = 30.0      # 合计 ≤ 月收入 30%


@dataclass(frozen=True)
class IncomeScenario:
    """收入锚定三档假设（显眼标注：以下均为假设值，非真实收入）。"""
    label: str
    monthly_income: float  # HKD（假设值）

    @property
    def starting_unit(self) -> float:
        return self.monthly_income * STARTING_UNIT_PCT / 100.0

    @property
    def theme_cap(self) -> float:
        return self.monthly_income * THEME_MONTHLY_CAP / 100.0


INCOME_SCENARIOS: tuple = (
    IncomeScenario("保守假设", 60_000.0),
    IncomeScenario("基准假设", 80_000.0),
    IncomeScenario("宽松假设", 100_000.0),
)


def position_size(annual_vol_pct: Optional[float]) -> float:
    """波动率目标制仓位（%）。

    annual_vol_pct = 标的年化波动率（百分比单位，如 45 表示 45%）。
    仓位% = min( 12% ÷ (年化波动率 × 3), 15% )
    例：年化 45% → 12/(0.45×3) = 8.89%；年化 20% → 20% 触顶 → 15%。
    """
    if not annual_vol_pct or annual_vol_pct <= 0:
        raise ValueError("年化波动率必须为正数；缺数据时不得套用公式（边界：答不出不落场）")
    return round(min(VOL_TARGET_ANNUAL / ((annual_vol_pct / 100.0) * ATR_MULTIPLIER), SINGLE_CAP), 2)


def max_loss(invested: float, stop_distance_pct: float) -> float:
    """最大亏损 = 投入金额 × 止损距离%。"""
    return round(invested * stop_distance_pct / 100.0, 2)


def scale_out_plan(entry: float, stop: float, t1: float, t2: float, t3: float) -> dict:
    """阶梯止盈骨架（C20：止盈按首阻力位定价；scale out 平半＋移损至成本）。"""
    assert stop < entry < t1 < t2 < t3, "点位结构必须 stop < entry < T1 < T2 < T3"
    return {
        "T1（首阻力）": {"price": t1, "action": "平 1/2，剩余止损上移至成本"},
        "T2": {"price": t2, "action": "再平 1/4，止损上移至 T1"},
        "T3（趋势逆转位）": {"price": t3, "action": "清仓或留长线评估格"},
        "止损": {"price": stop, "action": "收盘确认制；盘中击穿只披露（升级条款除外）"},
    }


def risk_reward(entry: float, stop: float, target: float) -> float:
    """盈亏比 = (目标-入场)/(入场-止损)。"""
    risk = entry - stop
    if risk <= 0:
        raise ValueError("止损必须低于入场价")
    return round((target - entry) / risk, 2)
