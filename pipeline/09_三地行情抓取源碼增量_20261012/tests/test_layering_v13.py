# -*- coding: utf-8 -*-
"""E-P2 批次2: data_layering v1.3 新格式单元测试
=================================================
覆盖: snapshot(UTC 归一/去重/可变指针排除) / filings / crosscheck / fundamentals /
      calendar+earnings JSON silver / gold 全量视图 / 血统完整性 / 幂等。
金准联动: tests/golden/ 批次2 三样本(sec_filings/us_metrics/fomc_meetings)。
"""
import json
import os

import pandas as pd
import pytest

from scripts import data_layering as dl

GOLDEN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "tests", "golden")


# ---------- helpers ----------
def _run(tmp_path, files, domain="t"):
    """在 tmp 域目录写入文件并跑完整 bronze→silver→gold。"""
    src = tmp_path / "src" / domain
    src.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (src / name).write_text(content, encoding="utf-8")
    root = str(tmp_path / "bsg")
    bronze = dl.promote_bronze(str(src), root, domain)
    silver = dl.promote_silver(str(src), root, domain)
    gold = dl.promote_gold(root, domain)
    return root, {"bronze": bronze, "silver": silver, "gold": gold}


def _state(actions, layer, needle=""):
    return [a for a in actions[layer] if needle in str(a["state"])]


# ---------- snapshot: UTC 归一 + 去重 + 数值化 ----------
def test_snapshot_utc_normalize_and_dedupe():
    df = pd.DataFrame({
        "key": ["sh000300", "sh000300", "usSPCX", "sh000300"],
        "market": ["CN", "CN", "US", "CN"],
        "code": ["000300", "000300", "SPCX", "000300"],
        "price": ["4510.16", "4510.16", "12.34", "4511.00"],
        "prev_close": ["4548.39", "4548.39", "12.10", "4548.39"],
        "fetched_at": ["2026-09-12 17:18:29", "2026-09-12 17:18:29",
                       "2026-09-12 17:18:29", "2026-09-12 18:00:00"],
    })
    s = dl._transform_snapshot(df)
    # naive 视为 UTC(全库约定), 全部带 +00:00
    assert (s["ts"].str.endswith("+00:00")).all()
    # 去重: key+ts 唯一
    assert not s.duplicated(subset=["key", "ts"]).any()
    assert len(s) == 3
    # 数值化
    assert pd.api.types.is_float_dtype(s["price"])
    # 排序: ts 升序
    assert list(s["ts"]) == sorted(s["ts"])


def test_snapshot_tz_aware_input_converts_to_utc():
    df = pd.DataFrame({
        "key": ["hk00700"], "code": ["00700"], "price": ["390.0"],
        "fetched_at": ["2026-09-12 17:18:29+08:00"],  # HKT → UTC 应为 09:18:29
    })
    s = dl._transform_snapshot(df)
    assert s.iloc[0]["ts"] == "2026-09-12T09:18:29+00:00"


# ---------- 可变指针排除（与冻结层判例一致）----------
def test_mutable_pointer_excluded_from_bronze_and_silver(tmp_path):
    files = {
        "latest.csv": "key,code,price,fetched_at\nsh000300,000300,1.0,2026-09-12 17:18:29\n",
        "snapshot_1.csv": "key,code,price,fetched_at\nsh000300,000300,2.0,2026-09-12 17:18:29\n",
    }
    root, acts = _run(tmp_path, files, domain="rt")
    assert len(_state(acts, "bronze", "skipped_mutable_pointer")) == 1
    assert len(_state(acts, "silver", "skipped_mutable_pointer")) == 1
    # bronze 只收 snapshot_1; silver 亦然
    assert os.path.isfile(os.path.join(root, "bronze", "rt", "snapshot_1.csv"))
    assert not os.path.exists(os.path.join(root, "bronze", "rt", "latest.csv"))
    gold = pd.read_csv(os.path.join(root, "gold", "rt", "latest_view_rt.csv"))
    assert len(gold) == 1  # 仅源自 snapshot_1


# ---------- filings / crosscheck ----------
def test_filings_sort_desc_and_dedupe():
    df = pd.DataFrame({
        "symbol": ["AAPL", "AAPL", "MSFT", "AAPL"],
        "form": ["10-Q", "10-Q", "10-K", "10-Q"],
        "filing_date": ["2026-07-31", "2026-07-31", "2026-07-30", "2026-04-30"],
        "accession": ["0000320193-26-000020", "0000320193-26-000020",
                      "0000950170-26-000001", "0000320193-26-000010"],
        "fetched_at": ["2026-10-10 13:27:05"] * 4,
    })
    s = dl._transform_filings(df)
    assert list(s["filing_date"]) == sorted(s["filing_date"], reverse=True)
    assert not s.duplicated(subset=["symbol", "form", "filing_date", "accession"]).any()
    assert len(s) == 3
    assert s.iloc[0]["as_of"] == "2026-10-10T13:27:05+00:00"


