#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kill 验收演练 (P0-1 · 评审文件2验收标准: "人为 kill 写档进程 100 次, 不产生可见半档")

方法:
  父进程循环 100 轮, 每轮 spawn 一个 worker 子进程 → 随机延时 → SIGKILL(模拟任意
  时刻崩溃, 覆盖 写入中/写入后/批次标记前后) → 立即校验目标档:
    ① 目标 JSON 必须可解析(旧完整档 或 新完整档, 永不半档);           [硬验收]
    ② 档内嵌入 sha256 与实际内容一致(强校验, 不止语法完整);            [硬验收]
    ③ `_SUCCESS` 批次三态(complete/in_progress/corrupted)统计与审查线索。
判定: 硬验收①② 100 轮全过 => PASS(评审原文"不产生可见半档"); 任一失败 => FAIL。
批次标记③为覆盖写管道的固有窗口(target 与 _SUCCESS 两次原子写之间被 kill 属
预期中间态, verify_batch 以 mtime 判 in_progress; 同秒精度边界下矛盾组合记
warning 供人工审查, 不作 FAIL)。

用法: python3 scripts/drills/kill_drill.py [--rounds 100] [--payload-kb 2048]
报告: reports/drill_kill_<ts>.json
"""
import argparse
import hashlib
import json
import os
import random
import signal
import subprocess
import sys
import time
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
from market_fetcher import atomic_io  # noqa: E402

WORKER_SRC = r'''
import json, os, sys, time, hashlib, random
sys.path.insert(0, os.environ["PIPE_BASE"])
from market_fetcher import atomic_io
target, kb = sys.argv[1], int(sys.argv[2])
seq = 0
# 先确保存在一个完整基线档(模拟线上已有历史数据)
base = {"seq": -1, "kb": kb,
        "data": "x" * (kb * 1024),
        "sha256": hashlib.sha256(("x" * (kb * 1024)).encode()).hexdigest()}
atomic_io.atomic_write_json(base, target)
random.seed(os.getpid())
while True:
    seq += 1
    body = "".join(random.choices("abcdefgh0123456789", k=kb * 1024))
    payload = {"seq": seq, "kb": kb, "data": body,
               "sha256": hashlib.sha256(body.encode()).hexdigest()}
    atomic_io.atomic_write_json(payload, target)
    atomic_io.write_batch_success(os.path.dirname(target), [target], seq=seq)
    time.sleep(0.01)
'''


def check_target(target: str) -> dict:
    try:
        with open(target, encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, ValueError) as e:
        return {"ok": False, "reason": f"unparsable: {e!r}"}
    body_sha = hashlib.sha256(payload["data"].encode()).hexdigest()
    if body_sha != payload["sha256"]:
        return {"ok": False, "reason": "embedded sha256 mismatch (内容半档)"}
    return {"ok": True, "seq": payload["seq"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=100)
    ap.add_argument("--payload-kb", type=int, default=2048)
    args = ap.parse_args()

    drill_dir = os.path.join(BASE, "reports", "drill_tmp_kill")
    os.makedirs(drill_dir, exist_ok=True)
    target = os.path.join(drill_dir, "target.json")
    worker = os.path.join(drill_dir, "_worker.py")
    with open(worker, "w", encoding="utf-8") as f:
        f.write(WORKER_SRC)

    # 预写完整基线档(模拟生产常态: 线上已有昨档), kill 永远打在"有旧档可读"的场景
    body = "x" * (args.payload_kb * 1024)
    atomic_io.atomic_write_json(
        {"seq": -1, "kb": args.payload_kb, "data": body,
         "sha256": hashlib.sha256(body.encode()).hexdigest()}, target)

    env = {**os.environ, "PIPE_BASE": BASE}
    results, fails, warnings = [], [], []
    for rnd in range(1, args.rounds + 1):
        proc = subprocess.Popen([sys.executable, worker, target, str(args.payload_kb)],
                                env=env, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        # worker 冷启动 import ~0.8s, 窗口取 0.85~1.6s 使 kill 必落在写入循环内
        # (单次原子写 ~15ms, 窗口内覆盖 tmp写入/fsync/rename/_SUCCESS 各阶段)
        time.sleep(random.uniform(0.85, 1.6))
        try:
            proc.send_signal(signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
        chk = check_target(target)
        batch = atomic_io.verify_batch(drill_dir)
        rec = {"round": rnd, "target_ok": chk["ok"], "seq": chk.get("seq"),
               "batch_state": ("complete" if batch.get("complete") else
                               "in_progress" if batch.get("in_progress") else
                               "corrupted" if batch.get("corrupted") else
                               "no_marker" if not batch.get("batch_present") else "other"),
               "mismatches": batch.get("mismatches", [])}
        # 硬验收 = 单档完整性(评审原文"不产生可见半档")
        if not chk["ok"]:
            rec["verdict"] = "FAIL"
            fails.append(rec)
        else:
            # 批次三态统计; 矛盾组合(数据完整但批次判corrupted)记warning供人工审查
            if rec["batch_state"] == "corrupted":
                rec["warning"] = "批次标记判corrupted但数据档完整(mtime同秒精度边界?), 人工审查"
                warnings.append(rec)
            rec["verdict"] = "PASS"
        results.append(rec)
        if rnd % 20 == 0:
            print(f"  ... {rnd}/{args.rounds} 轮, 累计FAIL={len(fails)}", flush=True)

    report = {
        "drill": "kill_drill(原子写入验收)",
        "standard": "评审文件2: 人为kill写档进程100次, 不产生可见半档",
        "rounds": args.rounds, "payload_kb": args.payload_kb,
        "fail_count": len(fails),
        "batch_states": {s: sum(1 for r in results if r["batch_state"] == s)
                         for s in ("complete", "in_progress", "corrupted", "no_marker")},
        "warning_count": len(warnings),
        "result": "PASS" if not fails else "FAIL",
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "fails": fails,
        "warnings": warnings,
    }
    out = os.path.join(BASE, "reports",
                       f"drill_kill_{datetime.now():%Y%m%d_%H%M%S}.json")
    atomic_io.atomic_write_json(report, out)
    # 清理演练临时目录
    for p in (worker, target, os.path.join(drill_dir, "_SUCCESS")):
        try:
            os.unlink(p)
        except OSError:
            pass
    try:
        os.rmdir(drill_dir)
    except OSError:
        pass
    print(f"=== kill演练 {args.rounds} 轮: {report['result']} "
          f"(FAIL={len(fails)}) 报告 -> {out} ===")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
