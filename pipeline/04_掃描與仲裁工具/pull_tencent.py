# -*- coding: utf-8 -*-
"""港股数据腿 Source A: 腾讯K线(不复权) + 实时快照. 2026-10-06 08:0x HKT 预市执行."""
import json, time, sys
import requests

H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
     'Referer': 'https://gu.qq.com/'}
HOSTS = ["https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
         "https://ifzq.gtimg.cn/appstock/app/fqkline/get",
         "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/fqkline/get"]

CODES = {
    # index
    "hkHSI": "HSI 恒生指数", "hkHSTECH": "HSTECH 恒生科技指数",
    # admin core 10
    "hk00700": "腾讯控股", "hk09988": "阿里巴巴-W", "hk09618": "京东集团-SW",
    "hk03690": "美团-W", "hk02269": "药明康德", "hk02268": "药明生物",
    "hk00388": "香港交易所", "hk00941": "中国移动", "hk01299": "友邦保险",
    "hk00005": "汇丰控股",
    # liquidity additions
    "hk02318": "中国平安", "hk01398": "工商银行", "hk00939": "建设银行",
    "hk00883": "中国海洋石油", "hk00857": "中国石油股份",
}

def kline(code, count=15, retries=4):
    param = f"{code},day,,,{count},"   # 不复权: adjust段留空
    for i in range(retries):
        url = HOSTS[i % len(HOSTS)]
        try:
            r = requests.get(url, params={"param": param}, headers=H, timeout=15)
            if r.status_code != 200 or not r.text.strip().startswith("{"):
                time.sleep(0.5 + i); continue
            d = r.json().get("data", {}).get(code, {})
            key = None
            for k in ("day", "qfqday"):
                if k in d and d[k]: key = k; break
            if not key: return None
            return [x[:6] for x in d[key]]  # [date, open, close, high, low, vol]
        except Exception:
            time.sleep(1 + i)
    return None

out = {}
for code in CODES:
    rows = kline(code)
    out[code] = {"name": CODES[code], "rows": rows}
    n = len(rows) if rows else 0
    print(f"{code:10s} {CODES[code]:8s} bars={n}{' last=' + str(rows[-1][:5]) if rows else ' FAIL'}", flush=True)
    time.sleep(0.3)

json.dump(out, open("tencent_kline_raw.json", "w"), ensure_ascii=False, indent=1)
print("SAVED tencent_kline_raw.json")
