#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三地行情数据管道 · 每日定时调度器 v1 (scheduler)

调度窗口(北京时间):
  ah_eod     周一~周五 16:40  A/H收盘后 → 三地全量: K线250根(含行业ETF) + 快照 + 宏观P0
  us_morning 周二~周六 06:30  美股收盘后(北京清晨) → 美股段K线(主池+观察池+ETF) + 快照 + 宏观P0
             周一 06:30 轻量轮: 只跑 快照+宏观 (美股上周五数据已于周六清晨日更)
             周日不跑。

可靠性设计:
  - 状态锁 config/scheduler_state.json: 每job每天至多触发一次, 窗口用">="匹配,
    进程重启/错过窗口后补跑, 幂等不重复。
  - K线批次带 sleep=0.6 节流; Finnhub 不健康自动腾讯兜底(runner内置)。
  - 日志 logs/scheduler.log (自动截断); 每轮 manifest 额外带 job/trigger 字段。
  - --verify-two-rounds: 启动即自动触发两轮真实作业(round1=ah_eod全量,
    冷却900s后 round2=us_morning), 轮次manifest含 trigger=scheduler_verify_*,
    结果写 config/scheduler_verify_report.json, 随后进入常驻守护。
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from market_fetcher import runner, us_symbols, storage  # noqa: E402
from market_fetcher.pools import (INDICES, A_POOL, HK_POOL, ETF_POOL,  # noqa: E402
                                  US_WATCH_POOL, SECTOR_ETF_POOL)

STATE_PATH = os.path.join(BASE, "config", "scheduler_state.json")
VERIFY_REPORT = os.path.join(BASE, "config", "scheduler_verify_report.json")
LOG_PATH = os.path.join(BASE, "logs", "scheduler.log")
COOLDOWN_KLINE_SECONDS = 900  # 两轮K线批次最小间隔(防腾讯501风控)


def log(msg: str):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 5 * 1024 * 1024:
            with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
                tail = f.readlines()[-2000:]
            with open(LOG_PATH, "w", encoding="utf-8") as f:
                f.writelines(tail)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_state() -> dict:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state: dict):
    storage.save_json(state, STATE_PATH)


def last_kline_ts(state: dict) -> float:
    return float(state.get("_last_kline_epoch", 0))


def build_us_pools():
    """与 run_all.py 同源逻辑: 映射表验证通过的美股主池/观察池 + 行业ETF(已验证者)。"""
    mapping = us_symbols.load_mapping()
    verified = {m["kline_code"]: m["name_cn"] for m in mapping if m["verified"]}
    us_pool = list(verified.items())
    us_codes = {c for c, _ in us_pool}
    watch_pool = []
    for s, _ in US_WATCH_POOL:
        sym = s.replace("us", "", 1)
        m = next((x for x in mapping if x["symbol"] == sym and x["verified"]), None)
        if m and m["kline_code"] not in us_codes:
            watch_pool.append((m["kline_code"], m["name_cn"]))
    sector_pool = []
    for s, n in SECTOR_ETF_POOL:
        sym = s.replace("us", "", 1)
        m = next((x for x in mapping if x["symbol"] == sym and x["verified"]), None)
        if m:
            sector_pool.append((m["kline_code"], n))
    return us_pool, watch_pool, sector_pool


def _save_tagged(manifest: dict, job: str, trigger: str) -> str:
    manifest["job"] = job
    manifest["trigger"] = trigger
    return runner.save_manifest(manifest)


def job_ah_eod(trigger: str) -> dict:
    """A/H收盘后全量轮: 三地K线(含行业ETF) + 快照 + 宏观。"""
    log(f"JOB ah_eod 触发 trigger={trigger}")
    us_pool, watch_pool, sector_pool = build_us_pools()
    pools = {"指数": INDICES, "A股65": A_POOL, "港股24": HK_POOL, "美股池": us_pool,
             "观察池18": watch_pool, "ETF": ETF_POOL}
    if sector_pool:
        pools["行业ETF"] = sector_pool
    m1 = runner.run_kline_batch(pools, count=250, sleep=0.6)
    p1 = _save_tagged(m1, "ah_eod", trigger)
    log(f"ah_eod K线: ok={m1['ok']} thin={m1['thin']} fail={m1['fail']} -> {p1}")
    r = {"kline": {"ok": m1["ok"], "thin": m1["thin"], "fail": m1["fail"], "manifest": p1}}
    r["snapshot"] = _light_job("ah_eod", trigger)
    return r


def job_us_morning(trigger: str, force: bool = False) -> dict:
    """美股清晨轮: 美股段K线 + 快照 + 宏观。周一自动转轻量轮。"""
    wd = datetime.now().weekday()  # 周一=0
    if wd == 6 and not force:
        log("us_morning: 周日美股无新收盘, 跳过")
        return {"skipped": True}
    full = (wd in (1, 2, 3, 4, 5)) or force  # 周二~周六有美股新收盘
    log(f"JOB us_morning 触发 trigger={trigger} full={full}")
    r = {}
    if full:
        us_pool, watch_pool, sector_pool = build_us_pools()
        pools = {"美股池": us_pool, "观察池18": watch_pool, "ETF": ETF_POOL}
        if sector_pool:
            pools["行业ETF"] = sector_pool
        m1 = runner.run_kline_batch(pools, count=250, sleep=0.6)
        p1 = _save_tagged(m1, "us_morning", trigger)
        log(f"us_morning K线: ok={m1['ok']} thin={m1['thin']} fail={m1['fail']} -> {p1}")
        r["kline"] = {"ok": m1["ok"], "thin": m1["thin"], "fail": m1["fail"], "manifest": p1}
    r["snapshot"] = _light_job("us_morning", trigger)
    return r


