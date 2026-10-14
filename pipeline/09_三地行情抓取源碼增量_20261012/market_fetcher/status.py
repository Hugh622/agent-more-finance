# -*- coding: utf-8 -*-
"""数据状态枚举 v1 (P0-4 · 缺失状态枚举化)

评审指出: 状态散落为裸字符串("ok"/"thin"/"fail"/"missing"/"verified"/...),
无法穷举校验、易拼错、manifest 与覆盖矩阵口径漂移。

统一枚举, 成员值向后兼容既有 manifest / 覆盖矩阵 / pipeline_us24h.verify 口径,
全部管道写侧引用本枚举, 读侧可用 coerce()/try_coerce() 安全解析。
"""
from enum import Enum
from typing import Optional


class DataStatus(str, Enum):
    """单标的/单通道数据状态(值即 manifest 落盘字符串)。"""
    OK = "ok"                      # 数据完整可用
    THIN = "thin"                  # 数据过薄(次新/长停牌), 落盘但标记
    FAIL = "fail"                  # 拉取失败
    MISSING = "missing"            # 该日期/标的无数据(缺口, 待回填)
    DEGRADED = "degraded"          # 经降级链取得(非首选源)
    VERIFIED = "verified"          # 多源交叉校验通过(对齐 pipeline_us24h.verify)
    INSUFFICIENT = "insufficient"  # 校验源不足, 转人工(对齐 pipeline_us24h.verify)
    SKIPPED = "skipped"            # 计划内跳过(周日轮/维护窗)
    PENDING = "pending"            # 待补/待人工确认
    NA = "na"                      # 不适用(覆盖矩阵"该列对该行无意义", 非数据语义)

    @classmethod
    def try_coerce(cls, v) -> Optional["DataStatus"]:
        """裸字符串安全转枚举; 未知值返回 None(读侧自由文本兼容)。"""
        if isinstance(v, cls):
            return v
        try:
            return cls(str(v).strip().lower())
        except (ValueError, AttributeError):
            return None


class QualityStatus(str, Enum):
    """批次级质量状态(Manifest v2 quality_status 字段, P1-a 复用)。"""
    GOOD = "good"    # 首选源全覆盖, 无降级无缺口
    WARN = "warn"    # 有降级/薄数据/单源, 但批次完整
    BAD = "bad"      # 有失败/缺口, 需回填或人工


def batch_quality(ok: int, thin: int, fail: int, total: int) -> QualityStatus:
    """按 K线批次计数规则推导批次质量(与 runner 现行口径对齐)。"""
    if total <= 0:
        return QualityStatus.BAD
    if fail > 0:
        return QualityStatus.BAD
    if thin > 0 or ok < total:
        return QualityStatus.WARN
    return QualityStatus.GOOD
