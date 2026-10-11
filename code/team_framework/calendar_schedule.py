# -*- coding: utf-8 -*-
"""事件日历与待命节点引擎——数据驱动，可查询最近节点。

节点分两类：
  MARKET：市场事件（CPI/FOMC/财报/选举）——触发裁决点
  INTERNAL：内部节奏（周检/滑动复核/台账收编/G 验收）
"""
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class Node:
    day: date
    kind: str          # MARKET / INTERNAL
    event: str
    decision_point: str = ""   # 该节点要裁决什么


# ---------------------------------------------------------------------------
# 节点表（2026Q4 主干；随事件滚动修订）
# ---------------------------------------------------------------------------
NODES: tuple = (
    Node(date(2026, 10, 12), "INTERNAL", "W0 纸面推演起跑"),
    Node(date(2026, 10, 13), "INTERNAL", "周检挂单确认；601985 结案回执"),
    Node(date(2026, 10, 14), "MARKET", "美国 CPI",
         "金链第一裁决：GLDM 85.29 双确认＋12月加息概率<60%=解禁；10Y 三闸重估"),
    Node(date(2026, 10, 15), "MARKET", "台积电法说",
         "AI capex 传导验证；MU 预授信第二触发源"),
    Node(date(2026, 10, 16), "INTERNAL", "首次周五周检＋MA 滑动复核＋台账 v2 收编"),
    Node(date(2026, 10, 23), "INTERNAL", "奇安信升格验证窗截止（31.88 放量确认线）"),
    Node(date(2026, 10, 27), "MARKET", "FOMC 第一日＋四财报扎堆", "只减不加 72h"),
    Node(date(2026, 10, 29), "MARKET", "FOMC 结束", "加息/不加息情景闸执行"),
    Node(date(2026, 11, 3), "MARKET", "美国中期选举", "Q4 部署版触发"),
    Node(date(2026, 11, 6), "INTERNAL", "G1 模拟条款首验（C7/C9/C12）"),
    Node(date(2026, 11, 10), "MARKET", "中美休战到期节点（延至 2027/1/10）"),
    Node(date(2026, 11, 20), "MARKET", "BMNR 10-K", "P/NAV 与稀释率重审"),
    Node(date(2026, 12, 6), "MARKET", "美股 23x5 夜盘新制生效",
         "T-0 过渡校准；夜盘仅限价＋LOP/CE 保护"),
    Node(date(2026, 12, 18), "INTERNAL", "G2 中期报告（五闸验收）"),
    Node(date(2027, 1, 6), "INTERNAL", "G3 N1 检讨（23x5 新制）"),
    Node(date(2027, 3, 14), "MARKET", "夏令切换＝23x5 满血联动日",
         "夜盘 HKT 09:00-16:00 全覆盖港A；监控钟改 09:00/04:00"),
)


def next_nodes(today: Optional[date] = None, n: int = 5) -> tuple:
    """返回今天（含）之后的最近 n 个节点。"""
    ref = today or date(2026, 10, 11)
    return tuple(sorted([x for x in NODES if x.day >= ref], key=lambda x: x.day)[:n])


def pending_decisions(today: Optional[date] = None) -> tuple:
    """未来 30 天内带裁决点的节点。"""
    ref = today or date(2026, 10, 11)
    from datetime import timedelta
    horizon = ref + timedelta(days=30)
    return tuple(x for x in NODES if ref <= x.day <= horizon and x.decision_point)
