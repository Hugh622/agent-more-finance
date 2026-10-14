# -*- coding: utf-8 -*-
"""E-P2-2 测试金字塔批次2 · 三地 corporate action 金样本回归。
金数据钉死于 tests/golden/corporate_action/ + GOLDEN_MANIFEST@1.1.0 (sha256 锚)。
覆盖: US 拆股 / HK 除息 / A股送转+派息 —— 检测、复权因子、复权连续性三断言。
"""
import csv
import hashlib
import json
import os

import pytest

GOLDEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden")
CA_DIR = os.path.join(GOLDEN_DIR, "corporate_action")


def _manifest():
    with open(os.path.join(GOLDEN_DIR, "GOLDEN_MANIFEST.json"), encoding="utf-8") as f:
        return json.load(f)


def _golden_entries():
    return [e for e in _manifest()["entries"] if e["file"].startswith("corporate_action/")]


def test_golden_sha256_pinned():
    """金样本本体防篡改: sha256 必须与钉档一致。"""
    for e in _golden_entries():
        p = os.path.join(GOLDEN_DIR, e["file"])
        assert os.path.exists(p), p
        assert hashlib.sha256(open(p, "rb").read()).hexdigest() == e["sha256"], e["file"]


def _load_series(fname):
    p = os.path.join(GOLDEN_DIR, fname)
    with open(p, encoding="utf-8") as f:
        rows = [(r["date"], float(r["raw_close"])) for r in csv.DictReader(f)]
    dates = [d for d, _ in rows]
    closes = [c for _, c in rows]
    assert dates == sorted(dates) and len(dates) >= 5
    return dates, closes


def _detect_ex_index(closes, threshold=0.2):
    """检测 corporate action ex 日: 最大跳变位置(|gap|>阈值)。除息类跳变小, 阈值逐案给。"""
    jumps = [(abs(closes[i] / closes[i - 1] - 1.0), i) for i in range(1, len(closes))]
    gap, idx = max(jumps)
    assert gap > threshold, f"未检测到 corporate action 跳变 max_gap={gap:.4f}"
    return idx  # ex 日索引(即 post_first 行)


@pytest.mark.parametrize("entry", _golden_entries(), ids=lambda e: os.path.basename(e["file"]))
def test_corporate_action_golden(entry):
    case = entry["case"]
    dates, closes = _load_series(entry["file"])
    ex = _detect_ex_index(closes, threshold=case.get("detect_threshold", 0.2))
    assert dates[ex] == case["ex_date"], f"检测 ex 日 {dates[ex]} != 钉档 {case['ex_date']}"
    pre_last, post_first = closes[ex - 1], closes[ex]
    kind, prm = case["kind"], case["params"]

    if kind == "split":
        factor = pre_last / post_first
        adj_pre = [c / factor for c in closes[:ex]]
        continuity = closes[ex] / adj_pre[-1] - 1.0
    elif kind == "div":
        div = prm["div_per_share"]
        factor = (pre_last - div) / pre_last
        continuity = post_first / (pre_last * factor) - 1.0
    elif kind == "split_div":
        ratio, div = prm["ratio"], prm["div_per_share"]
        factor = pre_last / post_first
        continuity = (post_first * (1.0 + ratio) + div) / pre_last - 1.0
    else:
        pytest.fail(f"未知 case kind: {kind}")

    assert abs(factor - case["expect_factor"]) <= case["factor_tol"], \
        f"复权因子 {factor:.6f} != 钉档 {case['expect_factor']:.6f}"
    assert abs(continuity - case["expect_continuity"]) <= case["continuity_tol"], \
        f"复权连续性 {continuity:.6f} != 钉档 {case['expect_continuity']:.6f}"
    assert all(c > 0 for c in closes), "价格序列含非正值"
