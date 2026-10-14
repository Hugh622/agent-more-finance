# -*- coding: utf-8 -*-
"""原子写入工具 v1 (P0-1 · 评审文件2《系统深度评审报告》可靠性项落地)

问题(评审原文): 核心写档直接 to_csv / json.dump 到目标路径, 程序写档中途死亡时,
读者可能取得半截 CSV/JSON; 单写者原则只能减少竞争, 不能解决崩溃一致性。

本模块语义:
  单文件  同目录临时档(.tmp_*) -> write -> flush -> os.fsync -> os.replace(原子rename)
          -> 目录 fsync。kill -9 任意时刻, 目标路径要么旧完整档要么新完整档, 永无半档。
  批次    批内所有文件各自原子写完成后, 由调用方调 write_batch_success() 落
          `_SUCCESS` 侧车(文件清单+sha256+meta, 亦原子写)。读者校验 _SUCCESS
          即知批次是否完整(评审原文: "读者只读 _SUCCESS 完成批次")。
  临时档  统一 .tmp_ 前缀, 崩溃残留可由 cleanup_stale_tmp() 识别清理, 永不会被
          正常读者当作数据文件。

验收: scripts/drills/kill_drill.py 随机 SIGKILL 100 次, 目标档 100% 可解析、
_SUCCESS 与实际内容 sha256 一致。
"""
import hashlib
import json
import os
import tempfile
from datetime import datetime
from typing import Callable, List, Optional

TMP_PREFIX = ".tmp_"
SUCCESS_NAME = "_SUCCESS"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fsync_dir(dirpath: str):
    """目录 fsync: 保证 rename 元数据落盘(掉电级持久化)。"""
    try:
        fd = os.open(dirpath, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass  # 部分文件系统不支持目录 fsync, 不阻塞主流程


def atomic_write(path: str, writer: Callable, mode: str = "wb",
                 encoding: Optional[str] = None) -> str:
    """通用原子写: writer(f) 负责把内容写入文件对象, 其余全部托管。"""
    path = os.path.abspath(path)
    dirpath = os.path.dirname(path) or "."
    os.makedirs(dirpath, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=TMP_PREFIX, suffix="_" + os.path.basename(path),
                               dir=dirpath)
    try:
        with open(fd, mode, encoding=encoding) as f:
            writer(f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)  # 同目录 rename, 原子
        _fsync_dir(dirpath)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def atomic_write_bytes(path: str, data: bytes) -> str:
    return atomic_write(path, lambda f: f.write(data), "wb")


def atomic_write_text(path: str, text: str, encoding: str = "utf-8") -> str:
    return atomic_write(path, lambda f: f.write(text), "w", encoding=encoding)


def atomic_write_json(obj, path: str, indent: int = 2,
                      ensure_ascii: bool = False) -> str:
    return atomic_write_text(path, json.dumps(obj, ensure_ascii=ensure_ascii,
                                              indent=indent))


def write_batch_success(dirpath: str, files: List[str], **meta) -> str:
    """批次完成标记: 汇总批内文件 sha256 清单, 原子写 `<dir>/_SUCCESS`。

    覆盖写管道三态语义(由 verify_batch 按 mtime 判定):
      complete    磁盘与 _SUCCESS 一致                    -> 批次确认完成, 可消费
      in_progress 数据文件比 _SUCCESS 新(新批写入中/中断)  -> 数据未损坏, 读者沿用旧批
      corrupted   数据文件比 _SUCCESS 旧且内容不符(标记后
                  被改动而未更新标记)                     -> 真损坏, 转人工
    """
    entries = []
    for p in files:
        p = os.path.abspath(p)
        entries.append({"file": os.path.basename(p),
                        "bytes": os.path.getsize(p),
                        "sha256": sha256_file(p)})
    payload = {"completed_at": datetime.now().isoformat(timespec="seconds"),
               "files": entries, **meta}
    return atomic_write_json(payload, os.path.join(os.path.abspath(dirpath),
                                                   SUCCESS_NAME))


def read_batch_success(dirpath: str) -> Optional[dict]:
    """读批次 _SUCCESS; 不存在返回 None。"""
    p = os.path.join(os.path.abspath(dirpath), SUCCESS_NAME)
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def verify_batch(dirpath: str) -> dict:
    """三态批次校验(complete/in_progress/corrupted), 语义见 write_batch_success。"""
    payload = read_batch_success(dirpath)
    if payload is None:
        return {"complete": False, "batch_present": False, "in_progress": False,
                "corrupted": False, "files": 0, "mismatches": []}
    s_path = os.path.join(os.path.abspath(dirpath), SUCCESS_NAME)
    try:
        s_mtime = os.path.getmtime(s_path)
    except OSError:
        s_mtime = 0.0
    mismatches = []
    for e in payload.get("files", []):
        p = os.path.join(os.path.abspath(dirpath), e["file"])
        if not os.path.exists(p):
            mismatches.append({"file": e["file"], "reason": "missing"})
            continue
        if sha256_file(p) == e["sha256"]:
            continue
        # 内容不符: 比标记新=新批写入中(正常中间态); 比标记旧=标记后被改(异常)
        newer = os.path.getmtime(p) > s_mtime
        mismatches.append({"file": e["file"],
                           "reason": "in_progress" if newer else "sha256_mismatch"})
    corrupted = any(m["reason"] in ("missing", "sha256_mismatch") for m in mismatches)
    in_progress = any(m["reason"] == "in_progress" for m in mismatches)
    return {"complete": not mismatches, "batch_present": True,
            "in_progress": in_progress, "corrupted": corrupted,
            "files": len(payload.get("files", [])), "mismatches": mismatches}


def cleanup_stale_tmp(dirpath: str, max_age_hours: float = 24.0) -> int:
    """清理崩溃残留的 .tmp_* 临时档(超过 max_age_hours 的), 返回清理数。"""
    n = 0
    cutoff = datetime.now().timestamp() - max_age_hours * 3600
    try:
        for name in os.listdir(dirpath):
            if name.startswith(TMP_PREFIX):
                p = os.path.join(dirpath, name)
                try:
                    if os.path.getmtime(p) < cutoff:
                        os.unlink(p)
                        n += 1
                except OSError:
                    pass
    except OSError:
        pass
    return n
