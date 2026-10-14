#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""进程级拉起+漏跑告警演练 (E-P0-1 验收: "杀进程演练: 2分钟内自动拉起; 漏跑15分钟告警触发留痕")

前置: 三进程(scheduler/spcx/watchdog)已在跑且含 _loop_epoch 心跳代码。

方法(四段):
  A. 杀 scheduler    -> 每2s轮询 pgrep, 记录拉起耗时; 硬验收 <=120s。
  B. 杀 spcx_monitor -> 同上。
  C. 漏跑告警留痕    -> 把 scheduler_state["_loop_epoch"] 回拨20分钟(原子写,
     每5s重拨直至告警出现, 期间调度器自身30s刷新会覆盖、演练再拨回), 等待
     watchdog(60s巡检) 在 watchdog_alerts.json 头部落 job_missed_heartbeat
     告警; 硬验收 <=180s 内告警留痕。
  D. 自恢复确认      -> 停止回拨后, scheduler 30s内刷新心跳, watchdog 下一轮
     复核 heartbeat_age_sec 回到正常(报告记录恢复耗时)。
判定: A/B 均 <=120s 拉起 + C 告警留痕 + D 恢复 => PASS。

用法: python3 scripts/drills/process_drill.py
报告: reports/drill_process_<ts>.json
注意: watchdog_alerts.json 为"最新在前"(unshift)。
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
from market_fetcher import atomic_io  # noqa: E402

HKT = timezone(timedelta(hours=8))
ALERTS = os.path.join(BASE, "config", "watchdog_alerts.json")
SCHED_STATE = os.path.join(BASE, "config", "scheduler_state.json")
SCHED_PAT = "scripts/scheduler.py"
SPCX_PAT = "scripts/spcx_monitor.py --loop"


def alive(pattern: str) -> bool:
    r = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
    for pid in (r.stdout or "").split():
        if pid.strip() and int(pid) != os.getpid():
            return True
    return False


def kill_daemon(pattern: str) -> int:
    r = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
    n = 0
    for pid in (r.stdout or "").split():
        try:
            os.kill(int(pid), 9)
            n += 1
        except (ValueError, ProcessLookupError):
            pass
    return n


def head_alerts(n: int = 5) -> list:
    try:
        with open(ALERTS, encoding="utf-8") as f:
            return json.load(f)[:n]
    except Exception:
        return []


def kill_and_measure(pattern: str, label: str, deadline: float = 120.0) -> dict:
    killed = kill_daemon(pattern)
    t0 = time.time()
    pulled, elapsed = False, None
    while time.time() - t0 < deadline:
        if alive(pattern):
            elapsed = round(time.time() - t0, 1)
            pulled = True
            break
        time.sleep(2)
    ok = pulled and elapsed is not None and elapsed <= deadline
    print(f"[{label}] killed={killed} pulled={pulled} elapsed={elapsed}s pass={ok}", flush=True)
    return {"label": label, "killed": killed, "pulled": pulled,
            "elapsed_sec": elapsed, "deadline_sec": deadline, "pass": ok}


def backdate_scheduler_heartbeat(minutes: float = 20.0):
    """回拨 _loop_epoch (read-modify-write, 原子写)。"""
    try:
        with open(SCHED_STATE, encoding="utf-8") as f:
            st = json.load(f)
    except Exception:
        st = {}
    st["_loop_epoch"] = time.time() - minutes * 60
    atomic_io.atomic_write_json(st, SCHED_STATE)


def fresh_heartbeat() -> bool:
    try:
        with open(SCHED_STATE, encoding="utf-8") as f:
            ep = json.load(f).get("_loop_epoch")
        return ep is not None and (time.time() - float(ep)) < 120
    except Exception:
        return False


def main() -> int:
    rA = kill_and_measure(SCHED_PAT, "A.scheduler")
    rB = kill_and_measure(SPCX_PAT, "B.spcx_monitor")
    time.sleep(70)  # 等拉起后的守护完成首轮心跳刷新, 排除A/B余波

    # C. 漏跑告警留痕: 回拨心跳至20分钟前, 等watchdog(60s巡检)告警
    alerts_before = len(json.load(open(ALERTS))) if os.path.exists(ALERTS) else 0
    t0, seen = time.time(), False
    while time.time() - t0 < 180:
        backdate_scheduler_heartbeat(20)   # 调度器30s会覆盖, 持续回拨保证窗口命中
        heads = head_alerts(3)
        if any(a.get("type") == "job_missed_heartbeat" and a.get("daemon") == "scheduler"
               for a in heads):
            seen = True
            break
        time.sleep(5)
    c_elapsed = round(time.time() - t0, 1)
    print(f"[C.stale_alert] seen={seen} elapsed={c_elapsed}s", flush=True)

    # D. 自恢复: 停止回拨, 等调度器刷新心跳(30s一轮)再被watchdog复核
    t1, recovered = time.time(), False
    while time.time() - t1 < 120:
        if fresh_heartbeat():
            recovered = True
            break
        time.sleep(5)
    d_elapsed = round(time.time() - t1, 1)
    print(f"[D.recover] fresh={recovered} elapsed={d_elapsed}s", flush=True)

    report = {
        "drill": "process_pullup_and_missed_run_alert",
        "ts": datetime.now(HKT).isoformat(),
        "spec": "杀守护<=120s自动拉起(watchdog 60s巡检); 心跳停跳>15min落"
                "job_missed_heartbeat告警留痕; 停止回拨后自恢复",
        "A_scheduler": rA, "B_spcx": rB,
        "C_missed_run_alert": {"seen": seen, "elapsed_sec": c_elapsed,
                               "head_alerts": head_alerts(3)},
        "D_recover": {"fresh": recovered, "elapsed_sec": d_elapsed},
        "pass": rA["pass"] and rB["pass"] and seen and recovered,
    }
    out = os.path.join(BASE, "reports", f"drill_process_{datetime.now(HKT):%Y%m%d_%H%M%S}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    atomic_io.atomic_write_json(report, out)
    print(f"报告: {out}", flush=True)
    print("PASS" if report["pass"] else "FAIL", flush=True)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
