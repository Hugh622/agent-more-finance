# -*- coding: utf-8 -*-
"""
批次运行器：K线批次 / 实时快照 / 宏观通道。单只失败不中断，全部记录进 manifest。
"""
import json
import os
import time
from datetime import datetime

import pandas as pd

from . import tencent_api, storage, macro_feeds, degrade
from . import finnhub_api  # 美股主力源(2026-09-12接入): 健康检查不通过自动回腾讯, key只读config/finnhub.json
from .pools import (INDICES, A_POOL, HK_POOL, US_POOL, ETF_POOL, US_WATCH_POOL,
                    A_POOL_SPARES, HK_POOL_SPARES, US_POOL_SPARES)

DATA_ROOT = "/home/z/my-project/shared/market_data"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 管道根(manifest_v2 指纹用)

# K线落盘列序：标准 OHLC（策略师约定）；腾讯原始列序为 date,open,close,high,low（量化约定），见README对照说明
KLINE_OUT_COLS = ["date", "open", "high", "low", "close", "volume",
                  "amount_raw", "code", "market", "name",
                  "fetched_at", "source", "source_level"]

# 行情类落盘等级: 腾讯=授权行情服务商(第三方可靠来源档,行情类主通道), README §2 特注
LEVEL_QUOTES = storage.LEVEL_THIRD_PARTY
GRADE_QUOTES = "行情商(腾讯)-实测稳定"
GRADE_QUOTES_FH = "行情商(Finnhub)-美股免费档实时"


def _market_of(code: str) -> str:
    if code.startswith("sh") or code.startswith("sz"):
        return "CN"
    if code.startswith("hk"):
        return "HK"
    if code.startswith("us"):
        return "US"
    return "UNKNOWN"


def run_kline_batch(pools: dict, count: int = 250, data_root: str = DATA_ROOT,
                    sleep: float = 0.3, retries: int = 2) -> dict:
    """pools: {"A股": [(code,name),...], ...} → 逐只抓取日K并落盘 CSV。
    返回 manifest dict；任何单只失败只记录不中断。
    美股源策略(2026-09-12): Finnhub 主力源(健康检查通过时) → 腾讯通道兜底;
    其余市场(A/HK/指数)固定腾讯。manifest.source_mix 记录实际来源构成。
    """
    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    results = []
    total = sum(len(v) for v in pools.values())
    done = 0
    fh = None
    fh_health = finnhub_api.health_check()
    if fh_health.get("ok"):
        try:
            fh = finnhub_api.FinnhubClient()
        except Exception:
            fh = None
    source_mix = {"finnhub": 0, "tencent": 0}
    for pool_name, items in pools.items():
        for code, name in items:
            done += 1
            df, used = None, "tencent"
            if fh is not None and code.startswith("us"):
                sym = finnhub_api.us_symbol_from_code(code)
                if sym:
                    df = fh.fetch_kline(sym, count=count)
                    if df is not None and len(df):
                        used = "finnhub"
            if df is None or df.empty:  # 兜底: 腾讯通道(含美股后缀/端点降级链)
                df = tencent_api.fetch_kline(code, count=count, retries=retries)
                used = "tencent"
            rec = {"pool": pool_name, "code": code, "name": name, "status": "ok",
                   "source": used, "rows": 0, "last_date": None}
            source_mix[used] += 1
            if df is None or df.empty:
                rec["status"] = "fail"
            elif len(df) < 30:
                rec["status"] = "thin"  # 数据过薄(次新/长停牌),落盘但标记
                rec["rows"] = int(len(df))
            else:
                rec["rows"] = int(len(df))
            if df is not None and not df.empty:
                rec["last_date"] = str(df["date"].max().date())
                out = df.copy()
                out.columns = ["date", "open", "close", "high", "low", "volume", "amount_raw"]
                # 重排为标准OHLC列序
                out = out[["date", "open", "high", "low", "close", "volume", "amount_raw"]]
                out["code"] = code
                out["market"] = _market_of(code)
                out["name"] = name
                fname = code.lower().replace(".", "_") + ".csv"
                if used == "finnhub":
                    src, grade = storage.SOURCE_FINNHUB_KLINE.format(ts=run_ts), GRADE_QUOTES_FH
                else:
                    src, grade = storage.SOURCE_TENCENT_KLINE.format(ts=run_ts), GRADE_QUOTES
                storage.save_csv(out, os.path.join(data_root, "daily", fname),
                                 run_ts, src, LEVEL_QUOTES, grade)
                rec["path"] = os.path.join("daily", fname)  # v2 data_files 索引锚
            results.append(rec)
            time.sleep(sleep)
        print(f"[kline] {pool_name}: {done}/{total} done")
    return {"run_ts": run_ts, "type": "kline_batch", "count": count,
            "total": total, "ok": sum(1 for r in results if r["status"] == "ok"),
            "thin": sum(1 for r in results if r["status"] == "thin"),
            "fail": sum(1 for r in results if r["status"] == "fail"),
            "source_mix": source_mix,
            "finnhub_health": fh_health,
            "results": results}


