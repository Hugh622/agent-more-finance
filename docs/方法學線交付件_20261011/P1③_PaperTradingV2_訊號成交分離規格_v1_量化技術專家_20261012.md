# P1③｜Paper Trading v2 訊號/成交分離規格 v1.0（量化技術專家）

日期：2026-10-12 ｜ 對齊：首席《Paper Trading v2＋Event Replay 十二周路線圖 v1.0》§三（Q-P1-3）｜ 狀態：**定稿**

---

## 一、四層分離模型（Signal → Order → Fill → Lot）

```
signal（觸發即凍結，不可變）
   └─ paper_order（執行意圖，可撤）
         └─ paper_fill（成交記錄，附價格來源與 Last Sale 資格判定）
               └─ position_lot（持倉批次，由 fill 聚合；減倉=FIFO 出 lot）
```

- **Signal 層**：`signal_id, as_of_time_utc, rule_id, rule_version, data_run_id（＝P1① manifest 側車 run_id，快照身份）, 觸發快照欄位（觸發價/觸發指標值/prior_high 等不可再算量）`。**觸發即凍結**：修正一律走新版本 signal（supersedes），禁覆寫——與註冊冊 supersedes 鏈同構。
- **Order 層**：`order_id, signal_id（可空＝人工令，須入 override 台賬）, market, side, qty, order_type, intended_session（目標成交時段枚舉）, created_at`。
- **Fill 層**：`fill_id, order_id, fill_session, fill_price, fill_qty, price_source, last_sale_eligible, slip_vs_anchor_bp, fill_ts_utc, reproducibility_hash`。
- **Lot 層**：`lot_id, fill_id_in, fill_id_out, qty, entry_date, exit_date, r_multiple`。減倉語義：只減不加的『減』＝按 FIFO 出既有 lot（E0 事件窗鐵律的 fill 層承載）。

**三條分離鐵律（驗收錨：分離執行率 100%，零混記）**
1. **B1 觸發≠成交**：signal 生成 bar 與 fill 成交 bar 是兩個決策點；signal 不攜帶任何成交價格欄位。
2. **B2 全鏈可追溯**：fill 必掛 order；order 必掛 signal 或人工令（人工令必入 override 台賬）；signal→order→fill→lot 四級外鍵閉合，回放器按鏈重建。
3. **B3 價格來源強制聲明**：每筆 fill 必填 `price_source`＋`last_sale_eligible` 兩欄——無來源聲明的 fill 視為 RULE_VIOLATION 入台賬。

## 二、paper_fill 三地微結構（定價假設，預註冊後不可切換）

### 2.1 US｜16:00 ET OCP 收盤競價（C1 明文錨）
- 官方收盤價＝16:00 ET **closing cross（OCP）**，屬官方 Last Sale；P0.C1@1.2.0「收盤越位」即此口徑（C23 收市確認制的執行層落點）。
- 半日市 OCP＝13:00 ET（感恩節次日等，假日曆靜態配置入凍結層）。
- **盤前盤後（4:00-9:30 / 16:00-20:00 ET）成交為 Form T（條件 'T'），不具 Last Sale 資格**——paper_fill 禁以此定價，僅可作 reference price 記錄。
- 數據現實：回放/回測期以 qfq 日K close 代理 OCP（`price_source='DAILY_CLOSE_PROXY'`），滑點帶按代理口徑放寬並在報告頭標注。

### 2.2 HK｜收市競價（CCP）與開市競價
- 收盤＝**16:00-16:10 收市競價段（隨機收市 16:08-16:10）**，`price_source='HK_CCP'`。
- 開倉執行＝T+1 開市競價（09:00-09:30 輸入盤，09:22-09:30 對盤），`price_source='HK_AUCTION_OPEN'`。
- **VCM 冷靜期**：5/10 分鐘監測觸發→paper_fill 標 `vcm_flag=true`，成交順延至冷靜期後首個可成交時段，禁按觸發價成交。

