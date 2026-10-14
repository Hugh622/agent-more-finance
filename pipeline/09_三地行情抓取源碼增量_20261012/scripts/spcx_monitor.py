#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPCX 被动买盘事件监控 · 量价基线日更管道 v1 (spcx_monitor)

任务来源(群管理员 2026-09-15 布置 / 2026-09-16 验收):
  usSPCX.OQ 与 usQQQ.OQ 日线(价格、成交量)接入每日定时拉取并存档,
  产过量价基线监控表(上市以来相对 QQQ 累计表现、量能衰减率),
  供 9/21 纳指100权重生效前后判断被动买盘是否现身。

产出:
  1) 日线存档(追加式, 按日期去重、新抓取覆盖旧值):
     /shared/market_data/daily/usspcx_oq.csv
     /shared/market_data/daily/usqqq_oq.csv
  2) 机器可读基线表(每次覆盖):
     /shared/market_data/spcx_monitor/spcx_baseline_monitor_latest.csv
  3) 群用日报(markdown, 按日期留档):
     /shared/market_data/spcx_monitor/SPCX量价基线监控_YYYYMMDD.md

调度:
  --loop 守护模式: 周二~周六(北京) 06:50 起检查, 每日一次(状态锁幂等),
     覆盖美股常规收盘后时点(北京清晨); 错过窗口由当日晚间补跑窗口兜底。
  --force 手动立即跑一次(无视当日锁), 用于补数与验收。

口径说明:
  - 累计表现基期 = SPCX 上市首日收盘(2026-06-12); rel_cum_pp = SPCX累计% - QQQ累计%。
  - 量能基线 = SPCX 上市首 5 个交易日日均成交量; 衰减率 = 近5日日均量 / 基线。
  - 事件标注(群内已双源核验口径): 2026-09-12 权重消息公开(纳指100 pro forma
    1.28%→2.82%); 2026-09-15~18 证伪观察窗口; 2026-09-21 权重正式生效。
  - 数据源: 腾讯 fqkline 行情通道(L2 第三方可靠来源), 复用 market_fetcher 封装。