def run_realtime_snapshot(data_root: str = DATA_ROOT, extra_codes: list = None) -> dict:
    """三地池+指数+AH对的实时快照 → realtime/。美股用无后缀实时码。"""
    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    codes = ([c for c, _ in INDICES] + [c for c, _ in A_POOL] +
             [c for c, _ in HK_POOL] + [c for c, _ in US_POOL] +
             [c for c, _ in US_WATCH_POOL] +
             [a for a, _, _ in macro_feeds.AH_PAIRS] +
             [h for _, h, _ in macro_feeds.AH_PAIRS])
    if extra_codes:
        codes += extra_codes
    # 美股实时码去后缀
    req = [tencent_api.us_realtime_code(c) for c in codes]
    quotes = tencent_api.fetch_realtime(req)
    rows = []
    for q in quotes:
        rows.append({k: q.get(k) for k in
                     ("key", "market", "name", "code", "price", "prev_close",
                      "open", "volume", "pct_chg", "high", "low", "amount_raw")})
    out = {"run_ts": run_ts, "type": "realtime_snapshot", "total": len(rows)}
    if rows:
        df = pd.DataFrame(rows)
        fname = "snapshot_" + datetime.now().strftime("%Y%m%d_%H%M") + ".csv"
        p = storage.save_csv(df, os.path.join(data_root, "realtime", fname),
                             run_ts, storage.SOURCE_TENCENT_RT.format(ts=run_ts),
                             LEVEL_QUOTES, GRADE_QUOTES)
        # 维护一份 latest 快照方便下游固定路径读取
        storage.save_csv(df, os.path.join(data_root, "realtime", "latest.csv"),
                         run_ts, storage.SOURCE_TENCENT_RT.format(ts=run_ts),
                         LEVEL_QUOTES, GRADE_QUOTES)
        out.update(paths=[p, os.path.join(data_root, "realtime", "latest.csv")])
    return out


