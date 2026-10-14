# -*- coding: utf-8 -*-
"""Manifest v2 生成器 (E-P1-1 · 量化腿凍結層規格 F-2/F-3/F-4 對接)

v2 字段(新增产出 100% 带齐, 存量 33 份 manifest 由量化腿 Q-P1-1 retro 补齐):
  schema_version = 2
  run_id         = run_<UTCts>_<type> (与文件名一致, 回测引用锚)
  ts_utc / ts_hk 双时戳(ISO8601, 对齐评审"UTC+HKT 双时戳")
  code_commit    = repo_staging 镜像仓 HEAD(真 git hash; pipeline 目录非独立仓,
                   以 code_fingerprint 为准)
  code_fingerprint = scripts/ + market_fetcher/ + tests/ 全部 *.py 的
                   sha256 内容指纹(本地代码态的精确锚, 改一行即变)
  quality_status = QualityStatus 枚举(good/warn/bad, 按 status 计数推导)
  data_files[]   = 全部引用数据文件 {path(rel), sha256, bytes, rows, last_date,
                   status, mutable_pointer}; F-4: latest.csv 类可变指针标
                   mutable_pointer=true
  archive/       = F-3 只追加区: 引用文件复制到 archive/<run_id>/<相对路径>,
                   批完落 _SUCCESS(sha256 清单), 同 type 保留最近 KEEP_RUNS 批

历史批次 manifest 一律不重写(不可变证据层, 由冻结侧车覆盖)。
"""
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone, timedelta

from market_fetcher import atomic_io
from market_fetcher.status import DataStatus, QualityStatus, batch_quality

HKT = timezone(timedelta(hours=8))
SCHEMA_VERSION = 2
KEEP_RUNS = 14          # F-3 只追加区: 同 type 保留批数(磁盘上限约束)
MUTABLE_POINTER_NAMES = {"latest.csv", "latest.json", "latest.md"}

_OK = {"ok", "verified", "good"}
_THIN = {"thin", "degraded", "insufficient", "warn", "pending"}
_FAIL = {"fail", "missing", "corrupted", "bad"}


def _code_commit() -> str:
    """repo_staging 镜像仓 HEAD; 不可得时 unversioned(诚实标注)。"""
    repo = "/home/z/my-project/agents/6aa5076624bdc41e7983913b/repo_staging"
    try:
        r = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        h = (r.stdout or "").strip()
        if r.returncode == 0 and len(h) == 40:
            return h + "+pipeline-mirror"
    except Exception:
        pass
    return "unversioned"


