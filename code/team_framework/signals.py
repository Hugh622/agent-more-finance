# -*- coding: utf-8 -*-
"""十信号体系（AI 周期监测）＋评分仲裁规则——可运行。

十信号 v1 分四类：量价/利率/叙事/微观结构。每信号 +1/0/-1，
总分映射状态：≤3.5 WATCH → >4 ALERT → >6 LATE → ≥8 END（示例刻度）。
仲裁规则：半分摆动不翻转风险闸（0.5 分变动采信读数但状态闸待周五二次确认）。
"""
from dataclasses import dataclass
from enum import Enum


class Phase(str, Enum):
    WATCH = "WATCH"    # 🟢 中期后段
    ALERT = "ALERT"    # 🟡 减仓预备
    LATE = "LATE"      # 🟠 高危
    END = "END"        # 🔴 周期末段


@dataclass(frozen=True)
class Signal:
    code: str
    name: str
    category: str
    threshold: str


SIGNALS_V2: tuple = (
    Signal("S1", "200DMA 斜率（SOXX）", "量价", "600根重算，斜率≥+30%=加速段"),
    Signal("S2", "量能纯度", "量价", "涨跌量比、机构吸筹/派发分账"),
    Signal("S3", "G类循环融资 2.0", "微观", "循环融资规模与频次（v2 升级口径）"),
    Signal("S4", "卖水人景气确定性（v2 降级项）", "基本面", "卖水人从独立信号降为景气确认"),
    Signal("S5", "数据/价格签名分账（v2 新增）", "微观", "数据超预期但价格不涨=定价层断裂"),
    Signal("S6", "10Y 利率三闸", "利率", "5.05% 三日/5.30% 红线/80% 仓位线"),
    Signal("S7", "12月加息隐含概率", "利率", ">70% 踩线 / <60% 撤销"),
    Signal("S8", "信用利差月度走阔", "利率", "走阔 50bp/月→权益上限降一档"),
    Signal("S9", "叙事密度与融资事件", "叙事", "IPO 密集/ celebrity 基金=晚期签名"),
    Signal("S10", "宽度背离", "量价", "指数新高个股不新高=顶部签名"),
)


def score_to_phase(score: float) -> Phase:
    if score >= 8.0:
        return Phase.END
    if score > 6.0:
        return Phase.LATE
    if score > 4.0:
        return Phase.ALERT
    return Phase.WATCH


def phase_transition(prev: float, curr: float, current_state: Phase) -> dict:
    """带仲裁的状态转移：跨阈窄幅摆动（|Δ|≤1 分）不翻转状态闸。

    案例：9/28 L3 修正使十信号 3.5→4.5（Δ=1.0，恰好跨过 ALERT 阈 4.0），
    采信读数但 C17 状态闸按 ALERT 预执行；若后续滑回 ≤4.0 且周五例行
    评分确认，才允许回 WATCH。大幅跳变（|Δ|>1）则随读数直接翻转。
    """
    delta = round(curr - prev, 1)
    new_phase = score_to_phase(curr)
    if new_phase != current_state and abs(delta) <= 1.0:
        return {
            "phase": current_state,           # 闸不翻转
            "reading": new_phase,             # 读数采信
            "action": f"按 {new_phase.value} 预执行，周五例行评分二次确认后定档",
            "delta": delta,
        }
    return {"phase": new_phase, "reading": new_phase,
            "action": "状态闸随读数翻转", "delta": delta}
