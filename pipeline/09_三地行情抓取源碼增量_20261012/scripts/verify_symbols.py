# -*- coding: utf-8 -*-
"""标的验证器：全池实测腾讯通道，生成 config/us_symbols.json（美股映射表）与验证报告。
用法: python3 scripts/verify_symbols.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market_fetcher import storage, tencent_api, us_symbols  # noqa: E402
from market_fetcher.pools import (INDICES, A_POOL, A_POOL_SPARES, HK_POOL,  # noqa: E402
                                  HK_POOL_SPARES, US_POOL, US_POOL_SPARES, ETF_POOL,
                                  US_WATCH_POOL)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def verify_cny_hk(codes):
    ok, fail = [], []
    for code, name in codes:
        df = tencent_api.fetch_kline(code, count=5)
        (ok if df is not None and len(df) > 0 else fail).append((code, name))
        print(f"[verify] {code:12s} {name:10s} -> {'OK' if df is not None else 'FAIL'}")
        time.sleep(0.2)
    return ok, fail


def main():
    report = {}

    print("== 指数 ==")
    ok, fail = verify_cny_hk(INDICES)
    report["indices"] = {"ok": ok, "fail": fail}

    print("== A股65 + 候补 ==")
    ok, fail = verify_cny_hk(A_POOL + A_POOL_SPARES)
    report["a_pool"] = {"ok": ok, "fail": fail}

    print("== 港股24 + 候补 ==")
    ok, fail = verify_cny_hk(HK_POOL + HK_POOL_SPARES)
    report["hk_pool"] = {"ok": ok, "fail": fail}

    print("== 美股映射表（后缀探测）==")
    us_known = {s.replace("us", "").split(".")[0] for s, _ in US_POOL + US_POOL_SPARES}
    # 2026-09-12: 并入宏观观察池18只中的新增标的，映射表全量重建（36主池+候补+12新增=48）
    candidates = US_POOL + US_POOL_SPARES + [(s, n) for s, n in US_WATCH_POOL
                                             if s.replace("us", "") not in us_known]
    mapping = us_symbols.build_mapping([(s.replace("us", "").split(".")[0], n)
                                        for s, n in candidates])
    storage.save_json(mapping, us_symbols.US_SYMBOLS_JSON)
    us_ok = [(m["kline_code"], m["name_cn"]) for m in mapping if m["verified"]]
    us_fail = [(m["symbol"], m["name_cn"]) for m in mapping if not m["verified"]]
    report["us_pool"] = {"ok": us_ok, "fail": us_fail}

    print("== ETF（后缀探测）==")
    etf_cny = [e for e in ETF_POOL if not e[0].startswith("us")]
    ok, fail = verify_cny_hk(etf_cny)
    etf_us = []
    for code, name in [e for e in ETF_POOL if e[0].startswith("us")]:
        sym = code.replace("us", "").split(".")[0]
        entry = us_symbols.probe_us_symbol(sym, name)
        # ETF可能挂在NYSE Arca/AMEX，探测结果回填
        if entry["verified"]:
            etf_us.append((entry["kline_code"], name))
        else:
            fail.append((sym, name))
        print(f"[verify] {sym:8s} {name:10s} -> {'OK ' + entry['kline_code'] if entry['verified'] else 'FAIL'}")
    report["etf_pool"] = {"ok": ok + etf_us, "fail": fail}

    # 汇总
    n_ok = sum(len(v["ok"]) for v in report.values())
    n_fail = sum(len(v["fail"]) for v in report.values())
    report["_summary"] = {"ok": n_ok, "fail": n_fail,
                          "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    storage.save_json(report, os.path.join(ROOT, "config", "verify_report.json"))
    print(f"\n总计: OK={n_ok} FAIL={n_fail}")
    print("映射表: config/us_symbols.json | 报告: config/verify_report.json")


if __name__ == "__main__":
    main()
