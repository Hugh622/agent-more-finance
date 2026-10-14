# -*- coding: utf-8 -*-
"""P2-1 Parquet 降级归档器 (E-P2 批次1 · 全栈开发)
=====================================================
定位（评审共识）: 大体积平价数据从行式 CSV 降级为列式 Parquet 归档;
主档(MySQL/manifest)只存 **位置 + sha256** 指针, 不复制数据本身。

语义:
  - 源域(如 market_data/daily/*.csv)整体聚合为单个 parquet 分片,
    逐行保留 source_file 列(可回溯到源文件), 不改写源数据;
  - 归档清单(manifest JSON)原子写: 归档档 sha256 + 总行数 + 逐源文件
    {file, sha256, rows} —— 即「主档只存位置+hash」的落地形态;
  - --verify 对既有归档做回读校验: parquet sha、总行数、逐源文件行数三方对齐;
  - 幂等: 同一源域内容不变时重跑产出 sha 一致的归档(确定性写出)。

用法:
  python3 scripts/archive_parquet.py --src ../market_data/daily --domain daily --out ../market_data/archive/parquet
  python3 scripts/archive_parquet.py --verify <archive.parquet>
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from market_fetcher.atomic_io import atomic_write_json, sha256_file  # noqa: E402

import pandas as pd  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

TOOL_VERSION = "archive_parquet@1.0.0"


def _atomic_parquet_write(table, path: str) -> str:
    """pyarrow 无内建原子写 —— 复刻 atomic_io 语义: 同目录 tmp + fsync + replace。"""
    import pyarrow as pa
    import pyarrow.parquet as pq
    path = os.path.abspath(path)
    dirpath = os.path.dirname(path)
    os.makedirs(dirpath, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp_parquet_", dir=dirpath)
    os.close(fd)
    try:
        pq.write_table(table, tmp, compression="snappy")
        with open(tmp, "rb") as f:
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def archive_domain(src: str, domain: str, out_dir: str) -> dict:
    src = os.path.abspath(src)
    csvs = sorted(f for f in os.listdir(src) if f.endswith(".csv"))
    if not csvs:
        raise SystemExit(f"FAIL: 源域无 CSV: {src}")
    frames, meta_files, total_rows = [], [], 0
    for name in csvs:
        p = os.path.join(src, name)
        df = pd.read_csv(p, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        df.insert(0, "source_file", name)
        frames.append(df)
        meta_files.append({"file": name, "sha256": sha256_file(p), "rows": len(df)})
        total_rows += len(df)
    big = pd.concat(frames, ignore_index=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    out_path = os.path.join(out_dir, f"{domain}_{stamp}.parquet")
    table = pa.Table.from_pandas(big, preserve_index=False)
    table = table.replace_schema_metadata({
        b"tool_version": TOOL_VERSION.encode(),
        b"domain": domain.encode(),
        b"source_files": json.dumps(meta_files, ensure_ascii=False).encode()})
    _atomic_parquet_write(table, out_path)

    manifest = {
        "tool_version": TOOL_VERSION,
        "domain": domain,
        "archive_file": out_path,
        "archive_sha256": sha256_file(out_path),
        "archive_bytes": os.path.getsize(out_path),
        "rows_total": int(total_rows),
        "source_files": meta_files,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    atomic_write_json(manifest, out_path + ".manifest.json")
    return manifest


def verify_archive(archive_path: str) -> dict:
    """回读三方校验: manifest 自洽 × parquet 元数据 × 实际行数。"""
    import pyarrow.parquet as pq
    mpath = archive_path + ".manifest.json"
    with open(mpath, encoding="utf-8") as f:
        m = json.load(f)
    report = {"archive": archive_path, "checks": [], "ok": True}

    def check(name, cond, detail=""):
        report["checks"].append({"check": name, "ok": bool(cond), "detail": detail})
        if not cond:
            report["ok"] = False

    check("manifest.archive_sha256", sha256_file(archive_path) == m["archive_sha256"])
    tbl = pq.read_table(archive_path)
    check("rows_total", tbl.num_rows == m["rows_total"],
          f"parquet={tbl.num_rows} manifest={m['rows_total']}")
    pdf = tbl.select(["source_file"]).to_pandas()
    for e in m["source_files"]:
        n = int((pdf["source_file"] == e["file"]).sum())
        check(f"rows[{e['file']}]", n == e["rows"], f"parquet={n} manifest={e['rows']}")
    meta = tbl.schema.metadata or {}
    check("schema_metadata.source_files",
          json.loads(meta.get(b"source_files", b"[]")) == m["source_files"])
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="P2-1 Parquet 降级归档器")
    ap.add_argument("--src", help="源域目录(含 *.csv)")
    ap.add_argument("--domain", help="域标识(daily/rates/...)")
    ap.add_argument("--out", help="归档输出目录")
    ap.add_argument("--verify", metavar="ARCHIVE", help="回读校验既有归档")
    a = ap.parse_args()
    if a.verify:
        rep = verify_archive(os.path.abspath(a.verify))
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0 if rep["ok"] else 1
    if not (a.src and a.domain and a.out):
        ap.error("--src/--domain/--out 或 --verify 必填其一")
    m = archive_domain(a.src, a.domain, os.path.abspath(a.out))
    print(json.dumps({"result": "OK", "archive_file": m["archive_file"],
                      "archive_sha256_16": m["archive_sha256"][:16],
                      "rows_total": m["rows_total"],
                      "source_files": len(m["source_files"]),
                      "manifest": m["archive_file"] + ".manifest.json"},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
