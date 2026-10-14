# -*- coding: utf-8 -*-
"""P2-3 B/S/G 分层 · 批次1测试: 血统链完整性
==========================================
语义: bronze 字节不可变 → silver 规整 → gold 视图, 逐层 lineage 记录
source_sha→output_sha; verify_lineage() 全链复算, 篡改任一层即断链报红。
"""
import os

import pytest

from scripts.data_layering import (
    promote_bronze, promote_gold, promote_silver, verify_lineage)

RATES_CSV = ("date,value,series_id,fetched_at,source\n"
             "2026-10-08,4.10,DFF,x,官方直连\n"
             "2026-10-09,4.11,DFF,x,官方直连\n")


@pytest.fixture()
def bsg(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "fedfunds.csv").write_text(RATES_CSV, encoding="utf-8")
    root = tmp_path / "bsg"
    root.mkdir()
    return str(src), str(root)


def _run_all(src, root):
    b = promote_bronze(src, root, "rates")
    s = promote_silver(src, root, "rates")
    g = promote_gold(root, "rates")
    return b, s, g


def test_full_chain_promotes_and_verifies(bsg):
    src, root = bsg
    b, s, g = _run_all(src, root)
    assert all(x["state"] == "promoted" for x in b + s + g), (b, s, g)
    rep = verify_lineage(root)
    assert rep["ok"], rep
    # gold 视图只含最新一行
    gv = os.path.join(root, "gold", "rates", "latest_view_rates.csv")
    with open(gv, encoding="utf-8") as f:
        lines = [l for l in f.read().splitlines() if l.strip()]
    assert len(lines) == 2 and "2026-10-09" in lines[1]


def test_bronze_idempotent_and_detects_source_change(bsg):
    src, root = bsg
    first = promote_bronze(src, root, "rates")
    second = promote_bronze(src, root, "rates")
    assert first[0]["state"] == "promoted" and second[0]["state"] == "unchanged"
    # 源变更 → 新 bronze 代生成, 血统更新
    with open(os.path.join(src, "fedfunds.csv"), "a", encoding="utf-8") as f:
        f.write("2026-10-10,4.12,DFF,x,官方直连\n")
    third = promote_bronze(src, root, "rates")
    assert third[0]["state"] == "promoted"
    assert verify_lineage(root)["ok"]


def test_tampering_any_layer_breaks_lineage(bsg):
    src, root = bsg
    _run_all(src, root)
    assert verify_lineage(root)["ok"]
    # 篡改 silver 产物 → 断链
    sp = os.path.join(root, "silver", "rates", "fedfunds.csv")
    with open(sp, "a", encoding="utf-8") as f:
        f.write("9999-99-99,0.0,FAKE,x,injected\n")
    rep = verify_lineage(root)
    assert not rep["ok"] and rep["layers"]["silver"]["broken"], rep
    # 篡改 bronze 副本 → 断链
    bp = os.path.join(root, "bronze", "rates", "fedfunds.csv")
    with open(bp, "a", encoding="utf-8") as f:
        f.write("tamper\n")
    rep2 = verify_lineage(root)
    assert not rep2["ok"] and rep2["layers"]["bronze"]["broken"], rep2


def test_gold_tamper_breaks_lineage(bsg):
    src, root = bsg
    _run_all(src, root)
    gp = os.path.join(root, "gold", "rates", "latest_view_rates.csv")
    with open(gp, "a", encoding="utf-8") as f:
        f.write("9999-99-99,0.0,FAKE,x\n")
    rep = verify_lineage(root)
    assert not rep["ok"] and rep["layers"]["gold"]["broken"], rep
