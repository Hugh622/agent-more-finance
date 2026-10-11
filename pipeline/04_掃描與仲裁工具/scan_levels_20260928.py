#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全面市场扫描 · 第三方数据仲裁与关键位复核（全栈开发）
数据基准：market_data 存档 2026-09-25 收市（A股 9/24 中秋休市）+ 腾讯通道临时直拉 7 只观察标的。
角色：对量化模块/宏观模块/首席快照读数做独立第三方复核（第三源），非策略判断。
"""
import glob, json, sys, os
sys.path.insert(0, "/home/z/my-project/shared/全栈工具v1_三地行情抓取")
import pandas as pd
from market_fetcher import tencent_api

DAILY = "/home/z/my-project/shared/market_data/daily"
RATES = "/home/z/my-project/shared/market_data/rates"
out = {"asof": "2026-09-25收市(A股9/24)", "index_check": {}, "levels": {},
       "adhoc": {}, "breadth": {}, "rates": {}}

def load(f):
    p = os.path.join(DAILY, f)
    if not os.path.exists(p): return None
    df = pd.read_csv(p)
    df["date"] = df["date"].astype(str)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df.dropna(subset=["close"])

def stat(df, lines=()):
    if df is None or df.empty: return None
    last = df.iloc[-1]
    r = {"last_date": last["date"], "close": round(float(last["close"]), 2)}
    for n in (20, 50, 200):
        if len(df) >= n:
            r[f"ma{n}"] = round(float(df["close"].rolling(n).mean().iloc[-1]), 2)
    for name, lv in lines:
        if lv and "close" in r:
            r[name] = round((r["close"] / lv - 1) * 100, 2)
    return r

# ---- 指数三源仲裁 ----
out["index_check"]["SPX"]  = stat(load("usinx.csv"))
out["index_check"]["IXIC"] = stat(load("usixic.csv"))
out["index_check"]["DJI"]  = stat(load("usdji.csv"))
out["index_check"]["HSI"]  = stat(load("hkhsi.csv"))
out["index_check"]["SSE"]  = stat(load("sh000001.csv"))
out["index_check"]["SZCOMP"] = stat(load("sz399001.csv"))
out["index_check"]["SPY"]  = stat(load("usspy_am.csv"), [("vs_7488_pct", 748.8)])
out["index_check"]["SPCX"] = stat(load("usspcx_oq.csv"),
    [("vs_145_pct", 145.0), ("vs_14993_pct", 149.93), ("vs_15687_pct", 156.87)])

# ---- 持仓关键位（池内文件） ----
out["levels"]["MU"]   = stat(load("usmu_oq.csv"),  [("vs_9416_pct", 941.6), ("vs_6611_pct", 661.1)])
out["levels"]["NVDA"] = stat(load("usnvda_oq.csv"))
out["levels"]["TSM"]  = stat(load("ustsm_n.csv"))

# ---- 临时直拉（不在存档池，仅复核用） ----
for code, name, lines in [("usCPER.AM", "CPER", [("vs_3766_pct", 37.66)]),
                          ("usHPE.N", "HPE",   [("vs_6215_pct", 62.15)]),
                          ("usZETA.N", "ZETA", [("vs_297_pct", 29.7)]),
                          ("usGLDM.AM", "GLDM",[("vs_8509_pct", 85.09)]),
                          ("usSOXX.OQ", "SOXX", ()),
                          ("usGDX.AM", "GDX", ()),
                          ("usGLD.AM", "GLD", ())]:
    df = tencent_api.fetch_kline(code, count=250)
    if df is None:
        out["adhoc"][name] = "FAIL"
        continue
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"])
    last = df.iloc[-1]
    r = {"code": code, "last_date": str(last["date"]), "close": round(float(last["close"]), 2)}
    for n in (20, 50, 200):
        if len(df) >= n:
            r[f"ma{n}"] = round(float(df["close"].rolling(n).mean().iloc[-1]), 2)
    if name == "SOXX" and len(df) >= 126:  # 200DMA 六个月斜率（量化L3口径复核）
        dma200_series = df["close"].rolling(200).mean().dropna()
        if len(dma200_series) >= 126:
            r["dma200_6m_slope_pct"] = round((dma200_series.iloc[-1] / dma200_series.iloc[-126] - 1) * 100, 1)
    for nm, lv in lines:
        r[nm] = round((r["close"] / lv - 1) * 100, 2)
    if name == "GDX" or name == "GLD":
        out["adhoc"].setdefault("_raw", {})[name] = float(last["close"])
    out["adhoc"][name] = r

g = out["adhoc"].get("_raw", {})
if g.get("GDX") and g.get("GLD"):
    out["adhoc"]["gdx_gld_ratio"] = round(g["GDX"] / g["GLD"], 4)
out["adhoc"].pop("_raw", None)

# ---- 市场宽度（存档池） ----
by_mkt = {"A": {"n":0,"above_ma20":0,"above_ma50":0,"macd_above":0,"golden_now":0,"dead_now":0},
          "HK": {"n":0,"above_ma20":0,"above_ma50":0,"macd_above":0,"golden_now":0,"dead_now":0},
          "US": {"n":0,"above_ma20":0,"above_ma50":0,"macd_above":0,"golden_now":0,"dead_now":0}}
for f in glob.glob(os.path.join(DAILY, "*.csv")):
    base = os.path.basename(f)
    if base.startswith(("us", "hk", "sh", "sz")) is False: continue
    if base.startswith("sh"): mkt = "A"
    elif base.startswith("sz"): mkt = "A"
    elif base.startswith("hk"): mkt = "HK"
    else: mkt = "US"
    try: df = load(base)
    except Exception: continue
    if df is None or len(df) < 60: continue
    st = by_mkt[mkt]; st["n"] += 1
    c = df["close"]
    m20 = c.rolling(20).mean().iloc[-1]; m50 = c.rolling(50).mean().iloc[-1]
    if c.iloc[-1] > m20: st["above_ma20"] += 1
    if c.iloc[-1] > m50: st["above_ma50"] += 1
    ema12 = c.ewm(span=12, adjust=False).mean(); ema26 = c.ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26; dea = dif.ewm(span=9, adjust=False).mean()
    prev, now = dif.iloc[-2] - dea.iloc[-2], dif.iloc[-1] - dea.iloc[-1]
    if now > 0: st["macd_above"] += 1
    if now > 0 and prev <= 0: st["golden_now"] += 1
    if now < 0 and prev >= 0: st["dead_now"] += 1
for mkt, st in by_mkt.items():
    n = st.pop("n")
    if n:
        st["pct_above_ma20"] = round(st.pop("above_ma20") / n * 100, 1)
        st["pct_above_ma50"] = round(st.pop("above_ma50") / n * 100, 1)
        st["sample_n"] = n
out["breadth"] = by_mkt

# ---- 利率波动率 ----
for f, label in [("us10y.csv", "us10y"), ("us02y.csv", "us02y"), ("vix.csv", "vix"),
                 ("fedfunds.csv", "fedfunds"), ("credit_spread_hy.csv", "hy_spread")]:
    p = os.path.join(RATES, f)
    if not os.path.exists(p): continue
    df = pd.read_csv(p)
    row = df.iloc[-1]
    val = None
    for c in df.columns[1:4]:
        try:
            val = float(row[c]); break
        except (ValueError, TypeError):
            continue
    out["rates"][label] = {"date": str(row[df.columns[0]]), "value": val}

print(json.dumps(out, ensure_ascii=False, indent=1))