def run_macro(data_root: str = DATA_ROOT) -> dict:
    """宏观P0通道（全链降级版）: 美债/FRED序列/中债/汇率/AH溢价/波动率/SEC/日历。
    每类数据按 降级链 命中层级落盘, manifest 记录 source_level 与降级轨迹。"""
    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    manifest = {"run_ts": run_ts, "type": "macro", "source_level_schema":
                {"官方直连": "L1(S级官网/联储系统/授权行情)", "第三方可靠来源": "L2(A/B级传媒核验或授权行情商)",
                 "检索兜底": "L3(检索录入/单源待核)"}}

    # --- 美债收益率: L1财政部 → L1 FRED → L2登记簿 ---
    payload, meta = degrade.run_chain(macro_feeds.us_yields_chain(), run_ts)
    paths = macro_feeds.publish_us_yields(payload, meta,
                                          os.path.join(data_root, "rates"), run_ts)
    manifest["us_yields"] = {
        "ok": bool(paths), "source_level": meta["level"], "grade": meta["grade"],
        "degraded": meta["degraded"], "attempts": meta["attempts"], "paths": paths,
        "fallback": None if paths else
        "L3检索兜底: 财政部+FRED+登记簿全失败, 通用助手/宏观按§2.1双源检索录入"}

    # --- FRED P0序列: 联邦基金利率 / VIX官方 / 信用利差 ---
    fred_results = {}
    for key, (sid, name) in macro_feeds.FRED_P0_SERIES.items():
        payload, meta = degrade.run_chain(macro_feeds.fred_series_chain(sid, name), run_ts)
        ok = payload is not None and isinstance(payload, pd.DataFrame) and len(payload)
        p = None
        if ok:
            p = storage.save_csv(payload.tail(30), os.path.join(data_root, "rates", f"{key}.csv"),
                                 run_ts, meta["source"], meta["level"], meta["grade"])
        fred_results[key] = {"name": name, "ok": bool(ok), "source_level": meta["level"],
                             "degraded": meta["degraded"], "path": p,
                             "fallback": None if ok else
                             "L2传媒检索录入(§2.1双源)→L3单源待核"}
    manifest["fred_p0"] = fred_results

    # --- 中债: L1 CFETS中国货币网 ---
    cn = macro_feeds.fetch_cn_yields()
    cn_paths = macro_feeds.cn_yield_p0_files(cn, os.path.join(data_root, "rates"), run_ts)
    manifest["cn_yields"] = {
        "ok": cn is not None, "source_level": storage.LEVEL_SEARCH if cn is None else storage.LEVEL_OFFICIAL,
        "grade": "S" if cn is not None else "L2录入", "paths": cn_paths,
        "fallback": None if cn is not None else
        "CFETS端点仅回日期元信息(待逆向v2) → L2检索录入: 宏观研究员每日CSV(§2.5)"}

    # --- 汇率矩阵 / AH溢价: 腾讯行情通道 ---
    manifest["fx"] = macro_feeds.run_fx(os.path.join(data_root, "fx"), run_ts)
    manifest["fx"]["source_level"] = LEVEL_QUOTES
    manifest["ah_premium"] = macro_feeds.run_ah_premium(os.path.join(data_root, "ah"), run_ts)
    manifest["ah_premium"]["source_level"] = LEVEL_QUOTES
    manifest["ah_premium"]["note"] = "自算口径; 恒指公司官方AH溢价指数→L2传媒转引(B+B)交叉"

    # --- 波动率: VHSI直连 + VIX代理ETF K线（VIX官方优先看 fred_p0.vix） ---
    vol_results = []
    from .pools import VOL_PROXY
    for code, name, kind in VOL_PROXY:
        df = tencent_api.fetch_kline(code, count=250, retries=2)
        rec = {"code": code, "name": name, "kind": kind,
               "status": "ok" if df is not None and len(df) >= 30 else "fail"}
        if rec["status"] == "ok":
            out = df[["date", "open", "close", "high", "low", "volume", "amount_raw"]].copy()
            out = out[["date", "open", "high", "low", "close", "volume", "amount_raw"]]
            out["code"] = code
            out["name"] = name
            fname = code.lower().replace(".", "_") + ".csv"
            storage.save_csv(out, os.path.join(data_root, "volatility", fname),
                             run_ts, storage.SOURCE_TENCENT_KLINE.format(ts=run_ts),
                             LEVEL_QUOTES, GRADE_QUOTES)
        vol_results.append(rec)
    manifest["volatility"] = {"results": vol_results,
                              "note": "VIX以L1官方VIXCLS为准; VXX/VIXY为期货ETF代理"}

    # --- SEC EDGAR 官方直连（美股池最近10-K/10-Q/8-K） ---
    manifest["sec_filings"] = run_sec_filings(os.path.join(data_root, "sec"), run_ts)

    # --- Finnhub 基本面通道（财报日历/经济日历/SEC交叉核验/池内基本面指标） ---
    manifest["finnhub_fundamentals"] = run_finnhub_fundamentals(data_root, run_ts)

    # --- 静态日历 + 南向/中间价 检索兜底模板 ---
    cal_paths = macro_feeds.publish_calendar(os.path.join(data_root, "calendar"), run_ts)
    manifest["calendar"] = {"paths": cal_paths, "source_level": storage.LEVEL_SEARCH,
                            "note": "制度性日历单源豁免(§SOP-7); 南向/中间价走L2传媒B+B核验"}
    return manifest