"""
import argparse
import io
import json
import os
import sys
import time
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import pandas as pd  # noqa: E402

from market_fetcher import storage, tencent_api  # noqa: E402
from market_fetcher import atomic_io  # noqa: E402

DATA_DIR = "/home/z/my-project/shared/market_data"
MONITOR_DIR = os.path.join(DATA_DIR, "spcx_monitor")
STATE_PATH = os.path.join(BASE, "config", "spcx_monitor_state.json")
LOG_PATH = os.path.join(BASE, "logs", "spcx_monitor.log")

SPCX = {"code": "usSPCX.OQ", "name": "SpaceX ETF", "archive": os.path.join(DATA_DIR, "daily", "usspcx_oq.csv")}
QQQ = {"code": "usQQQ.OQ", "name": "纳指100ETF", "archive": os.path.join(DATA_DIR, "daily", "usqqq_oq.csv")}

TRIGGER_HOUR, TRIGGER_MIN = 6, 50          # 北京时间 周二~周六 06:50
# 观察清单口径(群内已核验): SPCX 白盒区间与事件日期
WHITE_BOX = (145.0, 153.0)
ANN_DATE = "2026-09-12"                    # 权重消息公开日(首个交易日反应 9/14)
FAKE_WINDOW = ("2026-09-15", "2026-09-18") # 证伪观察窗口
EFFECT_DATE = "2026-09-21"                 # 权重正式生效日

CSV_COLS = ["date", "open", "high", "low", "close", "volume", "amount_raw",
            "code", "market", "name", "fetched_at", "source", "source_level", "grade"]


def log(msg: str):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 2 * 1024 * 1024:
            with open(LOG_PATH, encoding="utf-8", errors="ignore") as f:
                tail = f.readlines()[-1000:]
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


def pull_and_archive(spec: dict, fetched_at: str, count: int = 250) -> dict:
    """拉取单只美股日线并与存档合并(新值覆盖同日旧值), 返回合并结果摘要。"""
    df = tencent_api.fetch_kline(spec["code"], count=count)
    if df is None or df.empty:
        return {"code": spec["code"], "ok": False, "rows": 0, "new_rows": 0, "last_date": None}
    df = df.rename(columns={})  # RAW_COLS: date,open,close,high,low,volume,amount_raw
    df = df[["date", "open", "high", "low", "close", "volume", "amount_raw"]]
    df["code"], df["market"], df["name"] = spec["code"], "US", spec["name"]
    source = storage.stamp(storage.SOURCE_TENCENT_KLINE, fetched_at)
    df = storage.add_meta(df, fetched_at, source,
                          storage.LEVEL_THIRD_PARTY, "行情商(腾讯)-实测稳定")[CSV_COLS]
    # 与存档合并: 存档旧日期行保留(仅补齐), 同日期行以本次抓取为准
    old_last, new_last = None, str(df["date"].max().date())
    if os.path.exists(spec["archive"]):
        try:
            old = pd.read_csv(spec["archive"], encoding="utf-8-sig")
            old_last = str(pd.to_datetime(old["date"]).max().date())
            merged = pd.concat([old, df], ignore_index=True)
            merged = merged.drop_duplicates(subset="date", keep="last").sort_values("date")
        except Exception:
            merged = df
    else:
        merged = df
    # P0-1: 原子写入(tmp+fsync+rename), 归档永不半档; 列结构与原 to_csv 完全一致
    buf = io.BytesIO()
    merged.to_csv(buf, index=False, encoding="utf-8-sig")
    atomic_io.atomic_write_bytes(spec["archive"], buf.getvalue())
    new_rows = 0 if old_last is None else int((pd.to_datetime(df["date"]).dt.date
                                               > pd.to_datetime(old_last).date()).sum())
    return {"code": spec["code"], "ok": True, "rows": len(merged),
            "new_rows": new_rows, "last_date": new_last,
            "prev_last_date": old_last or "(新建存档)"}


def build_monitor(fetched_at: str) -> dict:
    """构建量价基线监控表(CSV + MD)。返回摘要指标 dict。"""
    sp = pd.read_csv(SPCX["archive"], encoding="utf-8-sig")
    qq = pd.read_csv(QQQ["archive"], encoding="utf-8-sig")
    sp["date"] = pd.to_datetime(sp["date"]).dt.date
    qq["date"] = pd.to_datetime(qq["date"]).dt.date
    m = sp[["date", "open", "high", "low", "close", "volume"]].merge(
        qq[["date", "close", "volume"]], on="date", suffixes=("_spcx", "_qqq"))
    m = m.sort_values("date").reset_index(drop=True)

    m["spcx_ret_pct"] = m["close_spcx"].pct_change() * 100
    m["qqq_ret_pct"] = m["close_qqq"].pct_change() * 100
    base_close_s, base_close_q = m.loc[0, "close_spcx"], m.loc[0, "close_qqq"]
    m["spcx_cum_pct"] = (m["close_spcx"] / base_close_s - 1) * 100
    m["qqq_cum_pct"] = (m["close_qqq"] / base_close_q - 1) * 100
    m["rel_cum_pp"] = m["spcx_cum_pct"] - m["qqq_cum_pct"]
    first_week_base = m["volume_spcx"].head(5).mean()
    m["spcx_vol_x_firstwk"] = m["volume_spcx"] / first_week_base
    m["spcx_vol5d_x_firstwk"] = m["volume_spcx"].rolling(5).mean() / first_week_base

    def note(d):
        ds = str(d)
        if ds == str(m.loc[0, "date"]):
            return "上市首日(基期)"
        if ds == ANN_DATE:
            return "权重消息公开(非交易日,反应看9/14)"
        if FAKE_WINDOW[0] <= ds <= FAKE_WINDOW[1]:
            return "证伪观察窗口" + ("(首日)" if ds == FAKE_WINDOW[0] else "")
        if ds == EFFECT_DATE:
            return "权重正式生效日"
        return ""

    m["event_note"] = m["date"].map(note)

    out_cols = {"date": "date", "open": "spcx_open", "high": "spcx_high", "low": "spcx_low",
                "close_spcx": "spcx_close", "spcx_ret_pct": "spcx_ret_pct",
                "close_qqq": "qqq_close", "qqq_ret_pct": "qqq_ret_pct",
                "spcx_cum_pct": "spcx_cum_pct", "qqq_cum_pct": "qqq_cum_pct",
                "rel_cum_pp": "rel_cum_pp", "volume_spcx": "spcx_volume",
                "spcx_vol_x_firstwk": "spcx_vol_x_firstwk",
                "spcx_vol5d_x_firstwk": "spcx_vol5d_x_firstwk",
                "volume_qqq": "qqq_volume", "event_note": "event_note"}
    out = m[list(out_cols)].rename(columns=out_cols)
    latest_csv = os.path.join(MONITOR_DIR, "spcx_baseline_monitor_latest.csv")
    storage.save_csv(out, latest_csv, fetched_at,
                     storage.stamp(storage.SOURCE_TENCENT_KLINE, fetched_at) + "; 基线口径见 scripts/spcx_monitor.py",
                     storage.LEVEL_THIRD_PARTY, "行情商(腾讯)-派生指标")

    # ---- 摘要指标 ----
    last = m.iloc[-1]
    d_str = m["date"].astype(str)
    post = m[d_str >= ANN_DATE]  # 消息公开后(9/14起)
    pre20 = m[d_str < ANN_DATE].tail(20)
    ann_base = m[d_str == "2026-09-11"]
    vol5d = m["volume_spcx"].tail(5).mean()
    white_lo, white_hi = WHITE_BOX
    summary = {
        "data_through": str(last["date"]),
        "sessions_listed": len(m),
        "listing_date": str(m.loc[0, "date"]),
        "spcx_last_close": round(float(last["close_spcx"]), 2),
        "spcx_cum_pct": round(float(last["spcx_cum_pct"]), 2),
        "qqq_cum_pct": round(float(last["qqq_cum_pct"]), 2),
        "rel_cum_pp": round(float(last["rel_cum_pp"]), 2),
        "firstwk_avg_vol": round(float(first_week_base) / 1e6, 1),      # 百万股
        "vol5d_avg": round(float(vol5d) / 1e6, 1),
        "vol_decay_pct": round(float(vol5d / first_week_base) * 100, 1),  # %
        "vol5d_ma_x_firstwk": round(float(last["spcx_vol5d_x_firstwk"]), 3),
        "post_ann_ret_pct": round(float(post["spcx_ret_pct"].sum()), 2) if len(post) else None,
        "post_ann_avgvol_m": round(float(post["volume_spcx"].mean()) / 1e6, 1) if len(post) else None,
        "pre20_avgvol_m": round(float(pre20["volume_spcx"].mean()) / 1e6, 1) if len(pre20) else None,
        "post_pre_vol_ratio": round(float(post["volume_spcx"].mean() / pre20["volume_spcx"].mean()), 2)
                              if len(post) and len(pre20) else None,
        "ann_base_close": round(float(ann_base["close_spcx"].iloc[0]), 2) if len(ann_base) else None,
        "white_box": list(WHITE_BOX),
        "in_white_box": bool(white_lo <= float(last["close_spcx"]) <= white_hi),
        "fake_window_progress": f"{sum(1 for d in d_str if FAKE_WINDOW[0] <= d <= FAKE_WINDOW[1])}/4 交易日",
    }
    return {"summary": summary, "table": out}


def write_md(summary: dict, table: pd.DataFrame, fetched_at: str) -> str:
    s = summary
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(MONITOR_DIR, f"SPCX量价基线监控_{datetime.now():%Y%m%d}.md")
    detail = table.tail(12).copy()
    for c in ("spcx_volume", "qqq_volume"):
        detail[c] = (detail[c] / 1e6).round(1)
    detail["spcx_ret_pct"] = detail["spcx_ret_pct"].round(2)
    detail["qqq_ret_pct"] = detail["qqq_ret_pct"].round(2)
    detail["spcx_cum_pct"] = detail["spcx_cum_pct"].round(2)
    detail["qqq_cum_pct"] = detail["qqq_cum_pct"].round(2)
    detail["rel_cum_pp"] = detail["rel_cum_pp"].round(2)
    detail["spcx_vol_x_firstwk"] = detail["spcx_vol_x_firstwk"].round(2)
    md = f"""# SPCX 量价基线监控表（数据截至 {s['data_through']} 收盘）

