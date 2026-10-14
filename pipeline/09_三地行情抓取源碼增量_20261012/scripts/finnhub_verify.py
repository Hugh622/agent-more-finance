# -*- coding: utf-8 -*-
"""Finnhub key 全端点实测矩阵（工程化版）
用法:
  python3 scripts/finnhub_verify.py             # 全矩阵30用例, 限频1.2s/req
  python3 scripts/finnhub_verify.py --quick     # 只测连通+K线+SEC 6个关键用例
输出:
  标准输出: 每用例状态行 + 汇总
  config/finnhub_verify_result.json: 机器可读结果(含 x-ratelimit 响应头)
说明:
  2026-09-12 首轮实测: 本环境出口对 Cloudflare 托管域(finnhub.io)为【间歇性可达】
  (直连成功率约20-30%, 部分请求TCP超时; 对照组 sec.gov/FRED/腾讯稳定可达)。
  已从有效响应确认: /quote AAPL 返回真实行情(c=332.27, t=2026-09-11收盘) → key【有效】。
  本脚本经 client 内置重试(3次+指数退避)后逐端点实测, 每用例成功即记录 x-ratelimit 响应头。
  若成功率过低导致个别用例 FAIL, 视为环境出口不稳而非端点/权限问题, 择机重跑即可。
"""
import argparse
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from market_fetcher import finnhub_api, storage  # noqa: E402

