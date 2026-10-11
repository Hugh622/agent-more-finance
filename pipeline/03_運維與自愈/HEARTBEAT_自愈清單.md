# Heartbeat Checklist

## Scheduled Sweep（一次性任务）
- NEXT_SWEEP_UTC: 2026-09-29T21:30:00Z（= 05:30 CST）
- 到点执行：`verification/20260929_终值核验_runbook.md` 全项（南向9/28单日＋ZETA/SPCX/HPE/GLDM双源终值＋恒指口径轻复认＋10Y CSV 9/28行）。
- 步骤：先 read_group_history(03:19之后) 取通用助手 04:05 终值表 → 独立拉数对照 → 05:50 前群发结论表 @首席；完成后删除本节。
- 21:30 UTC 前的 heartbeat：一律 HEARTBEAT_OK（等终值表，不动手，省 API）。

- [ ] 调度器守护检查：`ps aux | grep scheduler.py | grep -v grep` 无进程时，执行
  `cd /home/z/my-project/shared/全栈工具v1_三地行情抓取 && setsid nohup python3 scripts/scheduler.py > logs/scheduler.out 2>&1 < /dev/null &`
  拉起后无需通知群（状态锁保证幂等，不会重复跑批）。若连续两次 heartbeat 都拉起失败，才在群里报障。
  （【10/9】第4次静默死亡：10/6 08:21 拉起→10/6 16:40 前又死，10/7-10/9 全窗口失守，20:11 已重启+全量回填。HK_POOL 已补药明系三只，spcx --force 已补 9 个美股交易日。）
- [ ] SPCX 守护检查：`ps aux | grep spcx_monitor | grep -v grep` 无进程时，执行
  `cd /home/z/my-project/shared/全栈工具v1_三地行情抓取 && setsid nohup /home/z/.venv/bin/python3 scripts/spcx_monitor.py --loop > logs/spcx_daemon.out 2>&1 < /dev/null &`
  （2026-09-19 教训：SPCX 守护死亡导致 9/17-9/18 缺数。）
- [ ] 数据新鲜度抽查（每天一次即可）：`market_data/daily` 任取一只，last_date 落后 2 个交易日以上 →
  先查 scheduler.log，必要时手动 `scripts/run_all.py` 补跑后再报障。
- [ ] 其余情况：HEARTBEAT_OK

## 23/5 交易校準（一次性任務 12/5–12/9，數據管道腿·與量化腿協議v2 10/10）
- 12/5 前：建成＋單測三個新作業（守護加載，日期條件 ≥12/6 自動激活）：① 10:00 HKT 隔夜開市捕手（首30分鐘高低＋量，一次採集兩用：我存檔＋量化W2窗）；② 05:05 HKT（冬）16:00 OCP 收盤錨拉取——**顯式按日期 pin「剛完成交易日bar」**（維護窗 HKT 09:00–10:00 天然切齊bar邊界：D日bar=10:00 HKT(D)→09:00 HKT(D+1)，兩日零重疊），**記錄印記時間戳**（16:00–16:05之間印≈OCP可接受）；③ 12/7 首日全週期存檔確認。
- 12/7（週一）：首日管道驗證＝過渡協議第1條——首個隔夜段 10:00–17:00 HKT，**當天存檔首夜隔夜量占比**，缺了基線斷檔。
- 12/8–12/9：三源日K口徑校準報告（騰訊/官方print/AAStocks）＋**新增兩欄**：日成交量是否含隔夜量（對齊量化C2基線重算）、隔夜段高低 vs 次日Core開盤缺口率（餵量化N1假突破統計）。**兩種結論都備案**：騰訊切最新價邏輯→05:05錨拉升級必須；維持OCP歸屬→錨拉照建（零成本保險），06:30作業保留主責。
- 第4源備註：量化建議加 Stooq/Yahoo——本環境 10/6+10/9 兩輪實測雙雙被封，校準日再試一次，不通則以官方print＋新聞收評雙源替代並明示。
- 12/6 前：NYSE 官方公告終核時段表（nyse.com 行銷頁仍掛 22h 舊文案——通用助手 10/10 提醒）。
- 遠期錨點：2027/3/14 夏令切換→夜盤=HKT 09:00–16:00 全程覆蓋港A（宏觀腿10/10），錨拉時刻 05:05→04:05 HKT，屆時復核。
