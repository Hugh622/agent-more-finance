#!/bin/bash
# 看门狗: round2 验证报告落盘后, 停旧调度器(旧代码无幂等登记) -> 补写当日幂等锁 -> 新代码重启守护
cd /home/z/my-project/shared/全栈工具v1_三地行情抓取
LOG=/home/z/my-project/agents/6aa5076624bdc41e7983913b/watchdog.log
echo "[$(date '+%F %T')] watchdog 启动, 等待 scheduler_verify_report.json ..." >> "$LOG"
for i in $(seq 1 400); do
  [ -f config/scheduler_verify_report.json ] && break
  sleep 3
done
if [ ! -f config/scheduler_verify_report.json ]; then
  echo "[$(date '+%F %T')] 等待超时, 退出" >> "$LOG"
  exit 1
fi
echo "[$(date '+%F %T')] 验证报告已落盘, 停旧进程 3912 ..." >> "$LOG"
kill 3912 2>/dev/null
sleep 2
/home/z/.venv/bin/python3 - <<'PYEOF' >> "$LOG" 2>&1
import json, time
p = "config/scheduler_state.json"
try:
    state = json.load(open(p))
except Exception:
    state = {}
state["_last_kline_epoch"] = state.get("_last_kline_epoch", time.time())
for job in ("ah_eod", "us_morning"):
    state.setdefault(job, {})["last_run_date"] = "2026-09-12"
    state[job]["last_run_at"] = "2026-09-12T20:45:00"
json.dump(state, open(p, "w"), ensure_ascii=False, indent=2)
print("state 幂等锁已补写:", json.dumps(state, ensure_ascii=False))
PYEOF
setsid nohup /home/z/.venv/bin/python3 scripts/scheduler.py >> logs/scheduler.out 2>&1 < /dev/null &
echo "[$(date '+%F %T')] 新调度器已拉起 pid=$!" >> "$LOG"
sleep 5
ps aux | grep "scripts/scheduler.py" | grep -v grep >> "$LOG" 2>&1
tail -3 logs/scheduler.log >> "$LOG" 2>&1
echo "[$(date '+%F %T')] watchdog 完成" >> "$LOG"
