# -*- coding: utf-8 -*-
"""E-P2 批次2 · property-based 不变量 P7/P8（承接 test_property_based.py P1–P6）
=====================================================================
原文件属主为批次1 会话(root)不便追加, 本模块按批次拆分。
种子=20261012 与主文件同源; 修改种子视同金样本变更, 须走 supersedes。
"""
import random

import pandas as pd

from scripts import data_layering as dl

SEED = 20261012
N_CASES = 25


def _rng():
    return random.Random(SEED)


# ---------- P7: snapshot 变换不变量(UTC 归一/去重/排序/确定性) ----------
def test_p7_snapshot_utc_invariants():
    rng = _rng()
    keys = ["sh000300", "usSPCX", "hk00700", "usNOW", "usZETA"]
    for i in range(N_CASES):
        n = rng.randint(1, 12)
        rows = []
        for _ in range(n):
            k = rng.choice(keys)
            h, m, sec = rng.randrange(24), rng.randrange(60), rng.randrange(60)
            rows.append((k, f"{rng.uniform(1, 500):.2f}",
                         f"2026-09-{rng.randrange(1, 29):02d} {h:02d}:{m:02d}:{sec:02d}"))
        df = pd.DataFrame(rows, columns=["key", "price", "fetched_at"])
        df["code"] = df["key"].str.replace(r"^us|^sh|^hk", "", regex=True)
        s = dl._transform_snapshot(df)
        # 不变量: 输出≤输入 / (key,ts) 唯一 / ts 全 UTC / ts 升序 / price 数值
        assert len(s) <= n
        assert not s.duplicated(subset=["key", "ts"]).any()
        assert s["ts"].str.endswith("+00:00").all()
        assert list(s["ts"]) == sorted(s["ts"])
        assert pd.api.types.is_float_dtype(s["price"])
        # 同输入重复变换逐位一致(确定性)
        pd.testing.assert_frame_equal(s, dl._transform_snapshot(df))


# ---------- P8: filings 变换不变量(去重/降序/身份无损) ----------
def test_p8_filings_dedupe_and_order_invariants():
    rng = _rng()
    syms = ["AAPL", "MSFT", "NVDA", "C", "AZZ"]
    for i in range(N_CASES):
        n = rng.randint(1, 15)
        rows = []
        for _ in range(n):
            sym = rng.choice(syms)
            d = f"2026-{rng.randrange(1, 13):02d}-{rng.randrange(1, 29):02d}"
            rows.append((sym, rng.choice(["10-Q", "10-K", "8-K"]), d,
                         f"000-{rng.randrange(1000, 9999)}", "2026-10-10 13:27:05"))
        df = pd.DataFrame(rows, columns=["symbol", "form", "filing_date",
                                         "accession", "fetched_at"])
        s = dl._transform_filings(df)
        assert len(s) <= n
        assert not s.duplicated(
            subset=["symbol", "form", "filing_date", "accession"]).any()
        assert list(s["filing_date"]) == sorted(s["filing_date"], reverse=True)
        # 去重只按身份键, 不同身份的行零丢失
        ident = {tuple(r) for r in df[["symbol", "form", "filing_date", "accession"]]
                 .drop_duplicates().itertuples(index=False)}
        got = {tuple(r) for r in s[["symbol", "form", "filing_date", "accession"]]
               .itertuples(index=False)}
        assert got == ident
