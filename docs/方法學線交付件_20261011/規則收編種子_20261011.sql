-- ============================================================
-- 規則收編種子_20261011.sql（MySQL 方言）（方法學線 P1② 交付件，由 gen_seeds_dual.py 自 rules_registry_20261011.yaml 生成）
-- 源文件：rules_registry_20261011.yaml（72 行定稿，含歷史版本鏈）——單一事實源，兩方言種子同步生成
-- 載入順序鐵律：①EXP種子預註冊_20261011.sql → ②本文件（FK 依賴 experiment）
-- 執行者：全棧開發（單寫者原則）；憑據環境變數注入，本文件零憑據
-- ============================================================

-- ① 家族級佔位行退役（rule_id='C' 等家族行 → retired；個別規則已按 rule_id 逐條收編）
UPDATE rules SET status='retired',
  notes=CONCAT(COALESCE(notes,''),' [2026-10-11 方法学线收编: 家族级占位行退役, 个别规则见 C1-C19/R1-R10/N1-N19/D1-D3/K1-K6/W1-W5/G1-G2/P0.*]')
WHERE (rule_id, version) IN (('C', '1.0.0'), ('R', '1.0.0'), ('N', '1.0.0'), ('D', '1.0.0'), ('K', '1.0.0'), ('W', '1.0.0'), ('G', '1.0.0'));



