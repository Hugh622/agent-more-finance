#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""管线健康体检 v1 (P0-2 · agent heartbeat 的标准检查动作)

用法: python3 scripts/health_check.py [--json]
  exit 0=OK  1=WARN(需观察)  2=FAIL(需自愈+告警)
agent heartbeat 流程: 跑本脚本 → exit<2 静默; exit=2 → 按 runbook 自愈
(kill 残尸→重启三守护) 并向群聊告警(@群管理员)。

检查项:
  1. 三守护进程存活: watchdog / scheduler / spcx_monitor(--loop)
  2. 数据新鲜度: shared/market_data/manifest 最新批次年龄
     (us_morning 每日06:30, 周日跳过 → 阈值 36h; ah_eod 工作日16:40 → 阈值 96h)
  3. 守护日志新鲜度: scheduler.log / spcx_monitor.log 最近写入 < 12h(常驻每30s轮询)
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.path.join(BASE, "logs")
MANIFEST_GLOB = "/home/z/my-project/shared/market_data/manifest/run_*.json"

CHECKS = []


def check(name, status, detail, **extra):
    CHECKS.append({"check": name, "status": status, "detail": detail, **extra})


def proc_alive(pattern: str) -> int:
    try:
        r = subprocess.run(["pgrep", "-f", pattern],
                           capture_output=True, text=True, timeout=10)
        return max([int(x) for x in (r.stdout or "").split()] or [0])
    except (ValueError, subprocess.SubprocessError):
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    # 1. 三守护进程
    for name, pattern in [("watchdog", "watchdog.py"),
                          ("scheduler", "scheduler.py"),
                          ("spcx_monitor", "spcx_monitor.py --loop")]:
        pid = proc_alive(pattern)
        check(f"proc_{name}", "ok" if pid else "fail",
              f"pid={pid}" if pid else "进程不在", pid=pid)

    # 2. 数据新鲜度
    mans = sorted(glob.glob(MANIFEST_GLOB), key=os.path.getmtime)
    if not mans:
        check("data_freshness", "fail", "无任何 manifest 批次")
    else:
        latest = mans[-1]
        age_h = (time.time() - os.path.getmtime(latest)) / 3600
        status = "ok" if age_h <= 36 else ("warn" if age_h <= 96 else "fail")
        check("data_freshness", status,
              f"最新批次 {os.path.basename(latest)} 年龄 {age_h:.1f}h",
              latest=os.path.basename(latest), age_hours=round(age_h, 1))

    # 3. 守护日志新鲜度(常驻轮询每30s应持续写入或至少启动有记录)
    for lf, who in [("scheduler.log", "scheduler"),
                    ("spcx_monitor.log", "spcx_monitor")]:
        p = os.path.join(LOGS, lf)
        if not os.path.exists(p):
            check(f"log_{who}", "warn", "日志文件不存在")
            continue
        age_h = (time.time() - os.path.getmtime(p)) / 3600
        status = "ok" if age_h < 12 else ("warn" if age_h < 36 else "fail")
        check(f"log_{who}", status, f"最后写入 {age_h:.1f}h 前")

    worst = "ok"
    for c in CHECKS:
        order = {"ok": 0, "warn": 1, "fail": 2}
        if order[c["status"]] > order[worst]:
            worst = c["status"]
    result = {"checked_at": datetime.now().isoformat(timespec="seconds"),
              "overall": worst, "checks": CHECKS}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for c in CHECKS:
            print(f"[{c['status'].upper():4}] {c['check']}: {c['detail']}")
        print(f"OVERALL: {worst}")
    return {"ok": 0, "warn": 1, "fail": 2}[worst]


if __name__ == "__main__":
    raise SystemExit(main())