def test_crosscheck_tolerant_columns():
    df = pd.DataFrame({
        "symbol": ["AAPL", "AAPL", "MSFT"],
        "form": ["10-Q", "10-Q", "10-K"],
        "filed": ["", "", ""],
        "report": ["https://x/a.htm", "https://x/a.htm", "https://x/b.htm"],
        "fetched_at": ["2026-10-10 13:27:05"] * 3,
    })
    s = dl._transform_crosscheck(df)
    assert list(s["symbol"]) == ["AAPL", "MSFT"]  # report URL 去重后 AAPL 留 1 行
    assert (s["as_of"].str.endswith("+00:00")).all()


# ---------- fundamentals ----------
def test_fundamentals_meta_dropped_and_numeric():
    df = pd.DataFrame({
        "symbol": ["AAPL", "MSFT", "AAPL"],
        "peTTM": ["37.83", "31.20", "38.00"],
        "beta": ["1.106", "0.90", "1.11"],
        "junk": ["abc", "def", "ghi"],  # 非数值保留为 NaN 而非崩溃
        "fetched_at": ["2026-10-10 13:27:05"] * 3,
        "source": ["Finnhub"] * 3, "source_level": ["第三方"] * 3, "grade": ["行情商"] * 3,
    })
    s = dl._transform_fundamentals(df)
    assert "source" not in s.columns and "grade" not in s.columns
    assert "as_of" in s.columns and (s["as_of"] == "2026-10-10").all()
    assert pd.api.types.is_float_dtype(s["peTTM"])
    assert len(s) == 2  # symbol 去重
    assert list(s["symbol"]) == ["AAPL", "MSFT"]


# ---------- calendar / earnings JSON silver ----------
def test_calendar_json_normalize_and_template_skip(tmp_path):
    fomc = json.dumps({
        "calendar": "FOMC", "source": "federalreserve.gov",
        "meetings": [
            {"date_start": "2026-12-08", "date_end": "2026-12-09",
             "decision": "pending", "dot_plot_median": None},
            {"date_start": "2026-01-27", "date_end": "2026-01-28",
             "decision": "historical", "dot_plot_median": 4.50},
            {"date_start": "2026-01-27", "date_end": "2026-01-28",
             "decision": "dup", "dot_plot_median": None},
        ]}, ensure_ascii=False)
    template = json.dumps({"purpose": "t", "background": "b", "fields": [],
                           "records": [], "fetched_at": "x", "source": "s"},
                          ensure_ascii=False)
    root, acts = _run(tmp_path, {"fomc_calendar.json": fomc, "t.json": template},
                      domain="calendar")  # 全量视图按真实域名分发
    assert len(_state(acts, "silver", "skipped_template_no_data")) == 1
    s = pd.read_csv(os.path.join(root, "silver", "calendar", "fomc_calendar.csv"))
    assert list(s["date"]) == sorted(s["date"]) and len(s) == 2  # 去重+排序
    # gold: calendar 域 = 全量视图
    g = pd.read_csv(os.path.join(root, "gold", "calendar", "latest_view_calendar.csv"))
    assert len(g) == 2
    entry = [e for e in json.load(open(os.path.join(root, "lineage_gold.json")))
             ["entries"] if "latest_view_calendar.csv" in e["artifact"]]
    assert entry and entry[-1]["transform_id"] == "full_view_v1"


def test_earnings_json_normalize(tmp_path):
    earn = json.dumps({
        "window": ["2026-10-10", "2026-10-13"], "count": 2,
        "earningsCalendar": [
            {"symbol": "C", "date": "2026-10-13", "hour": "bmo", "quarter": 3,
             "year": 2026, "epsEstimate": 2.73, "epsActual": None,
             "revenueEstimate": 24202452747, "revenueActual": None},
            {"symbol": "AZZ", "date": "2026-10-13", "hour": "amc", "quarter": 2,
             "year": 2027, "epsEstimate": 1.87, "epsActual": None,
             "revenueEstimate": 468116143, "revenueActual": None},
            {"symbol": "C", "date": "2026-10-13", "hour": "bmo", "quarter": 3,
             "year": 2026, "epsEstimate": 2.73, "epsActual": None,
             "revenueEstimate": 24202452747, "revenueActual": None},
        ]}, ensure_ascii=False)
    root, acts = _run(tmp_path, {"us_earnings_calendar.json": earn}, domain="cal")
    s = pd.read_csv(os.path.join(root, "silver", "cal", "us_earnings_calendar.csv"))
    assert len(s) == 2 and list(s["symbol"]) == ["AZZ", "C"]  # 日期+符号排序


def test_broken_json_does_not_block_domain(tmp_path):
    root, acts = _run(tmp_path, {"bad.json": "{oops", "t.json": '{"a":1}'},
                      domain="cal")
    assert any("skipped_json" in str(a["state"]) for a in acts["silver"])


