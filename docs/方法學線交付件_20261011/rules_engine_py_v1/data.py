# -*- coding: utf-8 -*-
"""data.py — 冻结层消费层：manifest_v2_freeze 侧车选版＋sha256 全量复验＋日K装载（P1① 接入约定）
铁律：只消费 status=frozen 且校验通过的文件；哈希锚写入结果报告头。"""
import glob
import hashlib
import io
import json
import os

import numpy as np
import pandas as pd

FREEZE_DIR = "/home/z/my-project/shared/market_data/manifest_v2_freeze"
DATA_ROOT = "/home/z/my-project/shared/market_data"


def select_frozen_versions(freeze_dir=FREEZE_DIR, prefix="daily/"):
    """扫描全部 kline_batch 侧车，逐文件选『行数最多、同行数取最新冻结』的版本。
    返回 (selection, runs_used)：selection={path: entry}, runs_used={run_id: manifest_sha256}"""
    best = {}
    runs_used = {}
    for rp in sorted(glob.glob(os.path.join(freeze_dir, "*_kline_batch.frozen.json"))):
        j = json.load(io.open(rp, encoding="utf-8"))
        runs_used[j["run_id"]] = j["manifest_sha256"]
        for e in j.get("data_files", []):
            p = e.get("path", "")
            if not p.startswith(prefix):
                continue
            if e.get("status") != "frozen":
                continue
            cur = best.get(p)
            key = (e.get("actual_rows", 0), j.get("frozen_at", ""))
            if cur is None or key > (cur[1].get("actual_rows", 0), cur[0].get("frozen_at", "")):
                best[p] = (j, e)
    sel = {p: v[1] for p, v in best.items()}
    sel_runs = {p: v[0]["run_id"] for p, v in best.items()}
    return sel, sel_runs, runs_used


def verify_hashes(selection, data_root=DATA_ROOT):
    """全量复验 sha256（P1① F-1：身分由哈希认定）。返回 (ok_files, broken, verify_records)"""
    ok, broken, recs = 0, [], []
    for p, e in sorted(selection.items()):
        fp = os.path.join(data_root, p)
        if not os.path.exists(fp):
            broken.append((p, "MISSING_FILE"))
            continue
        h = hashlib.sha256(io.open(fp, "rb").read()).hexdigest()
        if h != e["sha256"]:
            broken.append((p, "HASH_MISMATCH"))
            continue
        ok += 1
        recs.append((p, e["sha256"][:16], e.get("actual_rows", -1)))
    return ok, broken, recs


def load_daily(path, data_root=DATA_ROOT, min_rows=240):
    """装载单标的日K：utf-8-sig、OHLCV 数值化、按日期去重保末、升序。
    返回 DataFrame(date,open,high,low,close,volume) 或 None（行数不足/解析失败）。"""
    fp = os.path.join(data_root, path)
    try:
        df = pd.read_csv(fp, encoding="utf-8-sig")
    except Exception:
        return None
    df.columns = [c.strip() for c in df.columns]
    need = {"date", "open", "high", "low", "close", "volume"}
    if not need.issubset(df.columns):
        return None
    df = df[list(need)].copy()
    for c in list(need - {"date"}):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "open", "high", "low", "close"]).drop_duplicates("date", keep="last")
    df = df.sort_values("date").reset_index(drop=True)
    if len(df) < min_rows:
        return None
    df["volume"] = df["volume"].fillna(0.0)
    return df


def market_of(path):
    """文件名前缀 → 市场标签（us→US, hk→HK, sh/sz→CN）"""
    name = os.path.basename(path).lower()
    if name.startswith("us"):
        return "US"
    if name.startswith("hk"):
        return "HK"
    if name.startswith(("sh", "sz")):
        return "CN"
    return "OTHER"


INDEX_FILES = {  # 指数类文件不可交易，剔除出可交易全集（EXP 预注册口径：池內標的）
    "daily/usdji.csv", "daily/usixic.csv", "daily/usndx.csv", "daily/usinx.csv",
    "daily/hkhsi.csv", "daily/hkhstech.csv", "daily/sh000001.csv", "daily/sh000300.csv",
    "daily/sz399001.csv", "daily/sz399006.csv",
}

POOL_CSV = "/home/z/my-project/shared/pool_review_20261010/池子全清单_数据覆盖矩阵_20261010_枚举版v1.1.csv"


def load_pool_list(pool_csv=POOL_CSV):
    """现行池子清单（10/10 年检枚举版 v1.1）→ 池內可交易代碼集。
    機械規則（EXP 預註冊「池內標的」的落實，非參數選擇）：
      ① 剔除 層級/池=指數 行；
      ② 剔除 年檢歸屬 含『出池』或『禁』之行（C-跟踪/禁/出池、B-金链(禁买)）——
         P0 確認制生成的是新買入訊號，出池/禁買標的不在可交易域；
      ③ 代碼 → daily/ 文件名（代碼本身即文件主名，如 sh600519/hk00700/usNVDA）。"""
    import csv
    keep, dropped = set(), {"index": 0, "out_or_banned": 0}
    for r in csv.DictReader(io.open(pool_csv, encoding="utf-8-sig")):
        code = (r.get("代码") or "").strip()
        if not code:
            continue
        if r.get("层级/池") == "指数":
            dropped["index"] += 1
            continue
        attr = r.get("年检归属") or ""
        if ("出池" in attr) or ("禁" in attr):
            dropped["out_or_banned"] += 1
            continue
        keep.add(code.lower())
    return keep, dropped


def load_universe(selection, pool_codes, data_root=DATA_ROOT, min_rows=240):
    """冻结层选择 ∩ 池内清单 → 可回测宇宙 {(market, code): df}。
    只装载 selection 中存在且通过哈希复验的文件（身份由 sha256 认定，P1① 契约）。"""
    _, broken, _ = verify_hashes(selection)
    broken_set = {p for p, _ in broken}
    uni = {}
    for p, e in selection.items():
        if p in INDEX_FILES or p in broken_set:
            continue
        code = os.path.basename(p).rsplit(".", 1)[0].lower()
        # 代码归一化: 池子清单 US 代码带交易所后缀 usaapl.oq, daily 文件名点转下划线 usaapl_oq
        if code not in pool_codes and code.replace("_", ".") not in pool_codes:
            continue
        df = load_daily(p, data_root, min_rows=min_rows)
        if df is None:
            continue
        uni[(market_of(p), code)] = df
    return uni
