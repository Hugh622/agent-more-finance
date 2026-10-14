# -*- coding: utf-8 -*-
"""P2-3 Bronze/Silver/Gold 数据分层 (E-P2 批次1/2 · 全栈开发)
=============================================================
分层语义（评审共识「Bronze/Silver/Gold」最小落地）:
  Bronze  原始层: 源文件字节级不可变副本 + sha256 + 来源探针, 一次入库永不改写;
  Silver  规整层: 按契约归一(列裁剪/类型化/日期规范化/排序), 逐行干净可重放;
  Gold    应用层: 面向执行的分析视图(每序列最新值视图; calendar 域=全量会议视图)。
血统(lineage): 每次晋升写入 lineage manifest ——
  {layer, artifact, source_artifact, source_sha256, output_sha256,
   transform_id, created_at}, verify_lineage() 全链复算, 任何环节篡改即断链报红。

幂等: 源未变(sha 同)时重跑跳过并报 unchanged; 源变更则生成新代并记录。
v1.1 域分发(批次2): rates(tall+wide) / fx(tall+wide) / ah(panel) / volatility(kline) / klines(kline)。
v1.3 域分发(批次2收尾): calendar(JSON bronze+silver: fomc/earnings 归一, 模板显式跳过)
  / fundamentals(fundamentals 格式) / realtime(snapshot 格式, latest.csv=可变指针排除)
  / sec(filings+crosscheck 格式)。
用法: python3 scripts/data_layering.py --src ../market_data/<域> --root ../market_data/bsg --domain <域>
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from market_fetcher.atomic_io import atomic_write_json, sha256_file  # noqa: E402

import pandas as pd  # noqa: E402

TOOL_VERSION = "data_layering@1.3.0"  # v1.3: JSON bronze/silver + snapshot/filings/crosscheck/fundamentals + 可变指针排除
TOOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 域格式分发(v1.1): 逐文件自动探测, 优先级 kline > panel_ah > filings > crosscheck
#   > snapshot > fundamentals > tall > wide > skip
META_COLS = {"fetched_at", "source", "source_level", "grade", "note", "amount_raw",
             "quote_ts", "prev_close"}
KLINE_NUM = ("open", "high", "low", "close", "volume")
# v1.3: 可变指针文件不晋升（bronze 字节副本会被改写破坏「一次入库永不改写」）,
#   与冻结层判例一致（latest.csv=可变指针, 排除冻结/分层资格）
MUTABLE_POINTERS = {"latest.csv"}


def _detect_format(df: pd.DataFrame) -> str:
    cols = set(df.columns)
    if {"date", "open", "high", "low", "close"} <= cols:
        return "kline"
    if {"a_code", "h_code"} <= cols:
        return "panel_ah"
    if {"form", "filing_date"} <= cols:
        return "filings"
    if {"form", "accession"} <= cols:
        return "crosscheck"
    if {"key", "code", "price", "fetched_at"} <= cols:
        return "snapshot"
    if "symbol" in cols and "date" not in cols:
        return "fundamentals"
    if {"date", "value"} <= cols:
        return "tall"
    if "date" in cols:
        num = [c for c in df.columns if c not in META_COLS and c != "date"
               and pd.to_numeric(df[c], errors="coerce").notna().sum() > 0]
        if len(num) >= 2:
            return "wide"
    return "unknown"


def _transform_tall(df: pd.DataFrame) -> pd.DataFrame:
    keys = [c for c in ("series_id", "ticker") if c in df.columns]
    s = df[["date"] + keys].assign(value=pd.to_numeric(df["value"], errors="coerce"))
    return s.dropna(subset=["value"]).sort_values("date").reset_index(drop=True)


def _transform_kline(df: pd.DataFrame) -> pd.DataFrame:
    keep = ["date", "open", "high", "low", "close", "volume"]
    keep += [c for c in ("code", "name") if c in df.columns]
    s = df[keep].copy()
    for c in KLINE_NUM:
        if c in s.columns:
            s[c] = pd.to_numeric(s[c], errors="coerce")
    return s.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)


def _transform_wide(df: pd.DataFrame) -> pd.DataFrame:
    num = [c for c in df.columns if c not in META_COLS and c != "date"
           and pd.to_numeric(df[c], errors="coerce").notna().sum() > 0]
    m = df.melt(id_vars="date", value_vars=num, var_name="series_id", value_name="value")
    m["value"] = pd.to_numeric(m["value"], errors="coerce")
    return m.dropna(subset=["value"]).sort_values(["date", "series_id"]).reset_index(drop=True)


def _transform_panel_ah(df: pd.DataFrame) -> pd.DataFrame:
    s = df[["date", "a_code", "h_code", "a_price", "h_price", "premium_pct"]].copy()
    for c in ("a_price", "h_price", "premium_pct"):
        s[c] = pd.to_numeric(s[c], errors="coerce")
    return s.dropna(subset=["premium_pct"]).sort_values(["date", "a_code"]).reset_index(drop=True)


def _to_utc_iso(series: pd.Series) -> pd.Series:
    """时间戳归一(v1.3): naive 视为 UTC(全库 UTC 应用层约定), 带时区则转 UTC。"""
    ts = pd.to_datetime(series, errors="coerce", utc=True)
    return ts.dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _transform_filings(df: pd.DataFrame) -> pd.DataFrame:
    keep = [c for c in ("symbol", "name_cn", "cik", "form", "filing_date",
                        "accession", "doc_url", "as_of") if c in df.columns]
    s = df[keep].copy()
    s["filing_date"] = pd.to_datetime(s["filing_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    s = s.dropna(subset=["filing_date", "symbol", "form"])
    if "fetched_at" in df.columns:
        s["as_of"] = _to_utc_iso(df.loc[s.index, "fetched_at"])
    s = s.drop_duplicates(subset=["symbol", "form", "filing_date", "accession"], keep="first")
    return s.sort_values(["filing_date", "symbol"],
                         ascending=[False, True]).reset_index(drop=True)


def _transform_crosscheck(df: pd.DataFrame) -> pd.DataFrame:
    keep = [c for c in ("symbol", "form", "filed", "report", "accession",
                        "doc_url") if c in df.columns]
    s = df[keep].copy()
    if "fetched_at" in df.columns:
        s["as_of"] = _to_utc_iso(df["fetched_at"])
    s = s.dropna(subset=["symbol", "form"])
    dedupe = [c for c in ("symbol", "form", "accession", "report") if c in s.columns]
    s = s.drop_duplicates(subset=dedupe, keep="first")
    return s.sort_values(["symbol", "form"]).reset_index(drop=True)


SNAPSHOT_NUM = ("price", "prev_close", "open", "high", "low", "pct_chg", "volume")


def _transform_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    keep = [c for c in ("key", "market", "name", "code", "price", "prev_close", "open",
                        "high", "low", "pct_chg", "volume", "ts") if c in df.columns]
    s = df[keep].copy()
    s["ts"] = _to_utc_iso(df["fetched_at"])
    for c in SNAPSHOT_NUM:
        if c in s.columns:
            s[c] = pd.to_numeric(s[c], errors="coerce")
    s = s.dropna(subset=["key", "ts", "price"])
    s = s.drop_duplicates(subset=["key", "ts"], keep="first")
    return s.sort_values(["ts", "key"]).reset_index(drop=True)


FUND_META = {"symbol", "fetched_at", "source", "source_level", "grade"}


def _transform_fundamentals(df: pd.DataFrame) -> pd.DataFrame:
    metrics = [c for c in df.columns if c not in FUND_META]
    keep = ["symbol"] + metrics
    s = df[keep].copy()
    for c in metrics:
        s[c] = pd.to_numeric(s[c], errors="coerce")
    s["as_of"] = pd.to_datetime(df["fetched_at"], errors="coerce").dt.strftime("%Y-%m-%d")
    s = s.dropna(subset=["symbol"]).drop_duplicates(subset=["symbol"], keep="first")
    return s.sort_values("symbol").reset_index(drop=True)


def _json_transform(name: str, obj):
    """JSON silver(v1.3): fomc 会议表/美股财报窗归一; 模板与未知结构显式跳过。"""
    if not isinstance(obj, dict):
        return None, "skipped_json_not_dict"
    if "meetings" in obj and isinstance(obj["meetings"], list):
        rows = [{"date": m.get("date_start"), "meeting_date_end": m.get("date_end"),
                 "decision": m.get("decision"),
                 "dot_plot_median": (None if m.get("dot_plot_median") is None
                                     else float(m["dot_plot_median"]))}
                for m in obj["meetings"] if m.get("date_start")]
        if rows:
            return ("calendar_normalize_v1",
                    pd.DataFrame(rows).drop_duplicates(subset=["date"])
                      .sort_values("date").reset_index(drop=True))
        return None, "skipped_empty_meetings"
    if "earningsCalendar" in obj and isinstance(obj["earningsCalendar"], list):
        rows = [{"symbol": r.get("symbol"), "date": r.get("date"), "hour": r.get("hour") or "",
                 "quarter": r.get("quarter"), "year": r.get("year"),
                 "eps_estimate": r.get("epsEstimate"), "eps_actual": r.get("epsActual"),
                 "revenue_estimate": r.get("revenueEstimate"),
                 "revenue_actual": r.get("revenueActual")}
                for r in obj["earningsCalendar"] if r.get("symbol") and r.get("date")]
        if rows:
            return ("earnings_normalize_v1",
                    pd.DataFrame(rows).drop_duplicates(subset=["symbol", "date", "hour"])
                      .sort_values(["date", "symbol"]).reset_index(drop=True))
        return None, "skipped_empty_records"
    if {"purpose", "fields", "records"} <= set(obj):
        return None, "skipped_template_no_data"
    return None, "skipped_json_unknown_structure"


TRANSFORMS = {"tall": ("tall_normalize_v1", _transform_tall),
              "kline": ("kline_normalize_v1", _transform_kline),
              "wide": ("wide_series_v1", _transform_wide),
              "panel_ah": ("panel_ah_v1", _transform_panel_ah),
              "filings": ("filings_normalize_v1", _transform_filings),
              "crosscheck": ("crosscheck_normalize_v1", _transform_crosscheck),
              "snapshot": ("snapshot_utc_v1", _transform_snapshot),
              "fundamentals": ("fundamentals_v1", _transform_fundamentals)}


def _gold_key(df: pd.DataFrame) -> list:
    """gold 视图的分组键: 面板对 / 序列 id / K 线代码, 皆无则整文件一组。"""
    if {"a_code", "h_code"} <= set(df.columns):
        return None  # 面板: 组合键特殊处理
    for k in ("series_id", "ticker", "key", "code", "symbol"):
        if k in df.columns:
            return [k]
    return []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_lineage(root: str, layer: str, entry: dict) -> None:
    path = os.path.join(root, f"lineage_{layer}.json")
    os.makedirs(root, exist_ok=True)
    book = {"tool_version": TOOL_VERSION, "entries": []}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            book = json.load(f)
    book["entries"] = [e for e in book["entries"]
                       if not (e["artifact"] == entry["artifact"]
                               and e["source_artifact"] == entry["source_artifact"])]
    book["entries"].append(entry)
    atomic_write_json(book, path)


def promote_bronze(src: str, root: str, domain: str) -> list:
    """字节级不可变副本(v1.3 收 .csv/.json)。源 sha 与现有 bronze 记录一致 → unchanged。"""
    bdir = os.path.join(root, "bronze", domain)
    os.makedirs(bdir, exist_ok=True)
    lpath = os.path.join(root, f"lineage_bronze.json")
    prev = {}
    if os.path.isfile(lpath):
        with open(lpath, encoding="utf-8") as f:
            prev = {e["artifact"]: e for e in json.load(f).get("entries", [])}
    out = []
    for name in sorted(f for f in os.listdir(src) if f.endswith((".csv", ".json"))):
        if name in MUTABLE_POINTERS:
            out.append({"artifact": name,
                        "state": "skipped_mutable_pointer: 不入 bronze(改写会破坏不可变语义)"})
            continue
        p = os.path.abspath(os.path.join(src, name))
        sha = sha256_file(p)
        dst = os.path.join(bdir, name)
        if dst in prev and prev[dst]["source_sha256"] == sha and os.path.isfile(dst) \
                and sha256_file(dst) == sha:
            out.append({"artifact": dst, "state": "unchanged"})
            continue
        tmp = dst + ".tmp_bronze"
        shutil.copy2(p, tmp)
        os.replace(tmp, dst)
        entry = {"layer": "bronze", "artifact": dst, "source_artifact": p,
                 "source_sha256": sha, "output_sha256": sha256_file(dst),
                 "transform_id": "copy_bytes", "created_at": _now()}
        _write_lineage(root, "bronze", entry)
        out.append({"artifact": dst, "state": "promoted"})
    return out


def promote_silver(src: str, root: str, domain: str) -> list:
    """规整层 v1.3: CSV 逐文件探测格式套变换; JSON 按结构归一(fomc/earnings), 模板显式跳过。
    幂等: 源 sha 与既有 silver 血统一致 → unchanged(产物字节稳定)。"""
    sdir = os.path.join(root, "silver", domain)
    os.makedirs(sdir, exist_ok=True)
    lpath = os.path.join(root, "lineage_silver.json")
    prev = {}
    if os.path.isfile(lpath):
        with open(lpath, encoding="utf-8") as f:
            prev = {e["artifact"]: e for e in json.load(f).get("entries", [])}
    out = []
    for name in sorted(f for f in os.listdir(src) if f.endswith((".csv", ".json"))):
        if name in MUTABLE_POINTERS:
            out.append({"artifact": name, "state": "skipped_mutable_pointer"})
            continue
        spath = os.path.abspath(os.path.join(src, name))
        sha = sha256_file(spath)
        dst = os.path.join(sdir, os.path.splitext(name)[0] + ".csv" if name.endswith(".json")
                           else name)
        if dst in prev and prev[dst]["source_sha256"] == sha and os.path.isfile(dst) \
                and sha256_file(dst) == prev[dst]["output_sha256"]:
            out.append({"artifact": dst, "state": "unchanged"})
            continue
        if name.endswith(".json"):
            try:
                with open(spath, encoding="utf-8") as f:
                    obj = json.load(f)
            except Exception as exc:  # 坏文件不阻断整域晋升
                out.append({"artifact": name, "state": f"skipped_json_read_error: {exc}"})
                continue
            tid, s = _json_transform(name, obj)
            if tid is None:
                out.append({"artifact": name, "state": s})
                continue
            dst = os.path.join(sdir, os.path.splitext(name)[0] + ".csv")
            tmp = dst + ".tmp_silver"
            s.to_csv(tmp, index=False)
            os.replace(tmp, dst)
            entry = {"layer": "silver", "artifact": dst, "source_artifact": spath,
                     "source_sha256": sha256_file(spath), "output_sha256": sha256_file(dst),
                     "transform_id": tid, "format": "json", "created_at": _now()}
            _write_lineage(root, "silver", entry)
            out.append({"artifact": dst, "state": "promoted",
                        "format": tid, "rows": int(len(s))})
            continue
        try:
            df = pd.read_csv(spath, encoding="utf-8-sig")
        except Exception as exc:  # 坏文件不阻断整域晋升
            out.append({"artifact": name, "state": f"skipped_read_error: {exc}"})
            continue
        fmt = _detect_format(df)
        if fmt not in TRANSFORMS:
            out.append({"artifact": name, "state": f"skipped_format: {fmt}"})
            continue
        tid, fn = TRANSFORMS[fmt]
        s = fn(df)
        dst = os.path.join(sdir, name)
        tmp = dst + ".tmp_silver"
        s.to_csv(tmp, index=False)
        os.replace(tmp, dst)
        entry = {"layer": "silver", "artifact": dst, "source_artifact": spath,
                 "source_sha256": sha256_file(spath), "output_sha256": sha256_file(dst),
                 "transform_id": tid, "format": fmt, "created_at": _now()}
        _write_lineage(root, "silver", entry)
        out.append({"artifact": dst, "state": "promoted", "format": fmt, "rows": int(len(s))})
    return out


def _gold_sort_col(df: pd.DataFrame) -> str | None:
    for c in ("date", "ts", "filing_date", "as_of"):
        if c in df.columns:
            return c
    return None


def promote_gold(root: str, domain: str) -> list:
    """应用层 v1.3: 每键取最新一行; calendar 域=全量视图(会议表本身即执行对象)。"""
    gdir = os.path.join(root, "gold", domain)
    os.makedirs(gdir, exist_ok=True)
    sdir = os.path.join(root, "silver", domain)
    rows, srcs = [], []
    full_view = domain == "calendar"
    if os.path.isdir(sdir):
        for name in sorted(f for f in os.listdir(sdir) if f.endswith(".csv")):
            spath = os.path.join(sdir, name)
            df = pd.read_csv(spath, encoding="utf-8-sig")
            if df.empty:
                continue
            sort_col = _gold_sort_col(df)
            if sort_col:
                df = df.sort_values(sort_col)
            if {"a_code", "h_code"} <= set(df.columns):
                df = df.assign(pair_id=df["a_code"] + "|" + df["h_code"])
                keys = ["pair_id"]
            else:
                keys = _gold_key(df)
            if full_view or not keys:
                last = df if full_view else df.iloc[[-1]]
            else:
                last = df.groupby(keys, as_index=False).tail(1)
            last = last.copy()
            last.insert(0, "source", name)
            rows.append(last)
            srcs.append(spath)
    if not rows:
        return [{"artifact": f"(gold skipped: {domain} 无 silver 输入)", "state": "skipped"}]
    gold = pd.concat(rows, ignore_index=True)
    dst = os.path.join(gdir, f"latest_view_{domain}.csv")
    tmp = dst + ".tmp_gold"
    gold.to_csv(tmp, index=False)
    os.replace(tmp, dst)
    tid = "full_view_v1" if full_view else "latest_row_view_v1"
    for s in srcs:
        _write_lineage(root, "gold", {
            "layer": "gold", "artifact": dst, "source_artifact": s,
            "source_sha256": sha256_file(s), "output_sha256": sha256_file(dst),
            "transform_id": tid, "created_at": _now()})
    return [{"artifact": dst, "state": "promoted", "rows": int(len(gold)), "view": tid}]


def _resolve_artifact(p: str, root: str) -> str | None:
    """血统路径解析(v1.3): 绝对路径直接用; 批次1 旧相对路径(../market_data/…,
    记账时 cwd=market_data)按 root 的父目录回退解析, 保证跨 cwd 复算稳定。"""
    if os.path.isabs(p):
        return p if os.path.isfile(p) else None
    if os.path.isfile(p):
        return p
    cand = os.path.normpath(os.path.join(root, "..", p))
    return cand if os.path.isfile(cand) else None


def verify_lineage(root: str) -> dict:
    """全链复算: 逐条目重算 source/output sha, 断链即列红。"""
    root = os.path.abspath(root)
    report = {"ok": True, "layers": {}}
    for layer in ("bronze", "silver", "gold"):
        lpath = os.path.join(root, f"lineage_{layer}.json")
        if not os.path.isfile(lpath):
            continue
        with open(lpath, encoding="utf-8") as f:
            entries = json.load(f).get("entries", [])
        broken = []
        for e in entries:
            art = _resolve_artifact(e["artifact"], root)
            if art is None or sha256_file(art) != e["output_sha256"]:
                broken.append({"artifact": e["artifact"], "why": "output_sha_mismatch_or_missing"})
                continue
            src = _resolve_artifact(e["source_artifact"], root)
            if src is None or sha256_file(src) != e["source_sha256"]:
                broken.append({"artifact": e["artifact"], "why": "source_changed_or_missing"})
        report["layers"][layer] = {"entries": len(entries), "broken": broken}
        if broken:
            report["ok"] = False
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="P2-3 B/S/G 数据分层")
    ap.add_argument("--src", required=True, help="源域目录")
    ap.add_argument("--root", required=True, help="分层根目录(将建 bsg 三层)")
    ap.add_argument("--domain", required=True)
    ap.add_argument("--verify", action="store_true", help="仅全链血统校验")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    if a.verify:
        rep = verify_lineage(root)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0 if rep["ok"] else 1
    res = {"bronze": promote_bronze(a.src, root, a.domain),
           "silver": promote_silver(a.src, root, a.domain),
           "gold": promote_gold(root, a.domain)}
    rep = verify_lineage(root)
    print(json.dumps({"result": "OK" if rep["ok"] else "BROKEN",
                      "lineage": rep, "actions": res}, ensure_ascii=False, indent=2))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