def _code_fingerprint(base: str) -> str:
    """scripts/+market_fetcher/+tests/ 全部 .py 的确定性内容指纹。"""
    import hashlib
    h = hashlib.sha256()
    roots = ["scripts", "market_fetcher", "tests"]
    files = []
    for root in roots:
        rd = os.path.join(base, root)
        if not os.path.isdir(rd):
            continue
        for dp, _dns, fns in os.walk(rd):
            if "__pycache__" in dp:
                continue
            for fn in fns:
                if fn.endswith(".py"):
                    files.append(os.path.join(dp, fn))
    for p in sorted(files):
        rel = os.path.relpath(p, base)
        h.update(rel.encode())
        with open(p, "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def _walk_records(obj, out):
    """递归收集所有含 status 的记录 dict(质量推导用)。"""
    if isinstance(obj, dict):
        if isinstance(obj.get("status"), str):
            out.append(obj)
        for v in obj.values():
            _walk_records(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_records(v, out)


def _collect_data_files(manifest: dict, data_root: str) -> list:
    """收集 manifest 引用的数据文件(manifest 任何含 path 的 dict 层)。"""
    data_root = os.path.abspath(data_root)
    found = []

    def walk(obj):
        if isinstance(obj, dict):
            p = obj.get("path")
            if isinstance(p, str) and p.strip():
                # 相对路径一律锚定 data_root(manifest 引用的都是数据区文件),
                # 不用 os.path.abspath(那是锚 CWD, 换工作目录即断链)。
                ap = p if os.path.isabs(p) else os.path.join(data_root, p)
                rel = os.path.relpath(ap, data_root) if ap.startswith(data_root) else ap
                entry = {"path": rel}
                for k in ("status", "rows", "last_date", "source", "source_level"):
                    if obj.get(k) is not None:
                        entry[k] = obj[k]
                bn = os.path.basename(ap)
                entry["mutable_pointer"] = bn in MUTABLE_POINTER_NAMES
                if os.path.isfile(ap):
                    entry["sha256"] = atomic_io.sha256_file(ap)
                    entry["bytes"] = os.path.getsize(ap)
                else:
                    entry["sha256"] = None
                    entry["exists"] = False
                found.append(entry)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(manifest)
    # 去重(同文件多节引用只索引一次, 但保留首见记录的声明字段)
    seen, uniq = set(), []
    for e in found:
        if e["path"] not in seen:
            seen.add(e["path"])
            uniq.append(e)
    return uniq


def _quality(manifest: dict) -> str:
    recs = []
    _walk_records(manifest, recs)
    ok = thin = fail = 0
    for r in recs:
        s = DataStatus.try_coerce(r.get("status"))
        v = s.value if s else str(r.get("status", "")).lower()
        if v in _OK:
            ok += 1
        elif v in _THIN:
            thin += 1
        elif v in _FAIL:
            fail += 1
    total = ok + thin + fail
    if total == 0:  # 无 status 记录的 manifest(纯元信息)按 good 处理
        return QualityStatus.GOOD.value
    return batch_quality(ok, thin, fail, total).value


def build_v2(manifest: dict, data_root: str, base: str, run_id: str = None) -> dict:
    """在 v1 manifest 上叠加 v2 顶层字段(不改动既有键, 向后兼容)。

    run_id 缺省= run_<UTCts>_<type>; 调用方传文件名 stem 时以文件名为准
    (回测引用 run_id 即可直接定位 manifest 文件)。
    """
    ts = datetime.now(timezone.utc)
    m = dict(manifest)
    m["schema_version"] = SCHEMA_VERSION
    m["run_id"] = run_id or f"run_{ts:%Y%m%d_%H%M%S}_{m.get('type', 'misc')}"
    m["ts_utc"] = ts.isoformat(timespec="seconds")
    m["ts_hkt"] = ts.astimezone(HKT).isoformat(timespec="seconds")
    m["code_commit"] = _code_commit()
    m["code_fingerprint"] = _code_fingerprint(base)
    m["quality_status"] = _quality(manifest)
    m["data_files"] = _collect_data_files(manifest, data_root)
    return m


def archive_run(m: dict, data_root: str) -> str:
    """F-3: 复制引用文件到 archive/<run_id>/ 只追加区 + _SUCCESS + 同型保留裁剪。"""
    arc_dir = os.path.join(data_root, "archive", m["run_id"])
    copied = []
    for e in m.get("data_files", []):
        if not e.get("sha256"):
            continue  # 缺失文件不进只追加区(以 manifest exists=false 记录)
        src = os.path.join(data_root, e["path"])
        dst = os.path.join(arc_dir, e["path"])
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(dst)
    if copied:
        atomic_io.write_batch_success(arc_dir, copied,
                                      run_id=m["run_id"], schema_version=SCHEMA_VERSION)
    _prune(os.path.dirname(arc_dir), m.get("type", "misc"), KEEP_RUNS)
    return arc_dir


def _prune(archive_root: str, mtype: str, keep: int):
    """同 type 前缀 run_ 目录仅保留最近 keep 批(只追加区的磁盘护栏)。"""
    try:
        dirs = sorted(
            (d for d in os.listdir(archive_root)
             if d.startswith("run_") and f"_{mtype}" in d and
             os.path.isdir(os.path.join(archive_root, d))),
            reverse=True)
        for d in dirs[keep:]:
            shutil.rmtree(os.path.join(archive_root, d), ignore_errors=True)
    except OSError:
        pass


def summary_for_log(m: dict) -> str:
    return (f"v2 run_id={m['run_id']} quality={m['quality_status']} "
            f"files={len(m.get('data_files', []))} commit={m['code_commit'][:12]}")
