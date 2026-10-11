#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI 测试入口 (E-P0-3 · CI 假绿灯修复)

评审原文: "CI 用自订 runner 收集 0 个测试也报绿" —— 本入口修复:
  1. 固定 stock pytest(禁自订 runner/禁自订收集器), 只加 -q 与 --co 两调用;
  2. 先 collect-only 统计收集数, tests_collected < MIN_COLLECTED 即 FAIL
     (防"静默收集 0/删测试仍绿");
  3. 再实跑, failed>0 或 errors>0 即 FAIL;
  4. 报告落 reports/ci_<ts>.json, 退出码 0/1。

约定值 MIN_COLLECTED=50 (E-P1-3 契约测试并入后套件 58 收集, 阈值留余量;
删测试会使 CI 变红)。
用法: python3 scripts/ci/run_tests.py [--min-collected 50]
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HKT = timezone(timedelta(hours=8))


def _run(args):
    return subprocess.run(args, cwd=BASE, capture_output=True, text=True, timeout=600)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-collected", type=int, default=50)
    a = ap.parse_args()
    py = sys.executable
    rep = {"runner": "pytest(stock)", "ts": datetime.now(HKT).isoformat(),
           "min_collected": a.min_collected, "ci_fix": "E-P0-3"}

    co = _run([py, "-m", "pytest", "tests", "--co", "-q"])
    m = re.search(r"(\d+) tests? collected", co.stdout) or \
        re.search(r"collected (\d+) item", co.stdout)
    collected = int(m.group(1)) if m else 0
    rep["tests_collected"] = collected
    rep["collect_stderr_tail"] = co.stderr.strip().splitlines()[-3:] if co.returncode else []
    if co.returncode != 0 or collected < a.min_collected:
        rep["verdict"] = ("FAIL: 收集异常或收集数<{min}".format(min=a.min_collected))
        return _emit(rep)

    run = _run([py, "-m", "pytest", "tests", "-q"])
    out = run.stdout
    rep["passed"] = int(m2.group(1)) if (m2 := re.search(r"(\d+) passed", out)) else 0
    rep["failed"] = int(m3.group(1)) if (m3 := re.search(r"(\d+) failed", out)) else 0
    rep["errors"] = int(m4.group(1)) if (m4 := re.search(r"(\d+) error", out)) else 0
    rep["duration_sec"] = round(run.duration, 2) if hasattr(run, "duration") else None
    rep["pytest_tail"] = out.strip().splitlines()[-1:] if out else []
    ok = run.returncode == 0 and rep["failed"] == 0 and rep["errors"] == 0 \
        and collected >= a.min_collected
    rep["verdict"] = "PASS" if ok else "FAIL"
    return _emit(rep)


def _emit(rep):
    out = os.path.join(BASE, "reports", f"ci_{datetime.now(HKT):%Y%m%d_%H%M%S}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(json.dumps(rep, ensure_ascii=False))
    print(f"报告: {out}")
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
