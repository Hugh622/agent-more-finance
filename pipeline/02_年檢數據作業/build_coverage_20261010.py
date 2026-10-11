# -*- coding: utf-8 -*-
"""池子年检·数据腿交付物生成:
① 池子全清单×数据覆盖矩阵 CSV（220只基础设施池+41只研究池新增，最新日K日期/收盘/行数/状态）
② 数据腿就绪通报 MD（锚新鲜度、修复项、残余缺口）→ shared/pool_review_20261010/
只读本地数据，不联网。"""
import sys, os, json, csv, datetime
TOOL = "/home/z/my-project/shared/全栈工具v1_三地行情抓取"
sys.path.insert(0, TOOL)
from market_fetcher import us_symbols
from market_fetcher.pools import (INDICES, A_POOL, HK_POOL, ETF_POOL,
    US_WATCH_POOL, SECTOR_ETF_POOL)
DATA = "/home/z/my-project/shared/market_data"
OUT = "/home/z/my-project/shared/pool_review_20261010"

NEW_A = [("sh603893","瑞芯微"),("sz002028","思源电气"),("sh688116","天奈科技"),("sh688561","奇安信")]
NEW_WL = [("sh688023","安恒信息"),("sz300454","深信服"),("sz002439","启明星辰")]
NEW_HK = [("hk09926","康方生物"),("hk09880","优必选"),("hk03888","金山软件"),
          ("hk01801","信达生物"),("hk09660","地平线机器人"),("hk00981","中芯国际H"),
          ("hk01816","中广核电力")]
mapping = us_symbols.load_mapping()
us_pool = [(m["kline_code"], m["name_cn"]) for m in mapping if m["verified"]]
new_us = {"us"+m["symbol"].upper() for m in mapping
          if m["verified"] and m.get("last_verified","") >= "2026-10-10"}

# 年检宇宙归属（底稿v1.1 A/B/C层 → 代码）
REVIEW = {
 "A核心-美股": ["usMSFT.OQ","usNVDA.OQ","usMU.OQ","usTSM.N","usCEG.OQ","usCVX.N","usVST.N",
   "usHPE.N","usSPCX.OQ","usCRWD.OQ","usPANW.OQ","usCIBR.OQ","usSNDK.OQ"],
 "A核心-港股": ["hk02269","hk02359","hk02268","hk00700","hk09988","hk01299"],
 "A核心-A股": ["sh600036","sh603259","sh601088","sz300750","sh600900","hk00939","sh601857"],
 "B-电力链": ["usETN.N","usXOM.N","usCOP.N","usGEV.N","usTLN.OQ","usNRG.N","usSMR.N",
   "sh601985","hk01816"],
 "B-软件云": ["usMETA.OQ","usNOW.N","usNTAP.OQ","usESTC.N","usSNOW.N"],
 "B-高股息": ["hk00941","hk00883","sh601398","hk01919","hk00005"],
 "B-国产替代": ["sz002371","sh603893","sh688981","hk00981"],
 "B-金链(禁买)": ["usGLDM.AM","sh601899","hk02899"],
 "B-其他观察": ["usBMNR.AM","usRKLB.OQ","sh688561","hk09926","usMRNA.OQ","usSLB.N",
   "usBE.N","usVRT.N","usCRWV.OQ"],
 "B-网安A股轮换": ["sh688561","sh688023","sz300454","sz002439"],
 "C-跟踪/禁/出池": ["usZETA.N","hk03690","hk00388","sh600276","sh600519",
   "usJPM.N","usGS.N","usAVGO.OQ","usUNH.N","usGDX.AM","usXBI.AM"],
 "指数/总闸": ["usSPY.AM","usQQQ.OQ","hkHSI","sh000001","usINX","usDJI","usIXIC","usNDX"],
}
REVIEW_MAP = {}
for layer, codes in REVIEW.items():
    for c in codes:
        REVIEW_MAP.setdefault(c, []).append(layer)

def read_daily(code):
    f = os.path.join(DATA, "daily", code.lower().replace(".", "_") + ".csv")
    if not os.path.exists(f):
        return None
    lines = open(f, encoding="utf-8-sig").read().strip().split("\n")
    if len(lines) < 2:
        return None
    last = lines[-1].split(",")
    hdr = [h.strip().strip("\ufeff") for h in lines[0].split(",")]
    i = {k: hdr.index(k) for k in ("date", "close") if k in hdr}
    if "close" not in i or "date" not in i:
        return None
    return {"rows": len(lines) - 1, "date": last[i["date"]],
            "close": last[i["close"]]}

rows = []
def add(pool, code, name, tag):
    d = read_daily(code)
    snap = os.path.exists(os.path.join(DATA, "realtime", "latest.csv")) and "有" or "-"
    rows.append({"层级/池": pool, "代码": code, "名称": name, "最新日K": d["date"] if d else "缺",
                 "最新收盘": d["close"] if d else "-", "K线行数": d["rows"] if d else 0,
                 "年检归属": "、".join(REVIEW_MAP.get(code, [])) or "基础设施池",
                 "数据备注": tag})

wm = {m["symbol"].upper(): (m["kline_code"], m["name_cn"]) for m in mapping if m["verified"]}
watch_resolved = []
for s, _ in US_WATCH_POOL:
    sym = s.replace("us", "", 1).upper()
    watch_resolved.append(wm.get(sym, (s, s)))
sector_resolved = []
for s, n in SECTOR_ETF_POOL:
    sym = s.replace("us", "", 1).upper()
    sector_resolved.append(wm.get(sym, (s, n)))