> 生成: {today} {fetched_at[11:16]} 北京时间 ｜ 管道: `scripts/spcx_monitor.py`(腾讯行情通道 L2) ｜
> 上市日 {s['listing_date']}，已录 {s['sessions_listed']} 个交易日 ｜ 明细CSV: `spcx_monitor/spcx_baseline_monitor_latest.csv`

## 一、基线指标汇总

| 指标 | 数值 | 口径 |
|---|---|---|
| SPCX 最新收盘 | {s['spcx_last_close']} | 白盒区间 {s['white_box'][0]:.0f}-{s['white_box'][1]:.0f}：{'✅ 区间内' if s['in_white_box'] else '⚠️ 已跌破/超出区间'} |
| SPCX 上市以来累计 | {s['spcx_cum_pct']:+.1f}% | 基期=上市首日收盘 |
| QQQ 同期累计 | {s['qqq_cum_pct']:+.1f}% | 同基期 |
| **相对 QQQ 超额** | **{s['rel_cum_pp']:+.1f}pp** | SPCX累计 − QQQ累计 |
| 首周量能基线 | {s['firstwk_avg_vol']}M 股/日 | 上市首5个交易日日均量 |
| 近5日日均量 | {s['vol5d_avg']}M 股/日 | — |
| **量能衰减率** | **{s['vol_decay_pct']:.0f}%**（{s['vol5d_ma_x_firstwk']}×基线） | 近5日日均 / 首周基线 |
| 消息后价格反应 | {s['post_ann_ret_pct']:+.1f}% | 9/12 消息公开后累计（基点 {s['ann_base_close']}，9/11收盘） |
| 消息后量能反应 | {s['post_pre_vol_ratio']}× | 消息后日均量 {s['post_ann_avgvol_m']}M vs 消息前20日 {s['pre20_avgvol_m']}M |
| 证伪窗口进度 | {s['fake_window_progress']} | 9/15-18 量价无反应即降级为短脉冲 |