-- supersedes 變數閉合（v1.0.1 修正：SET 必須前置於 INSERT——MySQL @var 在 INSERT 求值時展開，後置會使 supersedes_id 全部落 NULL）
SET @P0.C1_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='P0.C1' AND version='1.0.0' LIMIT 1);
SET @P0.C1_v_1_2_0 := (SELECT id FROM rules WHERE rule_id='P0.C1' AND version='1.2.0' LIMIT 1);
SET @P0.C2_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='P0.C2' AND version='1.0.0' LIMIT 1);
SET @P0.C2_v_1_2_0 := (SELECT id FROM rules WHERE rule_id='P0.C2' AND version='1.2.0' LIMIT 1);
SET @P0.C3_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='P0.C3' AND version='1.0.0' LIMIT 1);
SET @P0.E0_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='P0.E0' AND version='1.0.0' LIMIT 1);
SET @P0.E0_v_1_2_0 := (SELECT id FROM rules WHERE rule_id='P0.E0' AND version='1.2.0' LIMIT 1);
SET @P0.E1_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='P0.E1' AND version='1.0.0' LIMIT 1);
SET @C1_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='C1' AND version='1.0.0' LIMIT 1);
SET @C2_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='C2' AND version='1.0.0' LIMIT 1);
SET @C3_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='C3' AND version='1.0.0' LIMIT 1);
SET @C4_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='C4' AND version='1.0.0' LIMIT 1);
SET @C5_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='C5' AND version='1.0.0' LIMIT 1);
SET @C6_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='C6' AND version='1.0.0' LIMIT 1);
SET @C7_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='C7' AND version='1.0.0' LIMIT 1);
SET @C8_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='C8' AND version='1.0.0' LIMIT 1);
SET @C9_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='C9' AND version='1.0.0' LIMIT 1);
SET @C10_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='C10' AND version='1.0.0' LIMIT 1);
SET @C11_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='C11' AND version='1.0.0' LIMIT 1);
SET @C12_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='C12' AND version='1.0.0' LIMIT 1);
SET @C13_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='C13' AND version='1.0.0' LIMIT 1);
SET @C14_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='C14' AND version='1.0.0' LIMIT 1);
SET @C15_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='C15' AND version='1.0.0' LIMIT 1);
SET @C16_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='C16' AND version='1.0.0' LIMIT 1);
SET @C17_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='C17' AND version='1.0.0' LIMIT 1);
SET @C18_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='C18' AND version='1.0.0' LIMIT 1);
SET @C19_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='C19' AND version='1.0.0' LIMIT 1);
SET @R1_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='R1' AND version='1.0.0' LIMIT 1);
SET @R2_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='R2' AND version='1.0.0' LIMIT 1);
SET @R3_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='R3' AND version='1.0.0' LIMIT 1);
SET @R4_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='R4' AND version='1.0.0' LIMIT 1);
SET @R5_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='R5' AND version='1.0.0' LIMIT 1);
SET @R6_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='R6' AND version='1.0.0' LIMIT 1);
SET @R7_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='R7' AND version='1.0.0' LIMIT 1);
SET @R8_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='R8' AND version='1.0.0' LIMIT 1);
SET @R9_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='R9' AND version='1.0.0' LIMIT 1);
SET @R10_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='R10' AND version='1.0.0' LIMIT 1);
SET @N1_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='N1' AND version='1.0.0' LIMIT 1);
SET @N2_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='N2' AND version='1.0.0' LIMIT 1);
SET @N3_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='N3' AND version='1.0.0' LIMIT 1);
SET @N4_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='N4' AND version='1.0.0' LIMIT 1);
SET @N5_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='N5' AND version='1.0.0' LIMIT 1);
SET @N6_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='N6' AND version='1.0.0' LIMIT 1);
SET @N7_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='N7' AND version='1.0.0' LIMIT 1);
SET @N8_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='N8' AND version='1.0.0' LIMIT 1);
SET @N9_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='N9' AND version='1.0.0' LIMIT 1);
SET @N10_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='N10' AND version='1.0.0' LIMIT 1);
SET @N11_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='N11' AND version='1.0.0' LIMIT 1);
SET @N12_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='N12' AND version='1.0.0' LIMIT 1);
SET @N13_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='N13' AND version='1.0.0' LIMIT 1);
SET @N14_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='N14' AND version='1.0.0' LIMIT 1);
SET @N15_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='N15' AND version='1.0.0' LIMIT 1);
SET @N16_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='N16' AND version='1.0.0' LIMIT 1);
SET @N17_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='N17' AND version='1.0.0' LIMIT 1);
SET @N18_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='N18' AND version='1.0.0' LIMIT 1);
SET @N19_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='N19' AND version='1.0.0' LIMIT 1);
SET @D1_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='D1' AND version='1.0.0' LIMIT 1);
SET @D2_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='D2' AND version='1.0.0' LIMIT 1);
SET @D3_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='D3' AND version='1.0.0' LIMIT 1);
SET @K1_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='K1' AND version='1.0.0' LIMIT 1);
SET @K2_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='K2' AND version='1.0.0' LIMIT 1);
SET @K3_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='K3' AND version='1.0.0' LIMIT 1);
SET @K4_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='K4' AND version='1.0.0' LIMIT 1);
SET @K5_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='K5' AND version='1.0.0' LIMIT 1);
SET @K6_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='K6' AND version='1.0.0' LIMIT 1);
SET @G1_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='G1' AND version='1.0.0' LIMIT 1);
SET @G2_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='G2' AND version='1.0.0' LIMIT 1);
SET @W1_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='W1' AND version='1.0.0' LIMIT 1);
SET @W2_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='W2' AND version='1.0.0' LIMIT 1);
SET @W3_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='W3' AND version='1.0.0' LIMIT 1);
SET @W4_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='W4' AND version='1.0.0' LIMIT 1);
SET @W5_v_1_0_0 := (SELECT id FROM rules WHERE rule_id='W5' AND version='1.0.0' LIMIT 1);
-- ② 個別規則收編（72 行；supersedes 鏈經 @var 閉合，@var 已於上方 SET 前置）
INSERT INTO rules (rule_id,version,status,owner,scope,inputs,parameters,logic_ref,logic_desc,entry_effective,invalidation,validation_experiment_id,supersedes_id,notes) VALUES
('P0.C1','1.0.0','retired','quantitative','["US","HK","CN"]','["close","breakout_level"]','{"buffer_pct":0.002,"basis":"收盘越位（收盤價站上前高突破位＋0.2%緩衝方確認，盤中假越位不算）"}','bt_engine.rules_p0::c1_close_break','C1 收盤越位確認 v1.0：收盤＞突破位×(1+0.002) 才確認；盤中越位不作數','next_tradable_bar','回測判決 EXP-2026-001 NO-GO 或覆盤證實失效→永久撤回','EXP-2026-001',NULL,'v1.0 定稿 2026-09-12；v1.1 承繼不變'),
('P0.C1','1.2.0','active','quantitative','["US"]','["close","breakout_level","session"]','{"buffer_pct":0.002,"close_definition":"16:00 ET OCP（正式收盤競價 print）","overnight_bars":"23×5 隔夜段打印不具確認資格"}','bt_engine.rules_p0::c1_close_break_v12','C1 收盤明文修訂（23/5）：美市確認價=16:00 ET OCP；隔夜段『T』條件打印不得觸發 C1','next_tradable_bar','回測判決 EXP-2026-001 NO-GO 或 12/8 校準報告證偽→回退 1.0.0 口徑','EXP-2026-001',@P0.C1_v_1_0_0,'2026-10-10 23/5 修訂；框架 v1.4 收編程序進行中；HK/CN 維持 1.0.0 口徑'),
('P0.C2','1.0.0','retired','quantitative','["US","HK","CN"]','["volume","ma20_volume"]','{"vol_gate":1.5,"vol_soft_floor":1.2,"vol_fail_floor":1.0,"baseline_days":20}','bt_engine.rules_p0::c2_volume_gate','C2 量能確認 v1.0：突破日量≥1.5×20日均量；1.2-1.5×降級檔；v1.1 加 R9 時間尺度註解（日線 1.2-1.5×/日內 5×+ 禁混）','next_tradable_bar','EXP-2026-001/002 分層判決證偽→撤回','EXP-2026-001',NULL,'<1.0×直接不合格（R9 硬門檻）'),
('P0.C2','1.2.0','active','quantitative','["US","HK","CN"]','["volume","ma20_volume","ma21_volume"]','{"vol_gate":1.5,"vol_soft_floor":1.2,"vol_fail_floor":1.0,"amendment":"量能不足由單獨否決改為減半觀察檔（輔助訊號）；恢復判據=量能重回 21 日均量 1.0×"}','bt_engine.rules_p0::c2_volume_gate_v12','C2 量能降級修訂（23/5）：量能不足→確認維持但倉位減半＋觀察標記；21 日量能中樞恢復為解除條件','next_tradable_bar','EXP-2026-001 分層顯示降級檔期望值劣於硬門檻→回退','EXP-2026-001',@P0.C2_v_1_0_0,'2026-10-10 23/5 修訂'),
('P0.C3','1.0.0','active','quantitative','["US","HK","CN"]','["close","breakout_level"]','{"window_days":3,"hold_days_required":2,"buffer_pct":0.002}','bt_engine.rules_p0::c3_three_day_two_hold','C3 三日二守：突破後 3 個交易日內≥2 日收於突破位＋0.2%上方；未守=假突破處置（移出/留觀）','next_tradable_bar','EXP-2026-001 判決或 60 日統計（D3）證偽→撤回','EXP-2026-001',NULL,'v1.0→v1.2 承繼不變'),
('P0.E0','1.0.0','retired','quantitative','["US","HK","CN"]','["event_calendar"]','{"window_trading_days":1,"events":["FOMC"],"action":"只減不加"}','bt_engine.rules_p0::e0_event_filter','E0 事件過濾器 v1.0：FOMC 決議日±1 交易日只減不加','event_window','EXP-2026-003 NO-GO→撤回','EXP-2026-003',NULL,'v1.0 定稿'),
('P0.E0','1.2.0','active','quantitative','["US","HK","CN"]','["event_calendar","session"]','{"window_trading_days":1,"events":["FOMC"],"action":"只減不加","amendment":"事件時刻以決議公布時點錨定（23×5 跨時段）；事件日曆載入 market_data/calendar/fomc_calendar.json"}','bt_engine.rules_p0::e0_event_filter_v12','E0 事件時刻更新（23/5）：公布時點錨定＋三地日曆對齊；全日曆回放驗證=EXP-2026-003','event_window','EXP-2026-003 NO-GO→撤回','EXP-2026-003',@P0.E0_v_1_0_0,'2026-10-10 23/5 修訂'),
('P0.E1','1.0.0','active','quantitative','["US","HK","CN"]','["adx14","ma5","ma10","ma20","atr"]','{"adx_threshold":20,"entangle_rule":"MA5/10/20 高低差<1×ATR→纏繞","action":"突破類 setup 停做","release":"ADX>20 且均線發散解除"}','bt_engine.rules_p0::e1_environment_filter','E1 環境過濾器（v1.1 新增，掛載 P0 確認制）：whipsaw 環境自動停做突破類 setup','next_tradable_bar','無失效條款（治理條款：失效即撤）',NULL,NULL,'父條款=R6@1.0.0；兩處一體，改動須同步'),
('C1','1.0.0','active','quantitative','["US","HK","CN"]','["price","fair_value_band","tbill_yield"]','{"premium_1sd":"倉位×0.5","premium_2sd":"只觀察不落場","stock_5y_percentile_max":50,"hurdle":"T-bill ~5%"}',NULL,'C1 估值折讓檢查（雙刻度）：建倉區間與公允區間核對，升格新倉流程首閘（R8 前）','next_tradable_bar','三個月樣本錯過共振過多→放寬 1.5SD 重測；連續兩季無效即撤',NULL,NULL,'來源：Buffett 安全邊際＋宏觀 F3'),
('C2','1.0.0','active','quantitative','["US","HK","CN"]','[]','{"declaration_fields":["格位（短/中/長/超長）","樣本邊界"],"missing_penalty":"計違規，入閘A 違規率≤5%"}',NULL,'C2 格位＋樣本邊界聲明制：每筆交易標明格位＋適用邊界，答不出不落場','next_tradable_bar','無（永久紀律）',NULL,NULL,'與 P0.C2 為不同編號系統的兩條規則（並行不衝突）'),
('C3','1.0.0','active','quantitative','["US","HK","CN"]','["moat_life_years"]','{"moat_life_floor_years":5,"under_5y_action":"掛 M 編號里程碑重檢"}',NULL,'C3 護城河折舊評估：長線入池須評護城河壽命；『永久特許權』改讀『有到期日』','next_tradable_bar','里程碑到期未兌現→降格或出池',NULL,NULL,'長線池篩選掛載'),
('C4','1.0.0','active','quantitative','["US","HK","CN"]','["peg"]','{"peg_advisory_veto":1.2,"categories":["緩慢增長","穩定增長","快速增長","周期","轉機","資產富餘"],"log_to":"F 分"}',NULL,'C4 Lynch 六分類併入 R4 催化劑分類＋PEG>1.2 提示級否決','next_tradable_bar','六分類×催化劑映射一年後檢討重疊度',NULL,NULL,'入池估值審查掛載'),
('C5','1.0.0','active','quantitative','["US","HK","CN"]','["realized_vol_20d","vol_percentile"]','{"pctl_high":80,"coeff_high":0.6,"pctl_restore":60}','bt_engine.rules_sizing::c5_vol_coefficient','C5 波動率分位→倉位係數：20 日實現波動率 80 分位↑→×0.6；回落 60 分位↓恢復','next_tradable_bar','壓倉期間錯過兩次 P0 確認→檢討分位閾值',NULL,NULL,'倉位閘·波動率目標制；來源 Moreira & Muir 2017'),
('C6','1.0.0','active','quantitative','["US","HK","CN"]','["rs_sector","vol_regime","positioning"]','{"rs_below_median":"減半","momentum_crash":"高波動＋倉位擠壓→全面減倉","recalc":"RS 週度"}',NULL,'C6 動量退出機械化：RS 跌破板塊中位→減半；動量崩盤信號→全面減倉','next_tradable_bar','2009 式動量崩盤防禦每季回測校準',NULL,NULL,'掛 RS 過濾器/R8'),
('C7','1.0.0','registered','quantitative','["US"]','["earnings_surprise","close","volume"]','{"trigger":"財報後首個 P0 確認＋量能≥1.2× 雙件套","position":"分級倉位","gate_a":"≥100 筆＋期望值>0"}',NULL,'C7 PEAD 漂移入場（🟡模擬 8-12 週，零實盤授權）；C14 拐點閘為前置半邊','next_tradable_bar','模擬驗證失敗→永久撤回',NULL,NULL,'來源 Ball & Brown 1968（證據 A-）；whipsaw 市況啟動節奏從緊'),
('C8','1.0.0','frozen','quantitative','["US"]','[]','{"budget_share":"對沖 25%+ 的一部分","precondition":"SG Trend 官方數據核實＋與 VIXY 類相關性實測"}',NULL,'C8 CTA 危機對沖腿（🟠待核凍結）：SG 官方數據未核實前凍結推進','next_tradable_bar','核實後連續兩季遜現有對沖→回退',NULL,NULL,'來源 Moskowitz 2012 JFE（證據 A）'),
('C9','1.0.0','registered','quantitative','["US"]','["edgar_filings"]','{"drift_window":"申報公布後 1-3 個月","flow":"EDGAR 新申報→觀察名單→P0 確認→分級倉位"}',NULL,'C9 13D/G 跟蹤流（🟡模擬，純跟蹤不維權，零實盤授權）','next_tradable_bar','模擬驗證失敗→永久撤回',NULL,NULL,'掛事件日曆'),
('C10','1.0.0','active','quantitative','["US"]','["close","ma50","ma150","ma200","high_52w","low_52w","rs"]','{"above":"50/150/200MA","ma150_gt_ma200_rising_1m":true,"off_low_52w":0.3,"off_high_52w_max":0.25,"rs":"高"}','bt_engine.rules_prefilter::c10_stage2','C10 Stage 2 前置過濾器：44 標的池套用，承載金字塔加倉許可狀態機','next_tradable_bar','Stage 3 轉換信號→即時出列',NULL,NULL,'來源 Minervini（B 級，跨 25 年兩屆）；選股前置掛載'),
('C11','1.0.0','active','quantitative','["US","HK","CN"]','["entry_price","invalidation_level","atr14"]','{"stop_formula":"max(技術證偽位, 入場×0.92)","eqr_good_max":1.2,"eqr_poor_min":2.0,"avg_loss_target_pct":5}','bt_engine.rules_exit::c11_stop_cap','C11 個股止損硬頂（併 EQR 刻度）：止損=技術證偽位與入場×0.92 取嚴；EQR≤1.2 好／>2 劣質進場','next_tradable_bar','與三地波動校準衝突時以『金額細過獲利目標』原則話事','EXP-2026-002',NULL,'EXP-2026-002 基準臂之一'),
('C12','1.0.0','registered','quantitative','["US"]','["wedge_contraction","close","volume"]','{"trigger":"楔形量價收縮段入觀察→收盤確認後入場（P0 前置）","gate_a":"≥100 筆＋期望值>0"}',NULL,'C12 收縮→突破前置觸發器（🟡模擬，零實盤授權）','next_tradable_bar','模擬驗證失敗→永久撤回',NULL,NULL,'來源 Kell Wedge Pop（B 級單年 2020 +941.1%，⚠️ 2021 後無紀錄）'),
('C13','1.0.0','active','quantitative','["US"]','["iv_percentile","iv","rv"]','{"high_iv_day":"收窄進場容忍度＋限價單強制","exclude_0dte":true,"iv_gt_rv":"倉位天花板輔助讀數"}',NULL,'C13 波動率視角環境規則：IV 高分位日收窄容忍＋限價強制；0DTE 到期效應從日內統計剔除','next_tradable_bar','無（視角級紀律）；P0 確認制經此驗證維持不變',NULL,NULL,'掛環境解讀/E1；來源 XTX 視角＋量化 P4 判決'),
('C14','1.0.0','active','macro','["US","HK","CN"]','["revenue_growth","estimate_revisions","gross_margin"]','{"need":"三選二","a":"營收增速連 2 季加速（或負轉正）","b":"一致預期上修>下修／財報後 90 日中位數上調","c":"毛利率環比 2 季改善"}',NULL,'C14 盈利拐點三選二閘：買『變化』不買『存量』；入觀察池資格閘','next_tradable_bar','低頻同向閘；與 C1 併組入池首閘組合',NULL,NULL,'來源宏觀 F1（財報公開數據）'),
('C15','1.0.0','active','macro','["US","HK","CN"]','["ism_new_orders_minus_inventory","pmi","inventory_days"]','{"macro":"ISM 新訂單−客戶庫存差值月度跟蹤","pmi_below_50_3m":"去庫段回避重資產周期股","micro":"存貨週轉天數連 2 季上升＋營收未同步加速=渠道壓貨警號","double_kill":"PMI<50＋ADX<20 同現=禁開新倉"}',NULL,'C15 周期位置檢查：宏觀庫存周期＋微觀渠道壓貨雙刻度','next_tradable_bar','低頻同向閘',NULL,NULL,'掛 E1＋事件日曆；來源宏觀 F2'),
('C16','1.0.0','active','macro','["US","HK","CN"]','["ocf","net_income","net_debt_ebitda","interest_coverage","debt_maturity_24m"]','{"ocf_ni_min":0.8,"ocf_ni_years":2,"net_debt_ebitda_max":2.0,"interest_cover_min":5.0,"maturity_24m_lt":"EBITDA"}',NULL,'C16 現金流質量三閘：三條全過先算『養得起自己』——利潤係觀點，現金係事實','next_tradable_bar','現金流惡化=論點證偽',NULL,NULL,'反面教材 CRWV；掛第六問＋C11＋R7'),
('C17','1.0.0','active','quantitative','["US","HK","CN"]','["l1","l2","l3","l4","l5","l6","l7","l8","l9","l10"]','{"tiers":{"NORMAL(<=3)":"主題倉≤20%","ALERT(4-5)":"≤12%，禁新開拋物線股","LATE(6-7)":"≤8%，只留 leader、止加倉、拋物線減半","PARABOLIC_END(>=8)":"0-2%，只准減不准加"},"cadence":"每週五收市評分","jump_rule":"L1/L5/L9 任兩條由❌轉✅→階段即時上調","current_score_0927":3.5,"nested_within":"L2 40%／個股閘 28% 之內（主題倉子閘）","l_signals":{"L1":"指數高於 200DMA ≥+50%","L2":"6m ROC ≥+75% 或 12m ROC ≥+100%（40% 為 L2 全權益天花板非主題倉上限）","L3":"200DMA 六個月斜率 ≥+30%","L4":"6 個月內 ≥2 次單週漲幅>10%","L5":"價新高而 12m ROC<6m ROC 一半","L6":"領袖高於 200DMA ≥+60% 且 12m ROC ≥+200%","L7":"RS 12m 斜率歷史極值後轉負","L8":"板塊內部強弱差急擴（定性）","L9":"20 日漲跌量比<0.7 持續 5 日＋收穿 50MA","L10":"SPY 收穿 200DMA 或現行砍半線"}}','bt_engine.rules_bubble::c17_state_machine','C17 十信號泡沫狀態機（重標定版）：L1-L10 週評→主題倉四檔上限；L 碼為 C17 參數內信號 ID 不另立冊','next_tradable_bar','樣本更新即重校閾值；與現行閘衝突取嚴；單一信號系統永不單獨話事（須與宏觀 G1 交叉）',NULL,NULL,'n=3 外推 ⚠️；L9 閾值單源 ⚠️；XLK/IGV 2025-10~2026-03 復權段存疑'),
('C18','1.0.0','active','quantitative','["US","HK","CN"]','["high_200dma_reach","ma50","ma200","roc_6m","roc_12m","updown_vol_ratio_20d"]','{"T1":"拋物線股：高於 200DMA 曾達+60%，其後收穿 50MA→減半；收穿 200DMA→清（主題倉部分）","T2":"背離閘：指數新高而 12m ROC<6m ROC 之半→主題倉減半","T3":"派發閘：20 日量比<0.7 連續 5 日＋收穿 50MA→減半","T4_standing":"SPY 748.8 砍半線／200DMA(≈718.5) 清主題倉——現行閘重申，不佔新編號（裁決明文）","once_only":"同一觸發事件只執行一次、不疊加雙重減倉；衝突取嚴"}','bt_engine.rules_bubble::c18_realtime_gates','C18 即時觸發閘 T1-T3：即時執行不等週評；T4 屬現行閘重申註記','same_bar_close','無；與現行閘衝突取嚴',NULL,NULL,'來源量化避損規則 v1.0（三輪 12 次熊市反彈無一守住 200DMA）'),
('C19','1.0.0','active','quantitative','["US","HK","CN"]','["burst_date","trough_date","ma200","drawdown_vs_sector"]','{"dead_cat_days":45,"reentry_min_days":53,"reentry_confirm":"收盤站上 200DMA＋3-10 日回踩不破（二守）","tranches":3,"survivor_filter":"回撤<板塊均值＋谷底高於 200DMA＋修復段率先新高","first_tranche_max":"目標倉 1/3","base_case":"谷後 12-45 個月見底、回撤 -77~-84%"}','bt_engine.rules_bubble::c19_post_burst','C19 爆破後右側回補＋倖存者濾網：45 日內反彈一律當死貓；右側三批回補劇本','next_tradable_bar','『遺囑式名單』爆破後按 K6 重新打分，不自動沿用泡沫期結論',NULL,NULL,'疊加 R8＋P0/T+1；來源量化避損 v1.0＋宏觀 W4'),
('R1','1.0.0','active','quantitative','["US","HK","CN"]','["account_equity","daily_pnl"]','{"daily_loss_stop":-0.02,"action":"即日停新倉，持倉照常管理","consecutive_2_days":"強制休市一週＋覆盤報告後恢復","reset":"下一交易日自動重置"}','bt_engine.rules_risk::r1_daily_loss_gate','R1 賬戶級日虧損閘 −2% 停新倉；連續兩日觸閘休市一週','next_tradable_bar','無（治理條款：失效即撤）',NULL,NULL,'v1.1 新增；掛 P0 確認制'),
('R2','1.0.0','active','quantitative','["US","HK","CN"]','["intraday_breakout","close","volume"]','{"probe_size":"1/3 試倉（止損即設）","top_up_condition":"收盤過 C1（收盤越位）＋C2（量能≥1.5×）補足標準倉","else":"試倉即止損，唔准再等等"}','bt_engine.rules_p0::r2_probe_confirm','R2 試倉 1/3＋收盤確認兩段制：盤中買=用倉位換時間；確認制=用時間換確定性','next_tradable_bar','收盤不過 C1 或量能不足 C2→試倉止損；E1 啟動期間 setup 停做',NULL,NULL,'T+1 確認制正式融合條目'),
('R3','1.0.0','active','quantitative','["US","HK","CN"]','["entry_price","stop_price","unrealized_r"]','{"scale_out":"確認後漲 1R 平 50%","remainder_stop":"上移至成本價","no_reversal":"唔准移返止損"}','bt_engine.rules_exit::r3_scale_out','R3 分批止盈平半＋移損至成本：右偏化盈虧分布（用期望值上限換方差下降，誠實標注非免費午餐）','next_tradable_bar','未達 1R 前按原止損執行；餘倉跌回成本即無風險離場',NULL,NULL,'延伸段=D2（2×ATR trail 記帳觀察中）'),
('R4','1.0.0','active','quantitative','["US","HK","CN"]','["catalyst_news","float_structure","insider_positioning"]','{"q1_catalyst":"催化劑係咩/邊類/有冇公開可查；冇新聞暴漲=對倒盤多數","red_flag":"反向合股催化劑特別標紅","q6_who_is_selling":"流通盤結構/內部人/承銷商/解禁增發日曆"}',NULL,'R4 催化劑分類＋第六問『邊個喺度賣？』：否定性檢查前置','next_tradable_bar','催化劑查唔到或反向合股→唔入觀察；增發在途→按 R5',NULL,NULL,''),
('R5','1.0.0','active','quantitative','["US","HK","CN"]','["ipo_date","unlock_shares","free_float"]','{"auto_flag":"IPO+180日/+365日（港股上市 6/12 個月窗）","unlock_ff_gt_50":"高危","unlock_ff_gt_100":"禁做多","pre_window":"解禁前禁做多（防 pre-expiry run-up）","re_rating":"解禁後量比<0.8× 連續 5 日＋收復解禁日收盤→重新評級"}',NULL,'R5 事件日曆否決權：lock-up expiry＝有日期嘅供給衝擊','next_tradable_bar','縮量企穩定義達成後重新評級（唔係永久迴避=N8 界線）',NULL,NULL,'Field & Hanka 2001 學術支持；全棧排程自動標記'),
('R6','1.0.0','active','quantitative','["US","HK","CN"]','["adx14","ma5","ma10","ma20","atr","gap_pct"]','{"e1_switch":"ADX14<20＋MA5/10/20 纏繞（<1×ATR）→突破類停做","gap_up_ban":"冇催化劑唔追 gap up；確需追＝RR 重算（2.5→1.5）＋倉位減半","hsip_bottom_window":"新低期突破一律假突破優先假設，直到放量收復 MA20"}','bt_engine.rules_p0::e1_environment_filter','R6 Whipsaw 市減少交易：E1 環境過濾器＋唔追 gap up（E1 實體=P0.E1，兩處一體）','next_tradable_bar','ADX 回升>20 且均線發散→E1 解除',NULL,NULL,'P0.E1@1.0.0 為其掛載實體；樣本邊界：有催化劑標的走 Ross 語境＋R2 兩段制'),
('R7','1.0.0','active','quantitative','["US","HK","CN"]','["realized_pnl"]','{"rule":"交易池實現利潤強制轉入長線池","direction":"單向閘不可倒流","sleeve_cap":"短炒倉位上限=f(已驗證 edge)，冇 edge=零"}',NULL,'R7 利潤單向沉澱入長線池：切斷賭徒螺旋','next_tradable_bar','無——單向閘冇例外',NULL,NULL,'賬戶章程第一條級別'),
('R8','1.0.0','active','quantitative','["US","HK","CN"]','["ma200_slope","rsi14","stretch_atr20","annual_budget","reclaim_volume"]','{"f1_trend_filter":"200 天線仍向上先啟動；向下只 DCA 唔加碼","f2_oversold":"RSI14<30＋偏離 50 天線>2×ATR20","f3_budget_cap":"左側總預算年度封頂","f4_invalidation":"企穩確認（跌穿後收復＋量≥1.2×）先生效，唔係掛單等價"}','bt_engine.rules_sizing::r8_dip_adding','R8 左側加碼四件套規則化（buy the dip）','next_tradable_bar','趨勢過濾不通→只 DCA；預算用罄→停加；GLDM 案：連續收破 50MA＋三日二守破位→加碼檔作廢',NULL,NULL,'寧德判詞：左側不接刀，右側信號=放量收回 MA20'),
('R9','1.0.0','active','quantitative','["US","HK","CN"]','["breakout_volume","ma20_volume","rs_sector"]','{"hard_gate":"突破日量≥1.5×20日均量","outright_fail":"<1.0× 直接不合格","rs_filter":"RS 與板塊同行先完整，不同行→減倉或唔入","scale_declaration":"日線確認 1.2-1.5×／日內動量 5×+（RVOL）——禁混刻度"}','bt_engine.rules_p0::c2_volume_gate','R9 形態檢查增補：量能硬門檻＋RS 過濾＋時間尺度聲明（C2 加註）','next_tradable_bar','量<1.0× 直接否決','EXP-2026-001',NULL,'logic_ref 與 P0.C2@1.0.0 同源函數（硬門檻語義）'),
('R10','1.0.0','active','quantitative','["US","HK","CN"]','["age","assets","max_drawdown_tolerance"]','{"p1_workbackwards":"由目標倒推配置，順序不可倒轉；雙向收斂（市場只畀 6-8% 就改目標）","p2_no_pseudo_precision":"可以抄『骨』唔可以抄『數』","p3_rules_not_forecast":"regime first, pattern second；lump sum 約 68% 時間優於 DCA（Vanguard 2012）"}',NULL,'R10 配置層心法三條（決策前置 Checklist 對照打勾）','next_tradable_bar','Checklist 任何一項未做→唔好落場',NULL,NULL,''),
('N1','1.0.0','rejected','quantitative','["US","HK","CN"]',NULL,'{"item":"動量超短線五支柱選股","reason":"頻率哲學互斥（邊界②）"}',NULL,'不採納清單 v1.1 ①：連『試吓』都唔准','next_tradable_bar','無——拒收邊界不設翻案程序（除非治理裁決重開）',NULL,NULL,'防復辟條目'),
('N2','1.0.0','rejected','quantitative','["US"]',NULL,'{"item":"繞 PDT","reason":"規則套利違反風控本意"}',NULL,'不採納清單 v1.1 ②','next_tradable_bar','無',NULL,NULL,''),
('N3','1.0.0','rejected','quantitative','["US"]',NULL,'{"item":"1 分鐘級執行依賴","reason":"快變量優勢屬於做市商（0DTE 佔 61% 世界）"}',NULL,'不採納清單 v1.1 ③','next_tradable_bar','無',NULL,NULL,''),
('N4','1.0.0','rejected','quantitative','["US","HK","CN"]',NULL,'{"item":"「勝率 70-80%」宣稱","reason":"自述≠實證；本群紅線"}',NULL,'不採納清單 v1.1 ④；hit rate 在本系統僅分層參考不作判決','next_tradable_bar','無',NULL,NULL,'與 P0 機制 R-5 條款呼應'),
('N5','1.0.0','rejected','quantitative','["US"]',NULL,'{"item":"低 float·反向合股參與","reason":"內部人控盤+統計上多數延續下行"}',NULL,'不採納清單 v1.1 ⑤','next_tradable_bar','無',NULL,NULL,''),
('N6','1.0.0','rejected','quantitative','["US","HK","CN"]',NULL,'{"item":"高頻多筆頻率哲學","reason":"與 whipsaw 市減少交易互斥"}',NULL,'不採納清單 v1.1 ⑥','next_tradable_bar','無',NULL,NULL,''),
('N7','1.0.0','rejected','quantitative','["US"]',NULL,'{"item":"「盤前漲幅即追」套用非催化劑標的","reason":"沉沒成本唔係訊號"}',NULL,'不採納清單 v1.1 ⑦','next_tradable_bar','無',NULL,NULL,''),
('N8','1.0.0','rejected','quantitative','["US","HK","CN"]',NULL,'{"item":"「解禁永久迴避」一刀切","reason":"R5 已有縮量企穩重新評級通道"}',NULL,'不採納清單 v1.1 ⑧——迴避係窗口制唔係永久制','next_tradable_bar','無',NULL,NULL,''),
('N9','1.0.0','rejected','quantitative','["US"]',NULL,'{"item":"波動率收割／裸賣波實盤","reason":"與日虧損閘−2%＋避免永久性虧損根本衝突；XIV −96% 反面教材"}',NULL,'v1.2 拒收終版①（只取 IV>RV 作 C13 輔助讀數）','next_tradable_bar','無',NULL,NULL,'v1.2 拒收①'),
('N10','1.0.0','rejected','quantitative','["US","HK","CN"]',NULL,'{"item":"高頻／做市策略複製","reason":"XTX 係產業唔係策略；費用結構都唔同"}',NULL,'v1.2 拒收終版②','next_tradable_bar','無',NULL,NULL,''),
('N11','1.0.0','rejected','quantitative','["US"]',NULL,'{"item":"親身維權／重倉單一事件股","reason":"無 13D 話語權；重倉違反倉位天花板"}',NULL,'v1.2 拒收終版③','next_tradable_bar','無',NULL,NULL,''),
('N12','1.0.0','rejected','quantitative','["US"]',NULL,'{"item":"13F 抄作業當即時訊號","reason":"遲 45 日＋空頭不申報＝舊地圖"}',NULL,'v1.2 拒收終版④（C9 跟蹤流已限定 1-3 個月漂移窗＋P0 確認）','next_tradable_bar','無',NULL,NULL,''),
('N13','1.0.0','rejected','quantitative','["US","HK","CN"]',NULL,'{"item":"D 級自述數字入策略庫","reason":"零獨立核驗"}',NULL,'v1.2 拒收終版⑤','next_tradable_bar','無',NULL,NULL,''),
('N14','1.0.0','rejected','quantitative','["US"]',NULL,'{"item":"單年冠軍當長期期望值","reason":"Kell 941% 分母=2020 完美動量年"}',NULL,'v1.2 拒收終版⑥','next_tradable_bar','無',NULL,NULL,''),
('N15','1.0.0','rejected','quantitative','["US","HK","CN"]',NULL,'{"item":"「永遠持有」字面＋「唔止損」神學","reason":"巴郡結構優勢散戶冇；引 Lynch 剪鮮花澆雜草"}',NULL,'v1.2 拒收終版⑦','next_tradable_bar','無',NULL,NULL,''),
('N16','1.0.0','rejected','quantitative','["US"]',NULL,'{"item":"十倍股期待＋BWYK 當選股系統","reason":"倖存者偏差；Reg FD 2000 後制度性終結"}',NULL,'v1.2 拒收終版⑧','next_tradable_bar','無',NULL,NULL,''),
('N17','1.0.0','rejected','quantitative','["US","HK","CN"]',NULL,'{"item":"現金新高當擇時訊號","reason":"T-bill ~5% 下嘅機會成本行為"}',NULL,'v1.2 拒收終版⑨','next_tradable_bar','無',NULL,NULL,''),
('N18','1.0.0','rejected','quantitative','["US","HK","CN"]',NULL,'{"item":"「跌五成＝神仙價」撈底錨","reason":"跌幅本身唔係買入理由；須 C14-C16＋TW 逐項重判"}',NULL,'v1.2 拒收終版⑩','next_tradable_bar','無',NULL,NULL,''),
('N19','1.0.0','rejected','quantitative','["US","HK","CN"]',NULL,'{"item":"快變量框架複製（美林時鐘精確擇時／日內支撐計數）","reason":"只做慢變量＋事件日曆"}',NULL,'v1.2 拒收終版⑪','next_tradable_bar','無',NULL,NULL,''),
('D1','1.0.0','active','quantitative','["US","HK","CN"]',NULL,'{"columns":["進場 EQR","加倉批次編號＋當時組合 RR","過 P0 確認後條件勝率","劣質進場欄（EQR>2x）","金字塔與條件勝率（併入本組）"],"stats_trigger":"累積≥30 筆出首份統計"}',NULL,'D1 執行帳覆盤欄位組（即刻啟用，純記錄）——映射 position_lot／decision 表欄位','next_tradable_bar','無（紀錄用途）',NULL,NULL,'突破失敗率 40-45% 外部統計 ⚠️ 單源只作方向參照；本群自算數字先入帳'),
('D2','1.0.0','registered','quantitative','["US","HK","CN"]',NULL,'{"trail":"浮盈≥2R 啟動 2×ATR14 追蹤止損（代替跌回成本即走）","observation":"8-12 週記帳觀察，不構成執行依據"}','bt_engine.rules_exit::d2_atr_trail','D2 餘倉右尾延長（2×ATR trail）——觀察中，達標提請寫入 v1.3','next_tradable_bar','右尾貢獻未升或方差超標→不升格','EXP-2026-002',NULL,'R3 延伸段；EXP-2026-002 附帶統計其右尾貢獻'),
('D3','1.0.0','active','quantitative','["US"]',NULL,'{"condition":"越線（突破位＋0.2%緩衝）但 16:00 ET 收回","action":"只記不動","review":"60 日後檢討"}','bt_engine.rules_p0::d3_overnight_fail_stats','D3 隔夜假突破統計（23/5 新制）：越線收回只記不動，累積檢討假突破頻率','next_tradable_bar','60 日檢討：若統計支持收緊→提請 C1 參數修訂',NULL,NULL,'原 23/5 研究報告編號 N1，收編時重編 D3（N1 已被不採納清單占用；語義本屬記帳觀察）'),
('K1','1.0.0','active','macro','["TW"]',NULL,'{"criterion":"成本曲線斷崖式下降","threshold":"單位成本年降幅 ≥50%"}',NULL,'K1 判『技術係唔係真』（K1-K4 一組）','next_tradable_bar','無（判別準則，隨產業數據更新）',NULL,NULL,'TW 模塊專用樣本邊界：常規標的唔套用浪潮語言'),
('K2','1.0.0','active','macro','["TW"]',NULL,'{"criterion":"採用曲線斜率","threshold":"滲透率<5%→>20% 的年數 ≤5 年；企業級付費客戶加速"}',NULL,'K2 採用速度對比上一代技術','next_tradable_bar','無',NULL,NULL,''),
('K3','1.0.0','active','macro','["TW"]',NULL,'{"criterion":"基礎設施成熟度","threshold":"基建利用率上升＋監管框架落地"}',NULL,'K3 電力/網絡/支付/法規載體到位度','next_tradable_bar','無',NULL,NULL,''),
('K4','1.0.0','active','macro','["TW"]',NULL,'{"criterion":"殺手級應用出現","threshold":"單一應用收入/用戶規模可獨立核實"}',NULL,'K4 一個『單獨成立』的應用養起產業','next_tradable_bar','無',NULL,NULL,''),
('K5','1.0.0','active','macro','["TW"]',NULL,'{"criterion":"資本開支週期位置","threshold":"capex 增速 vs 收入增速缺口；產能利用率；再融資依賴度"}',NULL,'K5 判『而家買係唔係死路』（K5-K6 一組）：早段擴張定晚段過度建設','next_tradable_bar','無',NULL,NULL,'三輪浪潮殺傷力全部來自 K5 晚段＋K6 缺口'),
('K6','1.0.0','active','macro','["TW"]',NULL,'{"criterion":"盈利模式成立","threshold":"≥2 間上市公司：經營現金流為正＋連續兩季加速"}',NULL,'K6 真實經營利潤驗證（非補貼/非發幣）','next_tradable_bar','無',NULL,NULL,'代價聲明：2000 年 K6 會篩走未盈利 Amazon——組合級避損工具非單票預言機'),
('G1','1.0.0','active','macro','["TW"]',NULL,'{"criterion":"估值–現金流缺口護欄","alert_threshold":"產業 capex/收入 >5×＝泡沫晚段警報","current_status":"AI 現值 >8×，常開","structural_ban":"只禁新開模型層/概念層倉，唔構成減現倉理由","immediate_trigger":"單季 capex 指引下修＝即時減倉覆核觸發器"}',NULL,'G1 泡沫溫度計＋結構禁令細則（首席判決）','next_tradable_bar','無（常開護欄）',NULL,NULL,'與量化腿並行校驗（W3）；注意與台賬 G1/G2 實盤準入雙門（M 里程碑）嚴格區分'),
('G2','1.0.0','active','macro','["TW"]',NULL,'{"criterion":"負樣本測試","threshold":"主題熱潮中增發/offering 次數月度統計＋內部人減持頻率","hook":"掛 R4＋第六問"}',NULL,'G2 『邊個喺度賣』供給端測試','next_tradable_bar','無',NULL,NULL,''),
('W1','1.0.0','active','macro','["TW"]',NULL,'{"introduction":"只可觀察＋模擬盤；真錢只買已過 K6 的賣水人；導入期標的合計≤主題倉 1/3（≈6-7%）；單票終身≤2% 期權型","bubble":"只持有過 W2 篩查的倖存者候選；純概念股一律不買；R2 試倉 1/3＋收盤確認；破位即走唔補","washout":"遺囑式倖存者名單分批；R8 四件套＋P0/T+1；首批≤目標倉 1/3"}',NULL,'W1 浪潮階段×倉位矩陣','next_tradable_bar','階段判定隨產業數據季度更新',NULL,NULL,''),
('W2','1.0.0','active','macro','["TW"]',NULL,'{"pass_bar":"10 項≥7/10 先夠格入倖存者候選池","items":["真實收入≥50% YoY（財報可核）","backlog/訂單可獨立核實","毛利率方向向上或穩定","現金跑道≥24 個月","過去 12 個月無大幅折讓增發（G2）","lock-up 解禁日曆否決權（R5）","內部人淨賣出頻率未失控","前兩大客戶收入集中度<60%","利息覆蓋>5× 或淨現金","有一個唔靠新融資都活得落的業務閉環"],"combined":"與 C1（估值折讓）＋C10（Stage 2）併組『資格三件套』"}',NULL,'W2 倖存者候選 vs 純概念股篩查','next_tradable_bar','無',NULL,NULL,'主題股入池資格審查掛載'),
('W3','1.0.0','active','macro','["TW"]',NULL,'{"g1_gap":"產業 capex/應用收入>5×＝警報（AI>8× 常開）；單季 capex 增速環比轉負＝主警報","debt_financed_capex":"capex 由現金流轉向債券/私募信貸＝晚段確認","supply_side":"增發頻率（G2）/內部人減持/解禁潮","cross_check":"與 C18 交叉驗證；銜接 SPY 748.8 砍半線、L2→L3 觸發器、E1"}',NULL,'W3 泡沫晚期警報（G1 量化，與量化腿並行校驗）','next_tradable_bar','無',NULL,NULL,''),
('W4','1.0.0','active','macro','["TW"]',NULL,'{"minus80_assumption":"任何倖存者候選都要假設 -80% 級回撤會發生","no_bottom_fishing":"出清期入場必須 R8 四件套＋T+1 確認，唔用跌五成神仙價錨","survivor_recheck":"名單爆破後按 K6 重新打分","profit_recycle":"R7 利潤單向沉澱定期執行"}',NULL,'W4 爆破前後倉位處理（歷史錨：AMZN -94%/BTC -84%/-77%）','next_tradable_bar','無',NULL,NULL,''),
('W5','1.0.0','active','macro','["TW"]',NULL,'{"ai_posture":"AI＝採用期中段＋泡沫晚段特徵並存；唔清倉（K2/K4 真＋芯片層 K6 真），新倉只准賣水人＋過 W2","next_research":"穩定幣/代幣化＋核能/SMR 鏈（Q4 產業周期儀表板常規欄目，宏觀主理）","watchlist":"量子/BCI 零倉觀察；翻案條件=利率見頂（12/10 決議後）＋K4 首個可核實收入案例"}',NULL,'W5 2026 當前裁決（本群姿態）','next_tradable_bar','隨季度產業數據重判',NULL,NULL,'');

-- ③ 載入後驗收查詢（預期：69 個別規則行＋7 佔位行 retired）
SELECT rule_id, version, status, COUNT(*) c FROM rules GROUP BY rule_id, version, status ORDER BY rule_id, version;
SELECT status, COUNT(*) FROM rules WHERE rule_id LIKE '%.%' OR rule_id REGEXP '^[CRNDKWG][0-9]' GROUP BY status;