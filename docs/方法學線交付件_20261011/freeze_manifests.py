#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
freeze_manifests.py — 數據凍結層 v1 執行/校驗工具（方法學線 P1①）
原則：
  1. 原始 manifest 一律不動（不可變證據層），僅生成側車 <run>.frozen.json
  2. 現狀凍結（retro）：記錄 2026-10-11 時點文件字節 sha256；前向運行改為 v2-native
  3. latest.csv 等可變指針文件 flag=mutable_pointer，不入凍結判決
  4. code_commit 溯源錨：v1.0-20261011@0786c312（GitHub 基線，retro=true）
用法：
  python3 freeze_manifests.py freeze    # 生成側車+主索引
  python3 freeze_manifests.py verify    # 對側車重算哈希核驗
"""
import json, glob, hashlib, csv, os, sys, io
from datetime import datetime

BASE = "/home/z/my-project/shared/market_data"
OUT  = os.path.join(BASE, "manifest_v2_freeze")
CODE_COMMIT = "v1.0-20261011@0786c312f0f5eee235366b52cfb7ff5de0163afb"
FROZEN_AT = "2026-10-11T22:35:00+08:00"
MUTABLE = {"realtime/latest.csv"}

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def rel(p):
    return p.replace(BASE + "/", "") if p and p.startswith(BASE) else (p or "")

def collect_paths(obj, acc):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("path", "paths") and isinstance(v, (str, list)):
                vs = v if isinstance(v, list) else [v]
                acc.update(x for x in vs if isinstance(x, str))
            else:
                collect_paths(v, acc)
    elif isinstance(obj, list):
        for x in obj: collect_paths(x, acc)

def kline_map(code):
    return "daily/" + code.lower().replace(".", "_") + ".csv"

def csv_tail(p, n_rows=0):
    """返回 (rows_count_excl_header, last_date)"""
    try:
        with io.open(p, "r", encoding="utf-8-sig", errors="replace") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        if len(lines) < 2: return (0, None)
        last = lines[-1].split(",")[0]
        return (len(lines) - 1, last)
    except Exception:
        return (None, None)

def build_record(mpath):
    name = os.path.basename(mpath)
    run_id = name[:-5] if name.endswith(".json") else name
    d = json.load(io.open(mpath, "r", encoding="utf-8"))
    r = {"run_id": run_id, "type": d.get("type"), "run_ts": d.get("run_ts"),
         "schema_version": "2.0-freeze-retro", "code_commit": CODE_COMMIT,
         "code_commit_retro": True, "frozen_at": FROZEN_AT,
         "manifest_file": "manifest/" + name,
         "manifest_sha256": sha256_file(mpath), "data_files": [], "claims_check": []}
    refs = set()
    if d.get("type") == "kline_batch":
        for it in d.get("results", []):
            if it.get("code"):
                refs.add(kline_map(it["code"]))
                r["claims_check"].append({"code": it["code"],
                    "claimed_rows": it.get("rows"), "claimed_last_date": it.get("last_date")})
    collect_paths(d, refs)
    n_mut = 0
    for rp in sorted(refs):
        ap = os.path.join(BASE, rel(rp))
        if not ap.startswith(BASE):  # 越界路徑不收
            continue
        ent = {"path": rel(rp)}
        if not os.path.exists(ap):
            # 同詞干替代後綴解析（9/12 舊批次 _OQ/_N 誤標 → 9/19 後綴正名重拉已修正）
            stem, ext = os.path.splitext(rel(rp))
            resolved = None
            if ext == ".csv":
                if stem.endswith(("_n", "_oq", "_am")):
                    base = stem.rsplit("_", 1)[0]
                    alts = [s for s in ("_n", "_oq", "_am") if s != "_" + stem.rsplit("_", 1)[1]]
                    cands = [base + s for s in alts]
                else:
                    cands = [stem + s for s in ("_n", "_oq", "_am")]  # 無後綴代碼補後綴
                for cand in cands:
                    cpath = cand + ext
                    if os.path.exists(os.path.join(BASE, cpath)):
                        resolved = cpath; break
            if resolved:
                cap = os.path.join(BASE, resolved)
                ent.update(status="missing_superseded", resolved_path=resolved,
                           resolved_sha256=sha256_file(cap),
                           note="舊批次後綴誤標，9/19後綴正名重拉已修正取代")
            else:
                ent.update(status="missing")
            r["data_files"].append(ent); continue
        mutable = rel(rp) in MUTABLE
        if mutable: n_mut += 1
        ent.update(status="mutable_pointer" if mutable else "frozen",
                   sha256=sha256_file(ap), bytes=os.path.getsize(ap),
                   mtime=datetime.utcfromtimestamp(os.path.getmtime(ap)).isoformat() + "Z")
        if d.get("type") == "kline_batch" and not mutable:
            rows, last = csv_tail(ap)
            ent.update(actual_rows=rows, actual_last_date=last)
        r["data_files"].append(ent)
    r["summary"] = {"files_total": len(r["data_files"]),
                    "frozen": sum(1 for x in r["data_files"] if x["status"] == "frozen"),
                    "mutable_pointer": n_mut, "missing": sum(1 for x in r["data_files"] if x["status"] == "missing"),
                    "missing_superseded": sum(1 for x in r["data_files"] if x["status"] == "missing_superseded")}
    # kline 申明核對：文件 mtime 晚於 run_ts（重寫覆蓋）則申明僅歷史參考
    claims = []
    for c in r.pop("claims_check"):
        fent = next((x for x in r["data_files"] if x["path"] == kline_map(c["code"])), None)
        if not fent or fent["status"] != "frozen":
            claims.append({**c, "check": "n/a"}); continue
        mtime_after = fent["mtime"] > (d.get("run_ts", "1970") + "").replace(" ", "T")[:19]
        ok = (fent.get("actual_last_date") == c.get("claimed_last_date")) if not mtime_after else None
        claims.append({**c, "check": ("match" if ok else "advanced_overwritten") if ok is not None else "advanced_overwritten"})
    r["claims_check"] = claims
    return r

def main(mode):
    os.makedirs(OUT, exist_ok=True)
    mans = sorted(glob.glob(os.path.join(BASE, "manifest", "*.json")))
    idx = []
    for mp in mans:
        rec = build_record(mp)
        fp = os.path.join(OUT, rec["run_id"] + ".frozen.json")
        if mode == "freeze":
            with io.open(fp, "w", encoding="utf-8") as f:
                json.dump(rec, f, ensure_ascii=False, indent=1)
        else:  # verify
            old = json.load(io.open(fp, "r", encoding="utf-8"))
            assert old["manifest_sha256"] == sha256_file(mp), "MANIFEST CHANGED: " + rec["run_id"]
            for e in old["data_files"]:
                if e["status"] == "frozen":
                    ap = os.path.join(BASE, e["path"])
                    assert os.path.exists(ap) and sha256_file(ap) == e["sha256"], "DRIFT: " + e["path"]
            rec = old
        idx.append((rec["run_id"], rec["type"], rec["summary"]["files_total"],
                    rec["summary"]["frozen"], rec["summary"]["mutable_pointer"],
                    rec["summary"]["missing"], rec["summary"]["missing_superseded"],
                    rec["manifest_sha256"][:16]))
    ip = os.path.join(OUT, "freeze_index_20261011.csv")
    with io.open(ip, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["run_id", "type", "files_total", "files_frozen", "mutable_pointer",
                    "missing", "missing_superseded", "manifest_sha256_16", "code_commit", "frozen_at", "verify_mode"])
        for t in idx:
            w.writerow(list(t) + [CODE_COMMIT, FROZEN_AT, mode])
    print(f"[{mode}] manifests={len(mans)} files_frozen={sum(t[3] for t in idx)} "
          f"mutable={sum(t[4] for t in idx)} missing={sum(t[5] for t in idx)} -> {os.path.basename(ip)}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "freeze")
