-- =====================================================================
-- warren_learning_db 九表賬本 DDL（定稿 v1.0.0，2026-10-11）
-- 目標實例：騰訊雲 CynosDB MySQL 5.7.18（連接參數一律環境變數注入，本檔零憑據）
-- 來源：外部評審兩文件表目合併定稿（9 張全集）＋群內量化腿 schema 結論
--   · 文件1《GitHub+SQLite 架構建議》八表：instruments/data_runs/rules/signals/
--     decisions/paper_orders/paper_fills/positions
--   · 文件2《系統深度評審》八表：instrument_master/market_snapshot/signal/decision/
--     paper_order/paper_fill/position_lot/experiment
--   · 合併映射：instruments≡instrument_master、positions≡position_lot（6 對同義）；
--     data_runs 批次語義併入 market_snapshot（run_id/schema_version/code_commit/row_count/
--     quality_status 欄位），檔案級完整 Manifest v2 仍存管道側 → 9 張定稿
--   · C/R/N/D/K/W/G 收編 rules.rule_id；logic 混合模式＝元數據/參數(JSON/YAML)+Python 主體(logic_ref)
-- 5.7 適配：utf8mb4_unicode_ci（無 0900）、不用 CHECK（5.7 忽略，ENUM 已足）、JSON 可用(5.7.8+)
-- 代理適配：全庫 UTC 存儲由應用層約定（連接復用代理禁 SET SESSION/@@變量）
-- 隔離：僅九表白名單；既有他方表（daily_notes/rpg_progress/xp_log）零接觸
-- 幂等：CREATE TABLE IF NOT EXISTS；順序即 FK 依賴順序
-- =====================================================================

