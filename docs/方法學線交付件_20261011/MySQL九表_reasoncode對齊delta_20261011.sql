-- =====================================================================
-- MySQL 九表賬本 reason code 對齊 delta（v1.0.0 → v1.1.0）｜2026-10-11
-- 作者：資深量化技術專家（方法學線 P1②）｜執行者：全棧開發（單寫者原則，人工復核後執行）
-- 唯一基準：首席《reason_code_registry_v1_20261011.html》八類終版＋主輔碼制＋六字段最小集
-- 配套：機讀註冊冊 reasoncode_enum_20261011.yaml（含舊枚舉收編映射）
-- 執行順序：①pre-flight ②枚舉換版 ③新增列 ④存量行數據遷移 ⑤索引 ⑥驗收
-- 注意：MySQL 5.7 無 ADD COLUMN IF NOT EXISTS，本檔單次執行；重跑前先跑 pre-flight 斷言
-- 隔離：僅動 warren_learning_db 九表白名單內 decision 表；他方業務表零接觸
-- =====================================================================

-- ① Pre-flight：確認當前結構為 v1.0.0（reason_code 含 RISK_CAP 舊枚舉且尚無 reason_code_sub 列）
SELECT COLUMN_NAME, COLUMN_TYPE FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA='warren_learning_db' AND TABLE_NAME='decision'
ORDER BY ORDINAL_POSITION;
-- 預期：reason_code 存在（ENUM 舊八值），reason_code_sub 不存在。若已存在 → 本檔已執行過，停止。

-- ② 枚舉換版：舊七類＋REGIME_CHANGE → 首席八類終版
--    （ENUM 換版在 5.7 為表重建；decision 表量級為判例/台賬級，秒級完成）
ALTER TABLE decision
  MODIFY COLUMN reason_code ENUM('DATA_CONFLICT','MODEL_DISAGREEMENT','HUMAN_OVERRIDE','EXECUTION_SLIP',
                                 'RULE_VIOLATION','GAP_FILL','LESSON_LEARNED','REGIME_CHANGE')
  NULL COMMENT '首席八類終版（主碼）；收編映射見 reasoncode_enum_20261011.yaml legacy_enum_mapping';

-- ③ 新增列：輔碼＋六字段最小集（code_id=reason_code(+sub) 本列承載）＋override_log 最小七列落點
ALTER TABLE decision
  ADD COLUMN reason_code_sub ENUM('DATA_CONFLICT','MODEL_DISAGREEMENT','HUMAN_OVERRIDE','EXECUTION_SLIP',
                                  'RULE_VIOLATION','GAP_FILL','LESSON_LEARNED','REGIME_CHANGE')
    NULL COMMENT '輔碼（處置結果）；一單一主一輔，第三碼入 notes' AFTER reason_code,
  ADD COLUMN as_of_time DATETIME(6) NULL COMMENT '判定時點（UTC）＋as_of_tz 雙時戳；不可回填篡改' AFTER reason_code_sub,
  ADD COLUMN as_of_tz VARCHAR(40) NOT NULL DEFAULT 'UTC' COMMENT '原時區（HKT/ET/…）' AFTER as_of_time,
  ADD COLUMN snapshot_id VARCHAR(40) NULL COMMENT '判定所依據凍結快照 FK' AFTER as_of_tz,
  ADD COLUMN rule_ref VARCHAR(16) NULL COMMENT '收編 rule_id；無規則來源填 N-A' AFTER snapshot_id,
  ADD COLUMN evidence VARCHAR(300) NULL COMMENT '判例錨/來源鏈接/雙源標注，≤300字' AFTER rule_ref,
  ADD COLUMN owner ENUM('chief','quantitative','macro','fullstack','general','user') NULL
    COMMENT '記錄腿' AFTER evidence,
  ADD COLUMN override_object VARCHAR(512) NULL COMMENT '被改對象，帶原值→新值（override_log object 落點）' AFTER approved_by,
  ADD COLUMN override_validity ENUM('one_shot','term','permanent') NULL
    COMMENT '一次性/限期/永久（override_log validity 落點）' AFTER override_reason;

-- ④ 存量行數據遷移（依 reasoncode_enum_20261011.yaml legacy_enum_mapping；只打標不重寫敘事）
UPDATE decision SET reason_code='DATA_CONFLICT'
 WHERE reason_code='STALE_SIGNAL';   -- 首席 DATA_CONFLICT 定義明文含「陳舊緩存」
UPDATE decision SET reason_code='EXECUTION_SLIP'
 WHERE reason_code='EXECUTION_FAILURE';  -- 併入 EXECUTION_SLIP 全族
-- RISK_CAP / EVENT_BLOCK：不強行歸類（GAP_FILL=信息缺口，風控攔截非缺口；防濫立）。
-- 語義由 chief_verdict＋rule_ref＋evidence 承載；evidence 補 legacy 標記，交首席周檢定奪是否立碼：
UPDATE decision SET reason_code=NULL,
       evidence=CONCAT('[legacy=RISK_CAP 待周檢定奪] ', COALESCE(evidence,''))
 WHERE reason_code='RISK_CAP';
UPDATE decision SET reason_code=NULL,
       evidence=CONCAT('[legacy=EVENT_BLOCK 待周檢定奪] ', COALESCE(evidence,''))
 WHERE reason_code='EVENT_BLOCK';
-- 舊 override 敘事欄回填 override_object（原值→新值格式）：
UPDATE decision SET override_object=CONCAT('原值=', override_original, '；新值=', COALESCE(override_outcome,''))
 WHERE override_original IS NOT NULL AND override_object IS NULL;

-- ⑤ 索引
ALTER TABLE decision ADD INDEX idx_dec_reason_sub (reason_code_sub);
ALTER TABLE decision ADD INDEX idx_dec_rule_ref (rule_ref);
ALTER TABLE decision ADD CONSTRAINT fk_dec_snapshot FOREIGN KEY (snapshot_id)
  REFERENCES market_snapshot (snapshot_id);

-- ⑥ 驗收（預期全 0 命中）
SELECT COUNT(*) FROM decision WHERE reason_code IN ('STALE_SIGNAL','EXECUTION_FAILURE','RISK_CAP','EVENT_BLOCK'); -- 0
SELECT reason_code, reason_code_sub, COUNT(*) FROM decision GROUP BY reason_code, reason_code_sub;
SELECT COUNT(*) FROM information_schema.COLUMNS
 WHERE TABLE_SCHEMA='warren_learning_db' AND TABLE_NAME='decision'
   AND COLUMN_NAME IN ('reason_code_sub','as_of_time','as_of_tz','snapshot_id','rule_ref',
                       'evidence','owner','override_object','override_validity'); -- 預期 9
-- =====================================================================
-- 對齊後狀態：MySQL decision ≡ SQLite九表測試基座 v1.1.0 decision（同構）；
-- 此後 SQLite 基座自動同步結構漂移由本檔＋DDL 對照表維護。
-- =====================================================================