# ---------- 血统完整性 + 幂等（多格式混合域）----------
def test_lineage_ok_and_idempotent_across_new_formats(tmp_path):
    files = {
        "snapshot_1.csv": ("key,code,price,fetched_at\n"
                           "sh000300,000300,2.0,2026-09-12 17:18:29\n"
                           "usSPCX,SPCX,12.34,2026-09-12 17:18:29\n"),
        "us_recent_filings.csv": ("symbol,form,filing_date,accession,fetched_at\n"
                                  "AAPL,10-Q,2026-07-31,000-1,2026-10-10 13:27:05\n"
                                  "MSFT,10-K,2026-07-30,000-2,2026-10-10 13:27:05\n"),
        "us_metrics_latest.csv": ("symbol,peTTM,fetched_at\n"
                                  "AAPL,37.83,2026-10-10 13:27:05\n"),
        "fomc_calendar.json": ('{"meetings":[{"date_start":"2026-01-27",'
                               '"date_end":"2026-01-28","decision":"historical",'
                               '"dot_plot_median":4.5}]}'),
    }
    root, acts = _run(tmp_path, files, domain="mix")
    rep = dl.verify_lineage(root)
    assert rep["ok"], rep
    # 幂等: 同源重跑, bronze/silver 全 unchanged
    src = str(tmp_path / "src" / "mix")
    b2 = dl.promote_bronze(src, root, "mix")
    s2 = dl.promote_silver(src, root, "mix")
    assert all(a["state"] == "unchanged" for a in b2)
    assert all(a["state"] == "unchanged" for a in s2)


def test_lineage_tamper_detection_new_domain(tmp_path):
    files = {"us_metrics_latest.csv": "symbol,peTTM,fetched_at\nAAPL,37.83,2026-10-10 13:27:05\n"}
    root, acts = _run(tmp_path, files, domain="fd")
    # 篡改 silver 产物 → 链断
    with open(os.path.join(root, "silver", "fd", "us_metrics_latest.csv"), "a",
              encoding="utf-8") as f:
        f.write("TAMPER,1.0,2026-10-10 13:27:05\n")
    rep = dl.verify_lineage(root)
    assert not rep["ok"] and rep["layers"]["silver"]["broken"]


# ---------- 金准联动（批次2 三样本过变换后不变量）----------
def test_golden_sec_filings_transform_invariants():
    df = pd.read_csv(os.path.join(GOLDEN, "sec_filings_golden.csv"), encoding="utf-8-sig")
    s = dl._transform_filings(df)
    assert list(s["filing_date"]) == sorted(s["filing_date"], reverse=True)
    assert not s.duplicated(subset=["symbol", "form", "filing_date", "accession"]).any()


def test_golden_us_metrics_transform_invariants():
    df = pd.read_csv(os.path.join(GOLDEN, "us_metrics_golden.csv"), encoding="utf-8-sig")
    s = dl._transform_fundamentals(df)
    assert len(s) == df["symbol"].nunique()
    for c in ("peTTM", "pbQuarterly", "roeTTM", "beta"):
        assert pd.api.types.is_float_dtype(s[c])


def test_golden_fomc_matches_live_silver():
    """金准 fomc 会议表 == 实时源归一结果。宏观更新 pending 字段后本测红 → 按规程重钉。
    比较走 CSV 往返(与银层产物同构), 规避 dtype 噪音, 聚焦语义。"""
    golden = pd.read_csv(os.path.join(GOLDEN, "fomc_meetings_golden.csv"),
                         encoding="utf-8-sig")
    live_src = os.path.join(GOLDEN, "../../../market_data/calendar/fomc_calendar.json")
    if not os.path.isfile(os.path.abspath(live_src)):  # 环境缺数据时跳过
        pytest.skip("market_data/calendar 不在位")
    with open(os.path.abspath(live_src), encoding="utf-8") as f:
        tid, live = dl._json_transform("fomc_calendar.json", json.load(f))
    assert tid == "calendar_normalize_v1"
    live_csv = pd.read_csv(
        __import__("io").StringIO(live.to_csv(index=False)), encoding="utf-8")
    pd.testing.assert_frame_equal(
        live_csv.reset_index(drop=True), golden[list(live_csv.columns)].reset_index(drop=True))


# ---------- gold: filings 每符号最新 ----------
def test_gold_filings_latest_per_symbol(tmp_path):
    files = {"us_recent_filings.csv": (
        "symbol,form,filing_date,accession,fetched_at\n"
        "AAPL,10-Q,2026-07-31,000-2,2026-10-10 13:27:05\n"
        "AAPL,10-Q,2026-04-30,000-1,2026-10-10 13:27:05\n"
        "MSFT,10-K,2026-07-30,000-3,2026-10-10 13:27:05\n")}
    root, acts = _run(tmp_path, files, domain="sec")
    g = pd.read_csv(os.path.join(root, "gold", "sec", "latest_view_sec.csv"))
    assert sorted(g["symbol"]) == ["AAPL", "MSFT"]
    aapl = g[g["symbol"] == "AAPL"].iloc[0]
    assert aapl["filing_date"] == "2026-07-31"  # 取最新一期