for pool, items in [("指数", INDICES), ("A股65", A_POOL), ("港股24", HK_POOL),
                    ("美股池(映射表)", us_pool), ("观察池18", watch_resolved),
                    ("ETF", ETF_POOL), ("行业ETF", sector_resolved),
                    ("研究池新增A股", NEW_A), ("研究池新增港股", NEW_HK),
                    ("网安A股轮换(首席1010裁决)", NEW_WL)]:
    for it in items:
        code, name = (it[0], it[1])
        if any(r["代码"] == code for r in rows):
            continue
        tag = "本轮新增回填" if (code in new_us or code in [c for c, _ in NEW_A + NEW_HK]) else ""
        add(pool, code, name, tag)

os.makedirs(OUT, exist_ok=True)
p_csv = os.path.join(OUT, "池子全清单_数据覆盖矩阵_20261010.csv")
with open(p_csv, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

# 统计
total = len(rows)
missing = [r for r in rows if r["最新日K"] == "缺"]
us_stale = [r for r in rows if r["代码"].startswith("us") and r["最新日K"] < "2026-10-09" and r["最新日K"] != "缺"]
review_rows = [r for r in rows if r["年检归属"] != "基础设施池"]
fresh = sum(1 for r in review_rows if r["最新日K"] >= "2026-10-09")

try:
    S = json.load(open("/home/z/my-project/agents/6aa5076624bdc41e7983913b/jobs/pool_refresh_summary.json", encoding="utf-8"))
    batch_line = f"跑批manifest: ok={S['batch']['ok']} thin={S['batch']['thin']} fail={S['batch']['fail']}" + \
                 (f"，fail明细: {','.join(S['batch']['fails'])}" if S["batch"]["fails"] else "")
    map_line = f"映射表新增 {S['mapping_added']} 只(探测失败 {','.join(S['mapping_fail']) or '无'})"
except Exception as e:
    batch_line = f"summary不可读: {e}"; map_line = "-"

md = f"""# 数据腿就绪通报（池子年检 2026-10-10）
**编制**: 全栈开发（数据管道负责人）｜**用途**: 池子年检两腿统一数据底座，供宏观/量化/首席直接引用

## 锚新鲜度（本轮 13:18-13:3x 全池刷新后）
- **美股日K: 已刷新至 2026-10-09 收盘**（关键：10/9 20:28 HKT 的 us_morning 跑批发生在美东盘前，美股此前停在 10/8；本轮已补齐——两腿「10/9美收」锚自此有官方落盘依据，快照/最新收盘可复核）
- **A/H 日K: 2026-10-09 收盘**（10/9 20:11 ah_eod 落盘，本轮复刷无变化）
- 宏观通道（美债/FRED/信用利差/FX/AH溢价/波动率/SEC/日历）: 10/9 20:33 落盘，CPI 10/14 裁决前每日 06:30/16:40 自动续
- 实时快照: 本轮已重摄 latest.csv（腾讯通道，美股段=10/9收盘价口径）

## 修复项（本轮）
1. **调度守护已死重启**: 10/9 20:11 拉起的 scheduler 于当晚静默退出，今晨 06:30 us_morning 未触发（即美股停 10/8 的根因）→ 本轮人工跑批补齐 + 守护已重新拉起（状态锁幂等，周一 16:40 正常续跑）
2. **研究池缺口 41 只回填入池**: 两腿/底稿点名但基础设施池无数据的标的已探测验证+拉数（美股30: RKLB/MRNA/NOW/SNDK/CRWD/PANW/ZS/NRG/HPE/ZETA/UNH/PFE/SNOW/NTAP/ESTC/KKR/ASTS/AUR/QS/OKLO/SMR/BMNR+CIBR/BUG/SOXX/IGV/XBI/CPER/GLDM/GDX；A股4: 603893/002028/688116/688561；港股7: 09926/09880/03888/01801/09660/00981/01816）。{map_line}
3. {batch_line}

## 年检宇宙覆盖核对（底稿 v1.1 A/B/C 层）
- 年检名单（含指数总闸）**{len(review_rows)} 只，数据就绪 {fresh} 只**
- 缺数据标的: {"、".join(r['代码']+r['名称'] for r in missing) if missing else "无"}

## 残余缺口（不阻塞今晚交付）
1. **BTC**: 基础设施池无加密行情通道；BTC 接位区 82.9-83.5k / 生死线 78.6k 请量化腿沿用其自有实时源（此前报告口径），或待立项扩通道
2. **南向资金流**: 恒指解冻四条件之「南向退潮」读数——南向为 L2 检索录入项（制度限制），请通用助手/宏观按 §2.1 双源录入；若需我建港交所CCASS自动通道另立项
3. 港股「汇丰 00005 / 美团 03690 / 港交所 00388」如不在港股24蓝筹池内，本轮已按缺口清单标注，需要即补拉

## 文件
- `池子全清单_数据覆盖矩阵_20261010.csv`：{total} 只逐只「层级/代码/名称/最新日K/收盘/行数/年检归属/备注」，两腿引用请以此为准（勿再各自零散拉数）
- 本通报：`数据腿就绪通报_20261010.md`

*数据源等级: 腾讯=授权行情商(L2主通道)｜FRED/SEC=官方(L1)｜ Finnhub 美股K线为付费墙自动回退腾讯，不影响落盘完整性。*
"""
p_md = os.path.join(OUT, "数据腿就绪通报_20261010.md")
open(p_md, "w", encoding="utf-8").write(md)
print(f"rows={total} review={len(review_rows)} fresh={fresh} missing={len(missing)} us_stale={len(us_stale)}")
print("missing:", [(r['代码'], r['名称']) for r in missing][:15])
print("us_stale:", [(r['代码'], r['最新日K']) for r in us_stale][:10])
print("p_csv:", p_csv); print("p_md:", p_md)
