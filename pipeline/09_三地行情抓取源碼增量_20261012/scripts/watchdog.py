#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外部看门狗 v1 (P0-2 · 排程外部化: 本宿主无 crontab/systemd/launchd 的等价落地)

评审文件2 P0 项: "OS级调度器/独立 supervisor; 每个job heartbeat; 失败推送告警;
验收: 杀死程序后2分钟内拉起"。

本宿主事实: Linux 容器, 无 crontab(前四事故复盘定案), 唯一可行三层防线:
  L1 守护进程内建 try/except 自愈循环(已有)
  L2 本看门狗 watchdog.py 常驻: 每 60s 巡检 scheduler/spcx 两守护, 死亡即
     setsid 拉起 + 告警落盘 (本文件)
  L3 agent heartbeat 调 scripts/health_check.py 体检; 异常时自愈全部三进程
     并向群聊推送告警(唯一对外告警通道)
自我保护: watchdog 自身死亡由 L3 拉起(诚实边界, 无法进程内自证)。

用法: setsid python3 scripts/watchdog.py >> logs/watchdog.out 2>&1 < /dev/null &
状态: config/watchdog_state.json (原子写) | 告警: config/watchdog_alerts.json
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from market_fetcher import atomic_io, storage  # noqa: E402

STATE_PATH = os.path.join(BASE, "config", "watchdog_state.json")
LOCK_PATH = os.path.join(BASE, "config", "watchdog.pid")
ALERTS_PATH = os.path.join(BASE, "config", "watchdog_alerts.json")
INTERVAL_SEC = 60

# 监护对象: (名字, 进程匹配正则, 拉起命令)
# 匹配串锚定 ^/解释器路径+脚本, 排除 bash -lc 包装命令行误命中(单实例判例同理)
DAEMONS = [
    ("scheduler", r"^/home/z/.venv/bin/python3 scripts/scheduler\.py$",
     [sys.executable, "scripts/scheduler.py"]),
    ("spcx_monitor", r"^/home/z/.venv/bin/python3 scripts/spcx_monitor\.py --loop$",
     [sys.executable, "scripts/spcx_monitor.py", "--loop"]),
]


def log(msg: str):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    # 日志追加(日志自身半行可容忍, 不做原子)
    with open(os.path.join(BASE, "logs", "watchdog.log"), "a",
              encoding="utf-8") as f:
        f.write(line + "\n")


def pid_alive(pattern: str) -> int:
    """返回匹配进程的 pid, 无则 0。匹配串含脚本名, 不含 watchdog 自身。"""
    try:
        r = subprocess.run(["pgrep", "-f", pattern],
                           capture_output=True, text=True, timeout=10)
        for pid in (r.stdout or "").split():
            if int(pid) != os.getpid():
                return int(pid)
    except (ValueError, subprocess.SubprocessError):
        pass
    return 0


# E-P0-1: 漏跑判定——守护存活但 _loop_epoch 超时(15min)即告警。
# 依赖 scheduler/spcx 循环级心跳(每30s/60s刷新 state["_loop_epoch"])。
HEARTBEAT_STALE_SEC = 900
DAEMON_STATE = {
    "scheduler": os.path.join(BASE, "config", "scheduler_state.json"),
    "spcx_monitor": os.path.join(BASE, "config", "spcx_monitor_state.json"),
}
_STALE_ALERTED = {}  # 每个"健康→停跳"转换只报一次, 防每60s刷屏


def heartbeat_age(name: str):
    """守护状态文件内 _loop_epoch 的年龄(秒); 无字段/无文件返回 None(不判漏跑)。"""
    p = DAEMON_STATE.get(name)
    if not p:
        return None
    try:
        with open(p, encoding="utf-8") as f:
            epoch = json.load(f).get("_loop_epoch")
        return max(0.0, time.time() - float(epoch)) if epoch else None
    except (OSError, ValueError, TypeError):
        return None