def run_finnhub_fundamentals(data_root: str, run_ts: str,
                             metric_symbols: int = 12) -> dict:
    """Finnhub 基本面/日历通道（免费档, 限频60/min 强制节流）:
      ① 财报日历(未来3天) → calendar/us_earnings_calendar.json
      ② 宏观经济日历 → calendar/us_economic_calendar.json
      ③ SEC filings 交叉核验(美股池前5只 10-K/10-Q) → sec/finnhub_filings_crosscheck.csv
         (EDGAR 仍为 L1 主源, 本项仅交叉核验, 不替代)
      ④ 美股池前N只基本面指标(P/E/P/B/ROE等) → fundamentals/us_metrics_latest.csv
    健康检查不通过(如本环境出口受阻)立即返回 skipped, 不占用配额不阻塞主流程。
    """
    out = {"source": storage.SOURCE_FINNHUB_API, "source_level": LEVEL_QUOTES,
           "grade": "行情商(Finnhub)"}
    h = finnhub_api.health_check()
    out["health"] = h
    if not h.get("ok"):
        out.update(ok=False, skipped=f"health_check不通过: {h.get('reason')}",
                   note="Finnhub 通道未启用, 相关数据由既有降级链覆盖(EDGAR/静态日历/L2检索)")
        return out
    cli = finnhub_api.FinnhubClient()
    items = []
    from datetime import timedelta as _td
    d_from = datetime.now().strftime("%Y-%m-%d")
    d_to = (datetime.now() + _td(days=3)).strftime("%Y-%m-%d")
    # ① 财报日历
    try:
        ec = cli.earnings_calendar(d_from, d_to)
        items.append(storage.save_json({"window": [d_from, d_to], "count": len(ec),
                                        "earningsCalendar": ec},
                                       os.path.join(data_root, "calendar",
                                                    "us_earnings_calendar.json"),
                                       run_ts, storage.SOURCE_FINNHUB_API.format(
                                           endpoint="calendar/earnings", ts=run_ts),
                                       LEVEL_QUOTES))
        out["earnings_calendar"] = len(ec)
    except Exception as e:
        out["earnings_calendar"] = f"fail: {str(e)[:100]}"
    # ② 经济日历
    try:
        econ = cli.economic_calendar()
        items.append(storage.save_json({"count": len(econ), "economicCalendar": econ[:200]},
                                       os.path.join(data_root, "calendar",
                                                    "us_economic_calendar.json"),
                                       run_ts, storage.SOURCE_FINNHUB_API.format(
                                           endpoint="calendar/economic", ts=run_ts),
                                       LEVEL_QUOTES))
        out["economic_calendar"] = len(econ)
    except Exception as e:
        out["economic_calendar"] = f"fail: {str(e)[:100]}"
    # ③ SEC filings 交叉核验（美股池前5只）
    try:
        want = [finnhub_api.us_symbol_from_code(c) for c, _ in US_POOL][:5]
        rows = []
        for s in want:
            if not s:
                continue
            try:
                for f in cli.filings(symbol=s, form="10-Q") + cli.filings(symbol=s, form="10-K"):
                    rows.append({"symbol": s, "form": f.get("form"),
                                 "filed": f.get("filedAt") or f.get("filed"),
                                 "report": f.get("reportUrl") or f.get("linkToFilingDetails"),
                                 "accession": f.get("accessionNumber")})
            except Exception:
                continue
        if rows:
            items.append(storage.save_csv(pd.DataFrame(rows),
                                          os.path.join(data_root, "sec",
                                                       "finnhub_filings_crosscheck.csv"),
                                          run_ts, storage.SOURCE_FINNHUB_API.format(
                                              endpoint="stock/filings", ts=run_ts),
                                          LEVEL_QUOTES, "行情商(Finnhub)"))
            out["filings_crosscheck"] = len(rows)
        else:
            out["filings_crosscheck"] = "empty"
        out["note_sec"] = "SEC L1 主源仍为 EDGAR atom API; 本项仅交叉核验(来源一致性比对)"
    except Exception as e:
        out["filings_crosscheck"] = f"fail: {str(e)[:100]}"
    # ④ 美股池基本面指标
    try:
        want = [finnhub_api.us_symbol_from_code(c) for c, _ in US_POOL][:metric_symbols]
        mrows = []
        for s in want:
            if not s:
                continue
            try:
                m = cli.metrics(s)
                basic = m.get("metric") or {}
                mrows.append({"symbol": s, "peTTM": basic.get("peTTM"),
                              "pbQuarterly": basic.get("pbQuarterly"),
                              "roeTTM": basic.get("roeTTM"),
                              "beta": basic.get("beta"),
                              "52wHigh": basic.get("52WeekHigh"),
                              "52wLow": basic.get("52WeekLow"),
                              "dividendYieldIndicated": basic.get("dividendYieldIndicatedAnnual")})
            except Exception:
                continue
        if mrows:
            items.append(storage.save_csv(pd.DataFrame(mrows),
                                          os.path.join(data_root, "fundamentals",
                                                       "us_metrics_latest.csv"),
                                          run_ts, storage.SOURCE_FINNHUB_API.format(
                                              endpoint="stock/metric", ts=run_ts),
                                          LEVEL_QUOTES, "行情商(Finnhub)"))
            out["metrics"] = len(mrows)
        else:
            out["metrics"] = "empty"
    except Exception as e:
        out["metrics"] = f"fail: {str(e)[:100]}"
    out.update(ok=bool(items), paths=items)
    return out


