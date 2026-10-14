# -*- coding: utf-8 -*-
"""cost.py — 成本模型三地分参（EXP 种子『成本三地分参数见回测最低规格』的承载件）
口径（2026-10-11 冻结假设，报告须引用本文件 sha256）：
  US：佣金 0.10%/边（保守包络，覆盖 IBKR fixed+SEC/TAF）、印花 0、滑点 0.05%/边（OCP 成交假设）
  HK：佣金 0.05%/边、印花税 0.10%/边（双边，2023-11-17 减半后税率）、征费组 0.00765%/边
      （交易费 0.00565%＋结算 0.002%）、滑点 0.10%/边（价差较宽）
  CN：佣金 0.025%/边（万2.5）、印花税 0.05%（卖出单边，2023-08-28 减半后）、
      过户费 0.001%/边、滑点 0.05%/边
  5× 压力层＝全部摩擦 ×5（EXP 判决条件之『5x成本层』）
  成交假设＝OCP/CAS/收盘集合竞价 print（P1③ 规格锚定），滑点为对 print 的单边包络。
"""
COSTS = {
    "US": {"commission": 0.00100, "stamp": 0.0, "levy": 0.0, "slippage": 0.00050},
    "HK": {"commission": 0.00050, "stamp": 0.00100, "levy": 0.0000765, "slippage": 0.00100},
    "CN": {"commission": 0.00025, "stamp": 0.0, "levy": 0.00001, "slippage": 0.00050},  # stamp 卖出单边另计
}
CN_STAMP_SELL = 0.0005  # CN 印花税仅卖出单边
STRESS_MULTIPLE = 5.0


def side_cost(market, side, stress=1.0):
    """单边成本（占名义额比例）。side='buy'/'sell'。CN 印花税只在卖出边计。"""
    c = COSTS[market]
    m = float(stress)
    buy = (c["commission"] + c["stamp"] + c["levy"] + c["slippage"]) * m
    if side == "buy":
        return buy
    sell = (c["commission"] + c["levy"] + c["slippage"]) * m
    if market == "CN":
        sell += CN_STAMP_SELL * m
    else:
        sell += c["stamp"] * m
    return sell


def roundtrip_cost(market, stress=1.0):
    return side_cost(market, "buy", stress) + side_cost(market, "sell", stress)
