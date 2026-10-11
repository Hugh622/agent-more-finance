# -*- coding: utf-8 -*-
"""池子年检数据腿修复 2026-10-10:
① 研究池缺口标的探测入表(us_symbols.json) ② 全池K线刷新至10/9收盘 ③ 实时快照 ④ manifest"""
import sys, os, json, time, random
TOOL = "/home/z/my-project/shared/全栈工具v1_三地行情抓取"
sys.path.insert(0, TOOL)
from market_fetcher import us_symbols, runner
from market_fetcher.pools import (INDICES, A_POOL, HK_POOL, ETF_POOL,
    US_WATCH_POOL, SECTOR_ETF_POOL)

SUM = {"probed": [], "mapping_added": 0, "mapping_fail": [], "batch": None, "snapshot": None}

# ---- ① 研究池缺口: 美股个股(18)+ETF(8) ----
NEW_US = [
    ("RKLB","火箭实验室"),("MRNA","莫德纳"),("NOW","ServiceNow"),("SNDK","闪迪"),
    ("CRWD","CrowdStrike"),("PANW","Palo Alto"),("ZS","Zscaler"),("NRG","NRG能源"),
    ("HPE","慧与"),("ZETA","Zeta Global"),("UNH","联合健康"),("PFE","辉瑞"),
    ("SNOW","Snowflake"),("NTAP","NetApp"),("ESTC","Elastic"),("KKR","KKR"),
    ("ASTS","AST SpaceMobile"),("AUR","Aurora Innovation"),("QS","QuantumScape"),
    ("OKLO","Oklo"),("SMR","NuScale Power"),("BMNR","Bitmine Immersion"),
    ("CIBR","网安ETF(FirstTrust)"),("BUG","网安ETF(GlobalX)"),("SOXX","半导体ETF(iShares)"),
    ("IGV","软件ETF(iShares)"),("XBI","生物科技ETF(SPYDR)"),("CPER","铜ETF(USCF)"),
    ("GLDM","黄金迷你ETF(SPYDR)"),("GDX","金矿ETF(VanEck)"),
]
NEW_A = [("sh603893","瑞芯微"),("sz002028","思源电气"),("sh688116","天奈科技"),("sh688561","奇安信")]
NEW_HK = [("hk09926","康方生物"),("hk09880","优必选"),("hk03888","金山软件"),
          ("hk01801","信达生物"),("hk09660","地平线机器人"),("hk00981","中芯国际H"),
          ("hk01816","中广核电力")]

mapping = us_symbols.load_mapping()
have = {m["symbol"] for m in mapping}
for sym, name in NEW_US:
    if sym in have:
        SUM["probed"].append({"symbol": sym, "status": "already"});
        continue
    ent = us_symbols.probe_us_symbol(sym, name)
    SUM["probed"].append({"symbol": sym, "verified": ent["verified"], "code": ent["kline_code"]})
    if ent["verified"]:
        mapping.append(ent); SUM["mapping_added"] += 1
    else:
        SUM["mapping_fail"].append(sym)
    time.sleep(0.5 + random.random() * 0.3)
if SUM["mapping_added"]:
    with open(us_symbols.US_SYMBOLS_JSON, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=1)

# ---- ② 全池刷新(映射表已含新标的) ----
mapping = us_symbols.load_mapping()
watch_map = {m["symbol"]: (m["kline_code"], m["name_cn"]) for m in mapping if m["verified"]}
us_pool = [(m["kline_code"], m["name_cn"]) for m in mapping if m["verified"]]
used = {c for c, _ in us_pool}
watch_pool = []
for s, _ in US_WATCH_POOL:
    sym = s.replace("us", "", 1)
    if sym in watch_map and watch_map[sym][0] not in used:
        watch_pool.append(watch_map[sym])
pools = {"指数": INDICES, "A股65": A_POOL, "港股24": HK_POOL, "美股池": us_pool,
         "观察池18": watch_pool, "ETF": ETF_POOL, "行业ETF": SECTOR_ETF_POOL,
         "研究池新增A股": NEW_A, "研究池新增港股": NEW_HK}
print(f"计划标的: {sum(len(v) for v in pools.values())}", flush=True)
m1 = runner.run_kline_batch(pools, count=250, sleep=0.6)
p1 = runner.save_manifest(m1)
SUM["batch"] = {"ok": m1["ok"], "thin": m1["thin"], "fail": m1["fail"],
                "manifest": p1, "fails": [r["code"] for r in m1["results"] if r["status"] == "fail"]}
print(f"K线: ok={m1['ok']} thin={m1['thin']} fail={m1['fail']}", flush=True)

# ---- ③ 快照(覆盖新增A/H后手动并入) ----
m2 = runner.run_realtime_snapshot()
SUM["snapshot"] = {"total": m2["total"]}

with open("/home/z/my-project/agents/6aa5076624bdc41e7983913b/jobs/pool_refresh_summary.json", "w", encoding="utf-8") as f:
    json.dump(SUM, f, ensure_ascii=False, indent=1)
print("DONE", flush=True)