def run_sec_filings(outdir: str, run_ts: str, limit: int = 12) -> dict:
    """SEC EDGAR 官方直连: 美股池取前limit只, 抓最近 10-K/10-Q/8-K。
    CIK映射自动从SEC官方 company_tickers.json 构建并缓存 config/us_ciks.json。"""
    cache = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "config", "us_ciks.json")
    wanted = [c.replace("us", "").split(".")[0] for c, _ in US_POOL][:limit]
    cik_map = {}
    if os.path.exists(cache):
        try:
            with open(cache, encoding="utf-8") as f:
                cik_map = json.load(f)
        except Exception:
            cik_map = {}
    missing = [s for s in wanted if s not in cik_map]
    if missing:
        try:
            r = requests_get_json("https://www.sec.gov/files/company_tickers.json")
            for _, row in (r or {}).items():
                tkr, cik, title = row.get("ticker"), str(row.get("cik_str")), row.get("title")
                if tkr in wanted:
                    cik_map[tkr] = {"cik": cik, "name": title}
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            storage.save_json(cik_map, cache)
        except Exception:
            pass
    sub = {s: {"name_cn": "", "cik": (cik_map.get(s) or {}).get("cik")} for s in wanted}
    df = degrade.fetch_sec_filings(sub)
    out = {"ok": df is not None, "source_level": storage.LEVEL_OFFICIAL, "grade": "S",
           "symbols": len(wanted), "cik_resolved": sum(1 for v in sub.values() if v["cik"])}
    if df is not None and len(df):
        p = storage.save_csv(df, os.path.join(outdir, "us_recent_filings.csv"),
                             run_ts, storage.SOURCE_SEC_EDGAR.format(ts=run_ts),
                             storage.LEVEL_OFFICIAL, "S")
        out.update(paths=[p], filings=len(df))
    else:
        out["fallback"] = "L2传媒检索录入(§2.2: A+B双源, 回溯EDGAR原文链接)"
    return out


def requests_get_json(url: str):
    import requests
    r = requests.get(url, headers={"User-Agent": degrade.UA_COMPLIANT}, timeout=30)
    r.raise_for_status()
    return r.json()


def save_manifest(manifest: dict, data_root: str = DATA_ROOT) -> str:
    """E-P1-1: Manifest v2 原生落盘(新增产出 100% v2; 存量 33 份由量化腿补齐)。

    字段与只追加区语义见 manifest_v2.py; 文件名兼容 v1 模式
    run_<ts>_<type>.json(health_check glob 与冻结索引不断链), run_id=文件名 stem。
    """
    from market_fetcher import manifest_v2  # 延迟导入避免环
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"run_{ts}_{manifest.get('type','misc')}"
    p = os.path.join(data_root, "manifest", f"{stem}.json")
    m2 = manifest_v2.build_v2(manifest, data_root, BASE, run_id=stem)
    storage.save_json(m2, p)
    try:
        arc = manifest_v2.archive_run(m2, data_root)  # F-3 只追加区; 失败不阻断
    except Exception:
        arc = None
    print(f"[manifest] {manifest_v2.summary_for_log(m2)} archive={arc}")
    return p
