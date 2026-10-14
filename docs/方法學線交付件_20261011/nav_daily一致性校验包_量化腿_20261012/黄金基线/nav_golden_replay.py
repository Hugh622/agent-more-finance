#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nav_daily 一致性校验方案 · 黄金基线独立重放（量化腿独立实现，非运行红队脚本）
口径（首席裁决书 D3/D4 官方化 + 红队同款脚本口径）：
  A层=EW(SPY,QQQ,GLDM)×50%  B层=EW(SPCX,ZETA,NOW)×30%  现金20%（日收益记 0）
  未复权 close、共同交易日交集、日再平衡、NAV 起点 1.0
输出：逐日 NAV 黄金序列（供方案 fixture）＋关键统计量（对照红队 JSON 钉档值）
"""
import csv, json, os, hashlib
from datetime import date
from collections import OrderedDict

BASE = "/home/z/my-project/shared/market_data/daily"
FILES = OrderedDict([
    ("A_spy", "usspy_am.csv"), ("A_qqq", "usqqq_oq.csv"), ("A_gldm", "usgldm_am.csv"),
    ("B_spcx", "usspcx_oq.csv"), ("B_zeta", "uszeta_n.csv"), ("B_now", "usnow_n.csv"),
])
WA, WB, WC = 0.50, 0.30, 0.20

def load(p):
    out = OrderedDict()
    with open(p, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            d, c = row["date"].strip(), row["close"].strip()
            if d and c:
                out[d] = float(c)
    return out

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(65536), b""):
            h.update(ch)
    return h.hexdigest()

series, ev = {}, {}
for k, fn in FILES.items():
    p = os.path.join(BASE, fn)
    series[k] = load(p)
    ev[fn] = {"sha256": sha256(p), "rows": len(series[k]),
              "first": min(series[k]), "last": max(series[k])}

dates = sorted(set.intersection(*[set(s) for s in series.values()]))
nav = OrderedDict(); nav[dates[0]] = 1.0
rets = {}
for i in range(1, len(dates)):
    d0, d1 = dates[i-1], dates[i]
    rA = sum(series[k][d1]/series[k][d0]-1 for k in ("A_spy","A_qqq","A_gldm"))/3.0
    rB = sum(series[k][d1]/series[k][d0]-1 for k in ("B_spcx","B_zeta","B_now"))/3.0
    r = WA*rA + WB*rB + WC*0.0
    rets[d1] = r
    nav[d1] = nav[dates[i-1]] * (1+r)

def wk(d):
    y,m,dd = map(int, d.split("-")); iso = date(y,m,dd).isocalendar(); return (iso[0],iso[1])
weeks = OrderedDict()
for d in dates:
    weeks.setdefault(wk(d), []).append(d)
weekly = []
for w, ds in weeks.items():
    hi = max(nav[d] for d in ds); fri = nav[ds[-1]]
    weekly.append({"week": f"{w[0]}-W{w[1]:02d}", "days": len(ds), "close": fri,
                   "wdd_pct": round((hi-fri)/hi*100, 2)})
full = [w for w in weekly if w["days"] >= 3]
wdd_max = max(full, key=lambda w: w["wdd_pct"])
peak, cum = 0.0, []
for w in weekly:
    # v1.1 D1 口径：峰＝历史最高水位（含周内高点），测量锚＝当周五收盘
    wk_days = weeks[tuple(int(x) for x in w["week"].replace("-W", "-").split("-"))]
    w_peak = max(nav[d] for d in wk_days)
    peak = max(peak, w_peak)
    cum.append({"week": w["week"], "days": w["days"],
                "cum_dd_pct": round((peak-w["close"])/peak*100, 2) if peak else 0.0})
cum_full = [c for c in cum if c["days"] >= 3]
cum_max = max(cum_full, key=lambda c: c["cum_dd_pct"])
ge5 = [c["week"] for c in cum_full if c["cum_dd_pct"] >= 5.0]
d2 = [(d, round(r*100,2)) for d,r in rets.items() if r <= -0.02]
months = OrderedDict()
for d in dates:
    months.setdefault(d[:7], []).append(d)
mdd = {}
for m, ds in months.items():
    hi = max(nav[d] for d in ds); mdd[m] = round((hi-nav[ds[-1]])/hi*100, 2)

out = {
    "window": {"start": dates[0], "end": dates[-1], "common_days": len(dates)},
    "evidence": ev,
    "stats": {
        "n_weeks_full": len(full),
        "wdd_max": wdd_max, "wdd_ge3_weeks": [w["week"] for w in full if w["wdd_pct"] >= 3.0],
        "cum_dd_max": cum_max, "cum_ge5_weeks": ge5,
        "daily_le_minus2": d2, "n_daily": len(rets),
        "monthly_mdd": mdd,
        "nav_last": round(nav[dates[-1]], 6),
    },
}
odir = "/home/z/my-project/agents/6a852d5ae176869046aa8e8d/recheck_20261012"
with open(os.path.join(odir, "nav_golden_replay.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
with open(os.path.join(odir, "nav_golden_series.json"), "w", encoding="utf-8") as f:
    json.dump({d: round(v, 10) for d, v in nav.items()}, f, ensure_ascii=False, indent=0)
print(json.dumps(out["stats"], ensure_ascii=False, indent=1))
print("window:", out["window"])
