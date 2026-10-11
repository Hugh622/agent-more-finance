# -*- coding: utf-8 -*-
"""复盘评分框架：分层断言与同向验证机制——可运行结构。

复盘方法论（8月/9月/早期三轮沉淀）：
  分三层独立计分：框架层（方向判断）/ 规则层（执行线与风控）/ 介入层（实际入场）。
  已验证规律：框架层 80-83% vs 介入层 2/9-36% → 体系「啱方向、錯介入」，
  据此 9/24 双轮同向后把 C20-C22 升格 v1.3。
"""
from dataclasses import dataclass, field


@dataclass
class ReviewItem:
    """单条预判的可判定项。"""
    item: str
    layer: str          # framework / rule / entry
    verdict: str        # hit / miss / split / pending
    note: str = ""


@dataclass
class LayerScore:
    layer: str
    hits: int = 0
    misses: int = 0
    splits: int = 0

    @property
    def total(self) -> int:
        return self.hits + self.misses + self.splits

    @property
    def accuracy(self) -> float:
        if self.total == 0:
            return 0.0
        return round((self.hits + 0.5 * self.splits) / self.total * 100, 1)


def score_reviews(items) -> dict:
    """按层汇总命中率。"""
    layers = {"framework": LayerScore("框架层"),
              "rule": LayerScore("规则层"),
              "entry": LayerScore("介入层")}
    for it in items:
        bucket = layers[it.layer]
        if it.verdict == "hit":
            bucket.hits += 1
        elif it.verdict == "miss":
            bucket.misses += 1
        elif it.verdict == "split":
            bucket.splits += 1
    return layers


def cross_round_rule(r1_hits: str, r2_hits: str) -> str:
    """改判升格规则：修法建议需两轮复盘同向才写入正式条款。"""
    if r1_hits == r2_hits and r1_hits != "divergent":
        return f"两轮同向（{r1_hits}）→ 升格写入下一版本框架"
    return "分歧或单轮 → 记账观察，不升格"


# ---------------------------------------------------------------------------
# 复盘机制定版（缺口补全终局收口）
# ---------------------------------------------------------------------------
REVIEW_MECHANISM: dict = {
    "W0": "纸面推演起跑（10/12）",
    "周检": "每周五（首检 10/16 覆盖 CPI+台积电法说）",
    "G1": "11/6-7 首验（C7/C9/C12 模拟条款首验）",
    "G2": "12/18-20 中期报告（D-2 观察到期对齐）",
    "G3": "2027/1 N1 检讨",
    "五闸验收": [
        "触发正确率 ≥65%（样本≥10）",
        "纪律遵守 ≥95%",
        "滑点偏差 ≤0.5% 占比 ≥80%",
        "规则零失效",
        "覆盖 100%",
    ],
    "实盘准入": "G2 全过＋用户明示批准 → 教学仓（单笔≤1 起手单元/合计≤3/限价单/行为标注）",
    "回炉": "单闸不达标延 4 周；连续两轮回退 v1.2；工程性误判暂停审计",
}