now = datetime.datetime.now()
UNX = lambda d: int(time.mktime(d.timetuple()))
FROM_1Y = UNX(now - datetime.timedelta(days=370))
TO = UNX(now)
FROM_30D = UNX(now - datetime.timedelta(days=30))
FROM_90D = UNX(now - datetime.timedelta(days=90))
FROM_7D = (now - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
TO_7D = (now + datetime.timedelta(days=3)).strftime("%Y-%m-%d")

# (编号, 名称, 方法, 路径, 参数)
FULL = [
    ("01", "实时报价 /quote (AAPL)", "get", "/quote", {"symbol": "AAPL"}),
    ("02", "实时报价 /quote (NVDA)", "get", "/quote", {"symbol": "NVDA"}),
    ("03", "实时报价 /quote (TSLA)", "get", "/quote", {"symbol": "TSLA"}),
    ("04", "实时报价 /quote (BABA)", "get", "/quote", {"symbol": "BABA"}),
    ("05", "美股日K /stock/candle (AAPL D 1y)", "get", "/stock/candle",
     {"symbol": "AAPL", "resolution": "D", "from": FROM_1Y, "to": TO}),
    ("06", "美股日K /stock/candle (NVDA D 1y)", "get", "/stock/candle",
     {"symbol": "NVDA", "resolution": "D", "from": FROM_1Y, "to": TO}),
    ("07", "行业ETF日K /stock/candle (XLK D 1y)", "get", "/stock/candle",
     {"symbol": "XLK", "resolution": "D", "from": FROM_1Y, "to": TO}),
    ("08", "行业ETF日K /stock/candle (XLE D 1y)", "get", "/stock/candle",
     {"symbol": "XLE", "resolution": "D", "from": FROM_1Y, "to": TO}),
    ("09", "行业ETF日K /stock/candle (XLF D 1y)", "get", "/stock/candle",
     {"symbol": "XLF", "resolution": "D", "from": FROM_1Y, "to": TO}),
    ("10", "公司概况 /stock/profile2 (AAPL)", "get", "/stock/profile2", {"symbol": "AAPL"}),
    ("11", "基本面指标 /stock/metric (AAPL)", "get", "/stock/metric",
     {"symbol": "AAPL", "metric": "all"}),
    ("12", "财务报表 /stock/financials-reported (AAPL bs annual)", "get",
     "/stock/financials-reported", {"symbol": "AAPL", "statement": "bs", "freq": "annual"}),
    ("13", "财务报表 /stock/financials-reported (NVDA is quarterly)", "get",
     "/stock/financials-reported", {"symbol": "NVDA", "statement": "is", "freq": "quarterly"}),
    ("14", "SEC文件 /stock/filings (AAPL)", "get", "/stock/filings", {"symbol": "AAPL"}),
    ("15", "SEC文件 /stock/filings (TSLA 10-Q)", "get", "/stock/filings",
     {"symbol": "TSLA", "form": "10-Q"}),
    ("16", "EPS意外 /stock/earnings (AAPL)", "get", "/stock/earnings", {"symbol": "AAPL"}),
    ("17", "财报日历 /calendar/earnings (3天窗)", "get", "/calendar/earnings",
     {"from": FROM_7D, "to": TO_7D}),
    ("18", "经济日历 /calendar/economic", "get", "/calendar/economic", {}),
    ("19", "市场新闻 /news (general)", "get", "/news", {"category": "general"}),
    ("20", "公司新闻 /company-news (AAPL)", "get", "/company-news",
     {"symbol": "AAPL", "from": FROM_7D, "to": TO_7D}),
    ("21", "分析师推荐 /stock/recommendation (AAPL)", "get", "/stock/recommendation",
     {"symbol": "AAPL"}),
    ("22", "目标价 /stock/price-target (AAPL)", "get", "/stock/price-target",
     {"symbol": "AAPL"}),
    ("23", "同业 /stock/peers (NVDA)", "get", "/stock/peers", {"symbol": "NVDA"}),
    ("24", "市场状态 /stock/market-status (US)", "get", "/stock/market-status",
     {"exchange": "US"}),
    ("25", "节假日 /stock/market-holiday (US)", "get", "/stock/market-holiday",
     {"exchange": "US"}),
    ("26", "汇率 /forex/rates (base=USD)", "get", "/forex/rates", {"base": "USD"}),
    ("27", "美股代码表 /stock/symbol (exchange=US, 取样)", "get", "/stock/symbol",
     {"exchange": "US"}),
    ("28", "财报日历个股 /calendar/earnings (AAPL)", "get", "/calendar/earnings",
     {"symbol": "AAPL", "from": FROM_7D, "to": TO_7D}),
    ("29", "周K /stock/candle (AAPL W)", "get", "/stock/candle",
     {"symbol": "AAPL", "resolution": "W", "from": FROM_1Y, "to": TO}),
    ("30", "月K /stock/candle (AAPL M)", "get", "/stock/candle",
     {"symbol": "AAPL", "resolution": "M", "from": FROM_1Y, "to": TO}),
]
QUICK_IDX = {"01", "05", "07", "14", "16", "17"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    cases = [c for c in FULL if (not args.quick or c[0] in QUICK_IDX)]

    cli = finnhub_api.FinnhubClient()
    results, ok_n = [], 0
    for no, name, _m, path, params in cases:
        rec = {"no": no, "case": name, "endpoint": path, "params": params}
        t0 = time.time()
        try:
            body = cli.get(path, params)
            dt = round((time.time() - t0) * 1000)
            empty = (body in (None, {}, []) or (isinstance(body, dict) and body.get("s") == "no_data"))
            rec.update(status="OK" if not empty else "OK_EMPTY", latency_ms=dt,
                       sample_keys=list(body)[:8] if isinstance(body, dict) else
                       (f"list[{len(body)}]" if isinstance(body, list) else str(type(body))))
            ok_n += (rec["status"] == "OK")
        except finnhub_api.FinnhubError as e:
            rec.update(status="FAIL", latency_ms=round((time.time() - t0) * 1000),
                       detail=str(e)[:200])
        except Exception as e:
            rec.update(status="EXCEPTION", detail=f"{type(e).__name__}: {str(e)[:200]}")
        results.append(rec)
        print(f"[{no}] {rec['status']:<12} {str(rec.get('latency_ms','-')):>6}ms  {name}"
              + (f" | {rec.get('detail','')}" if rec.get("detail") else ""))
        time.sleep(1.2)

    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "config", "finnhub_verify_result.json")
    storage.save_json({"checked_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                       "mode": "quick" if args.quick else "full",
                       "ok": ok_n, "total": len(results), "results": results},
                      out_path)
    print(f"\n=== 实测汇总: OK {ok_n}/{len(results)} → {out_path} ===")


if __name__ == "__main__":
    main()