def spawn_daemon(cmd: list, logfile: str) -> int:
    """按守护 SOP 拉起: setsid + 重定向日志 + 脱离会话。"""
    out = open(os.path.join(BASE, "logs", logfile), "ab")
    p = subprocess.Popen(cmd, cwd=BASE, stdout=out, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    return p.pid


def append_alert(alert: dict):
    alerts = []
    try:
        with open(ALERTS_PATH, encoding="utf-8") as f:
            alerts = json.load(f)
    except (OSError, ValueError):
        alerts = []
    alerts.insert(0, alert)
    # 保留最近 200 条
    atomic_io.atomic_write_json(alerts[:200], ALERTS_PATH)
    print(f"[ALERT] {alert['type']} {alert['daemon']}: {alert['detail']}",
          flush=True)


def save_state(state: dict):
    atomic_io.atomic_write_json(state, STATE_PATH)


def single_instance() -> bool:
    """watchdog 自身单实例: fcntl 独占文件锁(进程死亡自动释放, 无残留误判)。

    教训(2026-10-11): 初版用 pgrep -f "watchdog.py", 会命中包装启动命令的
    bash(cmdline 含脚本名) 导致永远误判"已有实例"——禁用 cmd 匹配判单实例。
    """
    import fcntl
    global _LOCK_FD
    try:
        _LOCK_FD = open(LOCK_PATH, "w")
        fcntl.flock(_LOCK_FD, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _LOCK_FD.write(str(os.getpid()))
        _LOCK_FD.flush()
        return True
    except OSError:
        return False


def check_once() -> dict:
    state = {"checked_at": datetime.now().isoformat(timespec="seconds"),
             "daemons": {}}
    for name, pattern, cmd in DAEMONS:
        pid = pid_alive(pattern)
        rec = {"alive": bool(pid), "pid": pid or None}
        if not pid:
            logfile = ("scheduler.out" if name == "scheduler"
                       else "spcx_daemon.out")
            new_pid = spawn_daemon(cmd, logfile)
            time.sleep(2)  # 给拉起进程一点启动时间
            alive = pid_alive(pattern)
            rec.update(restarted_pid=new_pid, alive_after_restart=bool(alive))
            append_alert({
                "type": "daemon_down_restarted",
                "daemon": name,
                "detail": f"死亡→已拉起 pid={new_pid}, 复核alive={bool(alive)}",
                "at": datetime.now().isoformat(timespec="seconds")})
            log(f"DAEMON DOWN: {name} -> 拉起 pid={new_pid} alive={bool(alive)}")
            _STALE_ALERTED.pop(name, None)  # 刚拉起, 心跳从头计
        else:
            age = heartbeat_age(name)
            rec["heartbeat_age_sec"] = round(age, 1) if age is not None else None
            if age is not None and age > HEARTBEAT_STALE_SEC:
                if not _STALE_ALERTED.get(name):  # 状态转换只报一次, 防刷屏
                    append_alert({
                        "type": "job_missed_heartbeat",
                        "daemon": name,
                        "detail": f"存活但心跳停跳 {int(age)}s(>{HEARTBEAT_STALE_SEC}s), 疑漏跑",
                        "at": datetime.now().isoformat(timespec="seconds")})
                    log(f"HEARTBEAT STALE: {name} age={int(age)}s")
                    _STALE_ALERTED[name] = True
            elif age is not None:
                _STALE_ALERTED.pop(name, None)  # 恢复, 允许下次转换再报
        state["daemons"][name] = rec
    save_state(state)
    return state


def main():
    if not single_instance():
        print("watchdog 已有实例在跑, 退出", flush=True)
        return 0
    log(f"watchdog 启动 pid={os.getpid()} interval={INTERVAL_SEC}s "
        f"监控={[d[0] for d in DAEMONS]}")
    while True:
        try:
            check_once()
        except Exception as e:  # noqa: BLE001 - 看门狗绝不退出
            log(f"watchdog 巡检异常(不中断): {e!r}")
            try:
                save_state({"checked_at": datetime.now().isoformat(),
                            "error": repr(e)[:200]})
            except Exception:
                pass
        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    raise SystemExit(main())