## 二、近12个交易日明细

| 日期 | SPCX收 | 日涨跌% | SPCX量(M) | 量/首周基线 | QQQ收 | QQQ日% | SPCX累计% | QQQ累计% | 相对pp | 事件 |
|---|---|---|---|---|---|---|---|---|---|---|
""" + "\n".join(
        f"| {r['date']} | {r['spcx_close']:.2f} | {r['spcx_ret_pct']:+.2f} | {r['spcx_volume']:.1f} | "
        f"{r['spcx_vol_x_firstwk']:.2f}× | {r['qqq_close']:.2f} | {r['qqq_ret_pct']:+.2f} | "
        f"{r['spcx_cum_pct']:+.2f} | {r['qqq_cum_pct']:+.2f} | {r['rel_cum_pp']:+.2f} | {r['event_note'] or '—'} |"
        for _, r in detail.iterrows()
    ) + f"""

## 三、事件坐标（观察清单口径，群内已双源核验）

- **2026-09-12** 权重消息公开：纳指100 pro forma 权重 1.28%→2.82%（彭博），约 $15.5B 被动 rebalance 买盘预期；
- **2026-09-15 ~ 09-18** 证伪观察窗口：量价无反应即降级为短脉冲（证伪线由量化组 B 课题设定）；
- **2026-09-21** 权重正式生效日（rebalance 买盘窗口收口）。