def _light_job(job: str, trigger: str) -> dict:
    m2 = runner.run_realtime_snapshot()
    p2 = _save_tagged(m2, job, trigger)
    log(f"{job} 快照: {m2['total']} 条 -> {p2}")
    m3 = runner.run_macro()
    p3 = _save_tagged(m3, job, trigger)
    macro_ok = sum(1 for k in ("us_yields", "cn_yields", "fx", "ah_premium",
                               "sec_filings") if m3.get(k, {}).get("ok"))
    fred_ok = sum(1 for v in m3.get("fred_p0", {}).values() if v.get("ok"))
    log(f"{job} 宏观: 直接通道ok={macro_ok}/5 FRED ok={fred_ok}/3 -> {p3}")
    return {"snapshot_total": m2["total"], "snapshot_manifest": p2,
            "macro_manifest": p3, "macro_direct_ok": macro_ok, "macro_fred_ok": fred_ok}


def run_job(job: str, trigger: str, state: dict) -> dict:
    state["_last_kline_epoch"] = time.time()
    # 幂等锁: 验证轮/手动轮同样登记当日已跑, 防止 daemon_loop 同日重复触发
    state.setdefault(job, {})["last_run_date"] = f"{datetime.now():%Y-%m-%d}"
    state[job]["last_run_at"] = datetime.now().isoformat()
    save_state(state)
    if job == "ah_eod":
        return job_ah_eod(trigger)
    return job_us_morning(trigger)


def verify_two_rounds(state: dict):
    """连续两轮自动运行验证: round1=ah_eod全量 → 冷却 → round2=us_morning。"""
    log("=== 验证模式启动: 连续两轮自动运行 (round1 ah_eod → 900s冷却 → round2 us_morning) ===")
    report = {"started_at": datetime.now().isoformat(), "round1": None, "round2": None}
    try:
        report["round1"] = run_job("ah_eod", "scheduler_verify_round1", state)
    except Exception as e:  # noqa: BLE001
        log(f"round1 异常: {e!r}")
        report["round1"] = {"error": repr(e)}
    save_state(state)
    log(f"round1 完成, 冷却 {COOLDOWN_KLINE_SECONDS}s 后触发 round2 ...")
    time.sleep(COOLDOWN_KLINE_SECONDS)
    try:
        report["round2"] = run_job("us_morning", "scheduler_verify_round2", state)
    except Exception as e:  # noqa: BLE001
        log(f"round2 异常: {e!r}")
        report["round2"] = {"error": repr(e)}
    report["finished_at"] = datetime.now().isoformat()
    ok1 = isinstance(report["round1"], dict) and report["round1"].get("kline", {}).get("fail", 1) == 0
    ok2 = isinstance(report["round2"], dict) and (
        report["round2"].get("skipped") or
        report["round2"].get("kline", {}).get("fail", 1) == 0)
    report["result"] = "PASS" if (ok1 and ok2) else "CHECK_NEEDED"
    storage.save_json(report, VERIFY_REPORT)
    log(f"=== 两轮验证结束: result={report['result']} 报告 -> {VERIFY_REPORT} ===")


def daemon_loop(state: dict):
    log("进入常驻守护: ah_eod=工作日16:40 | us_morning=每日06:30(周日跳过,周 lightweight)")
    while True:
        try:
            now = datetime.now()
            today = f"{now:%Y-%m-%d}"
            # ah_eod: 周一~周五 16:40
            if now.weekday() <= 4 and now.hour * 60 + now.minute >= 16 * 60 + 40 \
                    and state.get("ah_eod", {}).get("last_run_date") != today:
                state.setdefault("ah_eod", {})["last_run_date"] = today
                state["ah_eod"]["last_run_at"] = now.isoformat()
                save_state(state)
                run_job("ah_eod", "scheduler", state)
            # us_morning: 每日 06:30 (周日job内自跳)
            if now.hour * 60 + now.minute >= 6 * 60 + 30 \
                    and state.get("us_morning", {}).get("last_run_date") != today:
                state.setdefault("us_morning", {})["last_run_date"] = today
                state["us_morning"]["last_run_at"] = now.isoformat()
                save_state(state)
                run_job("us_morning", "scheduler", state)
        except Exception as e:  # noqa: BLE001
            log(f"daemon_loop 异常(不中断): {e!r}")
            save_state(state)
        # E-P0-1 循环级心跳(评审"每个job heartbeat"): 每轮(30s)刷新 _loop_epoch,
        # watchdog 以此判定"守护存活但漏跑"(>900s 告警 job_missed_heartbeat)。
        state["_loop_epoch"] = time.time()
        save_state(state)
        time.sleep(30)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-two-rounds", action="store_true",
                    help="启动即连续自动跑两轮验证, 然后进入守护")
    args = ap.parse_args()
    state = load_state()
    log(f"scheduler 启动 pid={os.getpid()} verify={args.verify_two_rounds}")
    if args.verify_two_rounds:
        verify_two_rounds(state)
    daemon_loop(state)


if __name__ == "__main__":
    main()