-- ── 1/9 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS instrument_master (
  instrument_id        VARCHAR(32)  NOT NULL COMMENT '永久標的ID（跨代碼變更穩定）',
  symbol_current       VARCHAR(24)  NOT NULL COMMENT '現用代碼（例：02269.HK / CVX.N / 600519.SH）',
  name                 VARCHAR(128) NULL     COMMENT '標的名稱',
  exchange             VARCHAR(16)  NOT NULL COMMENT '交易所（HKEX/NYSE/NASDAQ/SSE/…）',
  market               ENUM('US','HK','CN','OTHER') NOT NULL DEFAULT 'OTHER' COMMENT '市場',
  currency             CHAR(3)      NOT NULL COMMENT '計價幣種（ISO 4217）',
  timezone             VARCHAR(40)  NOT NULL DEFAULT 'UTC' COMMENT '本地時區（IANA）',
  status               ENUM('active','watch','removed','forbidden','delisted') NOT NULL DEFAULT 'active' COMMENT '池內狀態（移出/留觀/禁止/新進）',
  symbol_history       JSON         NULL     COMMENT '代碼變更史 [{symbol,from,to,source}]（藥明類混淆判例防線）',
  corporate_action_note VARCHAR(512) NULL    COMMENT '拆股/復權/停牌註記（CRWD 拆股判例防線）',
  notes                VARCHAR(512) NULL,
  created_at           DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '入庫時間（UTC 約定）',
  updated_at           DATETIME(6)  NULL,
  PRIMARY KEY (instrument_id),
  UNIQUE KEY uq_im_symbol_current (symbol_current),
  KEY idx_im_market_status (market, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='標的主檔：永久ID/代碼史/幣種/時區';

-- ── 2/9 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS market_snapshot (
  snapshot_id     VARCHAR(40)  NOT NULL COMMENT '凍結快照ID（SNAP-…）',
  instrument_id   VARCHAR(32)  NOT NULL,
  as_of_time      DATETIME(6)  NOT NULL COMMENT '數據截至時點（UTC）',
  as_of_tz        VARCHAR(40)  NOT NULL DEFAULT 'UTC' COMMENT '原時區（HKT/ET/…）',
  source          VARCHAR(64)  NOT NULL COMMENT '來源（騰訊雙端/AAStocks/FRED/…）',
  source_url      VARCHAR(512) NULL,
  adjustment_flag ENUM('raw','forward_adjusted','backward_adjusted') NOT NULL DEFAULT 'raw' COMMENT '復權旗標',
  data_hash       CHAR(64)     NOT NULL COMMENT 'payload sha256（不可重放即不可信）',
  payload_path    VARCHAR(512) NULL COMMENT '原始檔位置（行情大檔不入庫，只存指針）',
  row_count       INT          NULL,
  schema_version  VARCHAR(16)  NULL COMMENT 'Manifest v2 schema 版本',
  run_id          VARCHAR(40)  NOT NULL COMMENT '管道批次 run_id（原 data_runs 語義併入）',
  code_commit     CHAR(40)     NULL COMMENT '抓取代碼 git commit',
  quality_status  ENUM('verified','suspect','failed','stale','manual_pending') NOT NULL COMMENT '品質狀態（缺失枚舉化）',
  quality_score   DECIMAL(5,2) NULL,
  missing_status  ENUM('not_applicable','not_available','failed','manual_pending','verified') NULL COMMENT '缺失狀態枚舉（P0 共識）',
  notes           VARCHAR(512) NULL,
  created_at      DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'UTC 約定',
  PRIMARY KEY (snapshot_id),
  KEY idx_ms_instrument (instrument_id, as_of_time),
  KEY idx_ms_run (run_id),
  CONSTRAINT fk_ms_instrument FOREIGN KEY (instrument_id) REFERENCES instrument_master (instrument_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='數據凍結層：訊號可重放的最小前提';

-- ── 3/9 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS experiment (
  experiment_id  VARCHAR(40) NOT NULL COMMENT '試驗ID（EXP-…）',
  title          VARCHAR(256) NOT NULL,
  hypothesis     TEXT        NOT NULL COMMENT '預先定義假設（禁止只寫方向）',
  rule_ids       JSON        NULL     COMMENT '涉及規則 ["C@1.0.0",…]',
  primary_metric VARCHAR(64) NULL     COMMENT '主指標（expectancy/MAE-MFE…）',
  benchmark      VARCHAR(64) NULL     COMMENT '比較基準（buy_and_hold/ma_only/fixed_stop）',
  pass_criteria  TEXT        NULL     COMMENT 'go/no-go 預註冊門檻',
  max_trials     INT         NULL     COMMENT '試驗次數預算（多重測試上限）',
  trials_used    INT         NOT NULL DEFAULT 0,
  status         ENUM('pre_registered','running','completed','aborted') NOT NULL DEFAULT 'pre_registered',
  result_summary JSON        NULL,
  owner          VARCHAR(32) NULL,
  started_at     DATETIME(6) NULL     COMMENT 'UTC',
  finished_at    DATETIME(6) NULL     COMMENT 'UTC',
  notes          VARCHAR(512) NULL,
  created_at     DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'UTC 約定',
  PRIMARY KEY (experiment_id),
  KEY idx_exp_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='試驗登記冊：DSR/PBO 的試驗次數底冊';

-- ── 4/9 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rules (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '內部代理鍵（supersedes 鏈用）',
  rule_id       VARCHAR(16)  NOT NULL COMMENT '規則家族編號（C/R/N/D/K/W/G/P0…）',
  version       VARCHAR(16)  NOT NULL COMMENT '語義化版本 semver',
  status        ENUM('registered','active','frozen','retired','rejected') NOT NULL DEFAULT 'registered' COMMENT '舊版只可 retired 不可覆寫',
  owner         VARCHAR(32)  NOT NULL COMMENT '規則擁有腿（quantitative/chief/macro）',
  scope         JSON         NULL     COMMENT '適用範圍 ["US","HK","CN"]',
  inputs        JSON         NULL     COMMENT '輸入欄位 [close,volume,ma20]',
  parameters    JSON         NULL     COMMENT '參數（元數據/參數 YAML 化部分）',
  logic_ref     VARCHAR(256) NULL     COMMENT '混合模式：Python 主體引用 module.path::func（含單測）',
  logic_desc    VARCHAR(1024) NULL    COMMENT '邏輯人類可讀摘要',
  entry_effective ENUM('next_tradable_bar','same_bar_close','event_window') NOT NULL DEFAULT 'next_tradable_bar' COMMENT '進場生效時點',
  invalidation  VARCHAR(512) NULL     COMMENT '預寫證偽條件（thesis+invalidation 同構）',
  validation_experiment_id VARCHAR(40) NULL COMMENT '驗證試驗引用',
  supersedes_id INT UNSIGNED NULL COMMENT '被取代版本（版本鏈）',
  approved_by   VARCHAR(64)  NULL,
  approved_at   DATETIME(6)  NULL COMMENT 'UTC',
  notes         VARCHAR(512) NULL,
  created_at    DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'UTC 約定',
  PRIMARY KEY (id),
  UNIQUE KEY uq_rules_id_version (rule_id, version),
  KEY idx_rules_status (status),
  CONSTRAINT fk_rules_supersedes FOREIGN KEY (supersedes_id) REFERENCES rules (id),
  CONSTRAINT fk_rules_experiment FOREIGN KEY (validation_experiment_id) REFERENCES experiment (experiment_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='規則註冊冊：YAML元數據+Python主體混合模式';

-- ── 5/9 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `signal` (
  signal_id       VARCHAR(40)  NOT NULL,
  instrument_id   VARCHAR(32)  NOT NULL,
  rule_id         VARCHAR(16)  NOT NULL,
  rule_version    VARCHAR(16)  NOT NULL,
  direction       ENUM('long','short','reduce','exit') NOT NULL,
  as_of_time      DATETIME(6)  NOT NULL COMMENT '觸發時點（UTC）',
  valid_until     DATETIME(6)  NULL COMMENT '有效期（UTC）',
  entry_condition VARCHAR(1024) NULL,
  exit_condition  VARCHAR(1024) NULL,
  confidence      DECIMAL(5,4) NULL,
  snapshot_id     VARCHAR(40)  NOT NULL COMMENT '凍結快照引用',
  run_id          VARCHAR(40)  NOT NULL COMMENT '數據批次冗餘欄（可重放最小集）',
  status          ENUM('open','expired','consumed','cancelled') NOT NULL DEFAULT 'open',
  notes           VARCHAR(512) NULL,
  created_at      DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'UTC 約定',
  PRIMARY KEY (signal_id),
  KEY idx_sig_instrument (instrument_id, as_of_time),
  KEY idx_sig_rule (rule_id, rule_version),
  KEY idx_sig_status (status),
  CONSTRAINT fk_sig_instrument FOREIGN KEY (instrument_id) REFERENCES instrument_master (instrument_id),
  CONSTRAINT fk_sig_snapshot FOREIGN KEY (snapshot_id) REFERENCES market_snapshot (snapshot_id),
  CONSTRAINT fk_sig_rule FOREIGN KEY (rule_id, rule_version) REFERENCES rules (rule_id, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='訊號表：訊號與成交分離的第一環';

-- ── 6/9 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS decision (
  decision_id       VARCHAR(40) NOT NULL,
  signal_id         VARCHAR(40) NULL COMMENT '否決/override 可無訊號 → NULL',
  chief_verdict     ENUM('approve','reject','modify','defer') NOT NULL COMMENT '首席/終審裁定',
  reason_code       ENUM('DATA_CONFLICT','MODEL_DISAGREEMENT','RISK_CAP','EVENT_BLOCK','STALE_SIGNAL','HUMAN_OVERRIDE','EXECUTION_FAILURE','REGIME_CHANGE') NULL COMMENT '原因碼（七類＋REGIME_CHANGE 增補）',
  rationale         TEXT NULL,
  approved_by       VARCHAR(64) NULL COMMENT '人類終審者（人工批准點）',
  override_original VARCHAR(1024) NULL COMMENT 'override：原始建議全記錄',
  override_reason   VARCHAR(512) NULL,
  override_deadline DATETIME(6) NULL COMMENT 'override 複核期限（UTC）',
  override_outcome  VARCHAR(512) NULL COMMENT '三個月增值分析回填欄',
  notes             VARCHAR(512) NULL,
  created_at        DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'UTC 約定',
  PRIMARY KEY (decision_id),
  KEY idx_dec_signal (signal_id),
  KEY idx_dec_reason (reason_code),
  CONSTRAINT fk_dec_signal FOREIGN KEY (signal_id) REFERENCES `signal` (signal_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='裁決表：判例庫機檢化的落點';

-- ── 7/9 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS paper_order (
  order_id          VARCHAR(40) NOT NULL,
  signal_id         VARCHAR(40) NULL,
  decision_id       VARCHAR(40) NULL,
  instrument_id     VARCHAR(32) NOT NULL,
  side              ENUM('buy','sell') NOT NULL,
  order_type        ENUM('market','limit') NOT NULL,
  limit_price       DECIMAL(18,6) NULL COMMENT '限價（市價單為 NULL）',
  quantity          DECIMAL(18,6) NOT NULL,
  currency          CHAR(3) NOT NULL,
  valid_until       DATETIME(6) NULL COMMENT '有效期（UTC）',
  event_window_flag TINYINT(1) NOT NULL DEFAULT 0 COMMENT '事件窗只減不加限制',
  risk_check_passed TINYINT(1) NOT NULL DEFAULT 0 COMMENT '五閘風檢結果',
  risk_note         VARCHAR(512) NULL,
  status            ENUM('pending','filled','partially_filled','expired','rejected','cancelled') NOT NULL DEFAULT 'pending',
  created_by        VARCHAR(32) NULL,
  notes             VARCHAR(512) NULL,
  created_at        DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'UTC 約定',
  PRIMARY KEY (order_id),
  KEY idx_po_instrument (instrument_id),
  KEY idx_po_status (status),
  CONSTRAINT fk_po_signal FOREIGN KEY (signal_id) REFERENCES `signal` (signal_id),
  CONSTRAINT fk_po_decision FOREIGN KEY (decision_id) REFERENCES decision (decision_id),
  CONSTRAINT fk_po_instrument FOREIGN KEY (instrument_id) REFERENCES instrument_master (instrument_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='紙面訂單：限價/數量/期限/風險限制';

-- ── 8/9 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS paper_fill (
  fill_id        VARCHAR(40) NOT NULL,
  order_id       VARCHAR(40) NOT NULL,
  fill_price     DECIMAL(18,6) NOT NULL,
  quantity       DECIMAL(18,6) NOT NULL,
  fill_time      DATETIME(6) NOT NULL COMMENT '成交時點（UTC；假設=訊號確認後下一可成交 bar）',
  slippage       DECIMAL(18,6) NULL,
  commission     DECIMAL(18,6) NULL,
  tax_fee        DECIMAL(18,6) NULL,
  liquidity_note VARCHAR(512) NULL COMMENT '流動性拒絕原因（拒單率統計源）',
  notes          VARCHAR(512) NULL,
  created_at     DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'UTC 約定',
  PRIMARY KEY (fill_id),
  KEY idx_pf_order (order_id),
  CONSTRAINT fk_pf_order FOREIGN KEY (order_id) REFERENCES paper_order (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='紙面成交：模擬成交價/滑點/費用';

-- ── 9/9 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS position_lot (
  lot_id             VARCHAR(40) NOT NULL,
  instrument_id      VARCHAR(32) NOT NULL,
  open_fill_id       VARCHAR(40) NULL,
  close_fill_id      VARCHAR(40) NULL,
  quantity_open      DECIMAL(18,6) NOT NULL,
  quantity_remaining DECIMAL(18,6) NOT NULL,
  avg_cost           DECIMAL(18,6) NOT NULL,
  currency           CHAR(3) NOT NULL,
  stop_loss          DECIMAL(18,6) NULL,
  mae                DECIMAL(18,6) NULL COMMENT 'Maximum Adverse Excursion',
  mfe                DECIMAL(18,6) NULL COMMENT 'Maximum Favorable Excursion',
  r_multiple         DECIMAL(10,4) NULL,
  status             ENUM('open','closed') NOT NULL DEFAULT 'open',
  exit_reason_code   ENUM('STOP_HIT','MA_SLIDE_EXIT','EVENT_WINDOW_REDUCE','TARGET_HIT','MANUAL','REBALANCE','DATA_INVALID') NULL COMMENT '退出原因碼',
  exit_note          VARCHAR(512) NULL,
  notes              VARCHAR(512) NULL,
  opened_at          DATETIME(6) NULL COMMENT 'UTC',
  closed_at          DATETIME(6) NULL COMMENT 'UTC',
  created_at         DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'UTC 約定',
  PRIMARY KEY (lot_id),
  KEY idx_pl_instrument (instrument_id, status),
  CONSTRAINT fk_pl_instrument FOREIGN KEY (instrument_id) REFERENCES instrument_master (instrument_id),
  CONSTRAINT fk_pl_open_fill FOREIGN KEY (open_fill_id) REFERENCES paper_fill (fill_id),
  CONSTRAINT fk_pl_close_fill FOREIGN KEY (close_fill_id) REFERENCES paper_fill (fill_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='逐lot持倉：成本/MAE-MFE/止損/退出原因';