## 四、口径与管道说明

- 累计表现基期 = SPCX 上市首日({s['listing_date']})收盘；复权口径 qfq；量能为原始成交量；
- 日线存档(追加式去重)：`market_data/daily/usspcx_oq.csv`、`usqqq_oq.csv`；
- 定时调度：北京周二~周六 06:50 守护进程自动拉取（美股收盘后），当日锁幂等，手动 `--force` 可补数；
- 下一版更新：明晨例行拉取后自动含 9/16 美股收盘数据（9/21 生效日前每日更新一版）。

（本表为数据监控产出，不构成投资建议）
"""
    atomic_io.atomic_write_text(path, md)
    return path


def run_job(force: bool = False, trigger: str = "manual") -> dict:
    state = load_state()
    today = f"{datetime.now():%Y-%m-%d}"
    if not force and state.get("last_run_date") == today:
        log(f"job skip: {today} 已跑过(state锁), trigger={trigger}")
        return {"skipped": True, "last_run_date": state.get("last_run_date")}
    ts = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
    log(f"JOB spcx_daily 触发 trigger={trigger} force={force}")
    r_spcx = pull_and_archive(SPCX, ts)
    time.sleep(1.5)
    r_qqq = pull_and_archive(QQQ, ts)
    result = {"trigger": trigger, "spcx": r_spcx, "qqq": r_qqq}
    if r_spcx["ok"] and r_qqq["ok"]:
        mon = build_monitor(ts)
        result["summary"] = mon["summary"]
        result["md_path"] = write_md(mon["summary"], mon["table"], ts)
        state.update({"last_run_date": today, "last_run_at": datetime.now().isoformat(),
                      "last_data_through": mon["summary"]["data_through"],
                      "last_result": "OK"})
        log(f"OK: 存档 spcx={r_spcx['rows']}行(+{r_spcx['new_rows']}) qqq={r_qqq['rows']}行"
            f"(+{r_qqq['new_rows']}), 数据截至 {mon['summary']['data_through']}, 表 -> {result['md_path']}")
    else:
        state.update({"last_run_date": today, "last_run_at": datetime.now().isoformat(),
                      "last_result": f"FAIL spcx_ok={r_spcx['ok']} qqq_ok={r_qqq['ok']}"})
        log(f"FAIL: spcx_ok={r_spcx['ok']} qqq_ok={r_qqq['ok']} (当日锁已记, 明晨窗口自动重试或手动--force)")
    storage.save_json(state, STATE_PATH)
    result["state"] = state
    return result


def daemon_loop():
    log("spcx_monitor 守护启动: 周二~周六 06:50 每日一拉(状态锁幂等)")
    while True:
        try:
            now = datetime.now()
            wd = now.weekday()  # 周一=0; 周二~周六=1..5
            if wd in (1, 2, 3, 4, 5) and (now.hour, now.minute) >= (TRIGGER_HOUR, TRIGGER_MIN):
                run_job(force=False, trigger="daemon")
        except Exception as e:  # noqa: BLE001
            log(f"daemon_loop 异常(不中断): {e!r}")
        # E-P0-1 循环级心跳: 每轮(60s)刷新 _loop_epoch, watchdog 15min 漏跑判据
        try:
            try:
                with open(STATE_PATH, encoding="utf-8") as f:
                    hb = json.load(f)
            except (OSError, ValueError):
                hb = {}
            hb["_loop_epoch"] = time.time()
            storage.save_json(hb, STATE_PATH)
        except Exception:
            pass  # 心跳失败不影响主流程(watchdog 侧死亡检测仍有效)
        time.sleep(60)


def main():
    ap = argparse.ArgumentParser(description="SPCX 量价基线日更监控")
    ap.add_argument("--force", action="store_true", help="无视当日锁立即跑一次")
    ap.add_argument("--loop", action="store_true", help="守护模式")
    args = ap.parse_args()
    if args.loop:
        daemon_loop()
        return
    r = run_job(force=args.force, trigger="cli")
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
