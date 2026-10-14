-- ============================================================
-- D4 建表腿 · nav_daily DDL · v1.1（DDL 凍結版 2026-10-12 02:5x HKT）
-- 執行: 全棧開發 · warren_learning_db (CynosDB MySQL 5.7.18) · 已實際建成並回填
-- 依據: 裁決書 VG-R1 §三 D4① ＋ 量化腿《nav_daily 一致性校驗方案》§八
--       ＋ 通用助手《周檢 SOP 修訂件》§三接口契約
-- 版本史: v1.0 (02:13, 七字段/DECIMAL(20,4)/date 列名) → v1.1 對齊凍結（本版）:
--   ①date→nav_date ②DECIMAL(20,4)→(18,6) ③增補 currency/price_source/computed_by/as_of_time/as_of_tz
--   ④data_run_id VARCHAR(128) NOT NULL＋四前綴值域（mv2:/freeze:/manual:/golden:）
-- 本檔=腳本 mysql_nav_daily_migration_20261012_v11.py 內 DDL_NAV_DAILY 單一事實源導出（逐字一致）。
-- 冪等可重跑; 憑據一律環境變數注入, 本檔零憑據。
-- ============================================================
CREATE TABLE IF NOT EXISTS nav_daily (
  nav_date               DATE          NOT NULL COMMENT '淨值日期＝記賬日（裁決書D4①字段date落表列名；週五行=SOP第0步責任腿，容量=美股交易日日頻，L1連續性由checker承接）',
  total_nav              DECIMAL(18,6) NOT NULL COMMENT '組合總淨值（USD）',
  layer_a                DECIMAL(18,6) NOT NULL COMMENT 'A層淨值＝EW(SPY,QQQ,GLDM)×50%',
  layer_b                DECIMAL(18,6) NOT NULL COMMENT 'B層淨值＝EW(SPCX,ZETA,NOW)×30%',
  cash                   DECIMAL(18,6) NOT NULL COMMENT '現金淨值＝20%（殘差列 cash=total−a−b 保障恒等式逐位成立）',
  currency               CHAR(3)       NOT NULL DEFAULT 'USD' COMMENT '幣種（量化§八：單值USD）',
  price_source           ENUM('DAILY_CLOSE_PROXY') NOT NULL DEFAULT 'DAILY_CLOSE_PROXY' COMMENT '取價口徑（P1③枚舉；出現第二值=口徑漂移，須走§七升版）',
  proxy_universe_version VARCHAR(64)   NOT NULL COMMENT '代理宇宙版本錨（D3）。定稿值 dd_v1.1_pool20261010_ledgerV2',
  data_run_id            VARCHAR(128)  NOT NULL COMMENT '數據血統引用（弱引用無FK）。值域四前綴：mv2:<run_id>｜freeze:<檔名>#<sha8>｜manual:<底稿名>#<sha8>｜golden:<檔名>#<sha8>',
  computed_by            ENUM('engineering','manual','checker') NOT NULL DEFAULT 'engineering' COMMENT '寫入方（量化§八）',
  as_of_time             DATETIME(6)   NOT NULL COMMENT '取價截至時點（UTC，沿 decision 六字段約定）',
  as_of_tz               VARCHAR(40)   NOT NULL DEFAULT 'UTC' COMMENT '原時區（沿 decision 六字段約定）',
  notes                  VARCHAR(512)  NULL     COMMENT '註記（記賬來源/手算兜底旗標等）',
  created_at             DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '入庫時間（UTC 約定）',
  updated_at             DATETIME(6)   NULL     COMMENT '修訂時間（UTC 約定）',
  PRIMARY KEY (nav_date),
  KEY idx_nd_run (data_run_id),
  KEY idx_nd_universe (proxy_universe_version),
  KEY idx_nd_computed (computed_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='淨值日記賬（VG-R1 D4①·DDL v1.1凍結版）：恒等式 total=layer_a+layer_b+cash 查詢側校驗（5.7 CHECK無效）；
時序鐵律 R-1 先落庫後消費；checker 只讀賬號 nav_checker_ro（GRANT SELECT，密碼 env 注入）由全棧於 checker 上線時創建；
校驗報告落地=shared/nav_daily一致性校驗包_量化腿_20261012/checker_reports/<date>_checker_report.json'
