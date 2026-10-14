#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validation Gate 首轮红队 · 数据复算脚本
对象: Drawdown Policy v1.0 (shared/drawdown_policy_v1_20261011.html)
复算项:
  R1 代理组合(§1.2 口径: A50/B30/现金20) 单日收益 <= -2% 的频次(L1 日线触发过敏度)
  R2 周线 WDD(§1.1 口径: 周内最高水位锚) 分布 -> >=3% / >=5% 触发次数
  R3 跨周盲区实例: 峰值累计回撤 >=5% 但当周 WDD <5% 的周数(L2 主条款漏触发检验)
  R4 L3 月回撤同窗口读数(政策未定义月回撤口径, 以自然月峰值锚演示)
证据钉: 六个源 CSV 的 sha256 + 行数 + 末日期
输出: JSON 复算底稿
"""
import csv, hashlib, json, os, sys
from collections import OrderedDict

BASE = "/home/z/my-project/shared/market_data/daily"
FILES = OrderedDict([
    ("A_spy",  "usspy_am.csv"),
    ("A_qqq",  "usqqq_oq.csv"),
    ("A_gldm", "usgldm_am.csv"),
    ("B_spcx", "usspcx_oq.csv"),
    ("B_zeta", "uszeta_n.csv"),
    ("B_now",  "usnow_n.csv"),
])
WA, WB, WCASH = 0.50, 0.30, 0.20  # §1.2 权重

def load(path):
    closes = OrderedDict()
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            d = row["date"].strip()
            c = row["close"].strip()
            if not d or not c:
                continue
            closes[d] = float(c)
    return closes

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    series, evidence = {}, {}
    for key, fn in FILES.items():
        p = os.path.join(BASE, fn)
        closes = load(p)
        series[key] = closes
        rows = sum(1 for _ in open(p, encoding="utf-8-sig")) - 1
        evidence[key] = {"file": f"market_data/daily/{fn}", "sha256": sha256(p),
                         "rows": rows, "first": min(closes), "last": max(closes)}
    common = set.intersection(*[set(s) for s in series.values()])
    dates = sorted(common)
    if len(dates) < 30:
        print("insufficient overlap", file=sys.stderr); sys.exit(2)

    # 日收益 (按共同交易日排序, 相邻日收益)
    rets = OrderedDict()
    for i in range(1, len(dates)):
        d0, d1 = dates[i-1], dates[i]
        rA = sum(series[k][d1] / series[k][d0] - 1 for k in ("A_spy", "A_qqq", "A_gldm")) / 3.0
        rB = sum(series[k][d1] / series[k][d0] - 1 for k in ("B_spcx", "B_zeta", "B_now")) / 3.0
        rets[d1] = WA * rA + WB * rB + WCASH * 0.0

    # R1: 单日线
    daily = [(d, r) for d, r in rets.items()]
    n_days = len(daily)
    trig_2  = [(d, r) for d, r in daily if r <= -0.02]
    trig_15 = [(d, r) for d, r in daily if r <= -0.015]
    worst = min(daily, key=lambda x: x[1])

    # 代理 NAV 序列 (起点=1)
    nav = OrderedDict(); nav[dates[0]] = 1.0
    for d, r in daily:
        nav[d] = nav[[k for k in nav][-1]] * (1 + r)

    # R2: 周线 WDD (§1.1: 周内最高水位锚, 周五收盘)
    def week_key(d):  # ISO week
        from datetime import date
        y, m, dd = map(int, d.split("-"))
        iso = date(y, m, dd).isocalendar()
        return (iso[0], iso[1])
    weeks = OrderedDict()
    for d in dates:
        weeks.setdefault(week_key(d), []).append(d)
    weekly = []
    for wk, ds in weeks.items():
        hi = max(nav[d] for d in ds)
        fri = nav[ds[-1]]  # 最后一交易日(共同窗口内)
        wdd = (hi - fri) / hi
        weekly.append({"week": f"{wk[0]}-W{wk[1]:02d}", "days": len(ds),
                       "peak": round(hi, 6), "close": round(fri, 6), "wdd_pct": round(wdd*100, 2)})
    w3 = [w for w in weekly if w["wdd_pct"] >= 3.0 and w["days"] >= 3]
    w5 = [w for w in weekly if w["wdd_pct"] >= 5.0 and w["days"] >= 3]

    # R3: 跨周盲区 — 滚动峰值累计回撤 >=5% 但当周 WDD <5%
    running_peak = 0.0; blind = []
    for w in weekly:
        pass
    # 按周顺序累计: 峰值取含当周在内的历史最高 NAV, 收盘取当周最后收盘
    peak_so_far = 0.0
    for w in weekly:
        peak_so_far = max(peak_so_far, w["peak"])
        cum_dd = (peak_so_far - w["close"]) / peak_so_far * 100
        w["cum_dd_from_peak_pct"] = round(cum_dd, 2)
        if cum_dd >= 5.0 and w["wdd_pct"] < 5.0 and w["days"] >= 3:
            blind.append(w)

    # R4: 自然月回撤(月内峰值锚, 月末收盘) — 政策未定义口径, 演示用
    months = OrderedDict()
    for d in dates:
        months.setdefault(d[:7], []).append(d)
    monthly = []
    for m, ds in months.items():
        hi = max(nav[d] for d in ds); fri = nav[ds[-1]]
        monthly.append({"month": m, "mdd_pct": round((hi-fri)/hi*100, 2)})

    out = {
        "target": "shared/drawdown_policy_v1_20261011.html",
        "window": {"start": dates[0], "end": dates[-1], "common_days": len(dates),
                   "portfolio": "A=EW(SPY,QQQ,GLDM) x50% | B=EW(SPCX,ZETA,NOW) x30% | cash 20%"},
        "R1_daily_line": {"n_days": n_days, "trig_le_-2pct": [[d, round(r*100,2)] for d,r in trig_2],
                          "count_le_-2pct": len(trig_2), "count_le_-1.5pct": len(trig_15),
                          "worst": [worst[0], round(worst[1]*100,2)]},
        "R2_weekly_wdd": {"n_weeks_full": len([w for w in weekly if w["days"]>=3]),
                          "ge_3pct": w3, "ge_5pct": w5},
        "R3_crossweek_blind": {"n_blind_weeks": len(blind), "instances": blind},
        "R4_monthly_mdd_demo": monthly,
        "weekly_series": weekly,
        "evidence": evidence,
    }
    od = "/home/z/my-project/agents/6aa5076624bdc41e7983913b/reports"
    os.makedirs(od, exist_ok=True)
    op = os.path.join(od, "redteam_recalc_drawdown_20261012.json")
    with open(op, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    # 控制台摘要
    print(json.dumps({k: out[k] for k in ("window","R1_daily_line","R2_weekly_wdd","R3_crossweek_blind","R4_monthly_mdd_demo")},
                     ensure_ascii=False, indent=1))
    print("saved:", op)

if __name__ == "__main__":
    main()