### 2.3 CN｜集合競價（開盤 9:15-9:25 / 收盤 14:57-15:00）
- 收盤＝**14:57-15:00 收盤集合競價**，`price_source='CN_AUCTION_CLOSE'`；開倉＝T+1 開盤集合競價（9:20 後不可撤單），`price_source='CN_AUCTION_OPEN'`。
- **漲跌停微結構**：一字板無法成交——fill 狀態 `NO_FILL(limit_up/limit_down)`，禁按漲停價虛擬成交（這是 A 股回測虛假優勢的最大來源，寫死為引擎常量）。
- **T+1 制度**：當日買入 lot 的 fill_id_out 最早掛次日——position_lot 結算日約束由引擎強制。

### 2.4 隔夜段（跨節假／盤外）——'T' 條件通用禁令
- 券商隔夜盤（20:00-04:00 ET 等）成交一律 Form T 條件，**不具 Last Sale 資格，禁按隔夜價成交**（路線圖 §三明文）。
- 落地：引擎與紙面倉的 fill 定價域 = {OCP, 開/收集合競價, 正規連續時段}；隔夜只允許「掛單意圖」記錄於 order 層（intended_session=NEXT_TRADABLE），fill 順延至次一正規時段。
- E0 事件窗「只減不加」的減倉單同理：不在窗內即時價成交，走次一正規時段。

### 2.5 fill_session 枚舉（DDL CHECK 已入）
`US_OCP ｜ HK_CCP ｜ HK_AUCTION_OPEN ｜ CN_AUCTION_CLOSE ｜ CN_AUCTION_OPEN ｜ NEXT_TRADABLE（回放代理）｜ REFERENCE_ONLY（T 條件價，永不入 fill 定價）`

## 三、時鐘/日曆規範

- `as_of_time`、`fill_ts` 統一存 **UTC**；展示層雙時區（UTC＋市場本地 ET/HKT/CST）。
- DST：US 11/1 變冬日／3 月第 2 個周日切換，由 pytz 鏈處理，禁止硬編碼 UTC-5/-4。
- 三地假日曆（us/hk/cn）靜態配置入凍結層（與 fomc_calendar.json 同模式，帶 sha256）。

## 四、狀態機與滑點驗收

- fill 狀態機：`PENDING → FILLED ｜ NO_FILL(limit_up ｜ limit_down ｜ vcm ｜ liquidity) ｜ CANCELLED`。
- 錨價＝intended_session 對應官方時段價；`slip_vs_anchor_bp` 記偏移。**驗收錨（路線圖 §四）：滑點 ≤0.5% 容差內佔比 ≥80%**；超帶 fill 逐筆入行為復盤扣分項（EXECUTION_SLIP）。
- 可復現性：`reproducibility_hash = sha256(規範化 fill 序列 JSON)`；同凍結層重跑 100% 一致，不一致＝引擎 RULE_VIOLATION。

## 五、與回測引擎（P2）及九表的銜接

- 回測成交約定已按本規格實現（engine.py 頭註釋即預註冊聲明）：**觸發一律收盤確認（C23）→ 入場=確認日 T 下一可成交 bar 收盤（entry_effective=next_tradable_bar）→ 退出=觸發日當日收盤**；退出在收盤競價流程內可執行（OCP/CCP/CN 收盤集合競價均容許收盤段出單），計滑點。
- DDL：SQLite 基座九表（paper_order/paper_fill/position_lot）＋MySQL delta 補列見 shared 交付件；signal 表 W1 收編正式。
- 回測期 price_source 一律 `DAILY_CLOSE_PROXY`（250 根日K 無分時），紙面實盤期按 §二三地真實微結構定價——兩期口徑差異在每份回報頭部聲明。

## 六、局限聲明

- 回放/回測用日K 代理，無法模擬盤中流動性沖擊與部分成交（partial fill）；紙面 v2 實時期以 `fill_session` 真值互校，代理口徑與實時口徑的差值月度匯報。
- 港股 VCM／A 股漲跌停在日K 代理下只能事後標注（若当日 high=low=limit），無法事前攔截——已作為 NO_FILL 判定的保守規則寫入引擎。
