-- =====================================================================
-- SQLite 九表測試基座 DDL（定稿 v1.1.0，2026-10-11）｜方法學線 P1② 交付件
-- 作者：資深量化技術專家｜雙軌定位（依全棧《落地報告與雙軌定案_20261011》）：
--   · MySQL warren_learning_db 九表 = 唯一事實源（單寫者=全棧 ledger 服務）
--   · 本 SQLite 基座 = 同構測試基座（單元測試/引擎試跑/管道本地緩存）
--   · 不雙寫、不自動同步；結構漂移以本檔 vs MySQL DDL 對照表為準（見檔尾）
-- 上游：外部評審兩文件 9 張全集合併定稿（映射見 MySQL DDL v1.0.0 檔頭）
-- 本版 v1.1.0 增量＝首席《reason_code_registry_v1_20261011.html》八類收編落點：
--   · decision.reason_code 枚舉換為首席八類（七類舊枚舉收編映射見 reasoncode_enum_20261011.yaml）
--   · decision 增六字段最小集＋override_log 最小七列落點（一表承載，不另立 override_log）
-- 方言翻譯規則：ENUM→TEXT+CHECK（SQLite 強制執行 CHECK，此處比 MySQL 5.7 更嚴）；
--   DATETIME→TEXT（ISO-8601，UTC 約定，微秒精度由寫入方保證）；JSON→TEXT+json_valid；
--   AUTO_INCREMENT→INTEGER PRIMARY KEY AUTOINCREMENT；`signal` 在 SQLite 非保留字，仍加引號保持兩端一致
-- 用法：PRAGMA foreign_keys=ON;  後按序執行；載入種子見 規則收編種子_20261011.sqlite.sql
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ── 1/9 instrument_master ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS instrument_master (
  instrument_id        TEXT    NOT NULL PRIMARY KEY,              -- 永久標的ID（跨代碼變更穩定）
  symbol_current       TEXT    NOT NULL,                          -- 現用代碼（02269.HK / CVX.N / 600519.SH）
  name                 TEXT    NULL,
  exchange             TEXT    NOT NULL,                          -- HKEX/NYSE/NASDAQ/SSE/…
  market               TEXT    NOT NULL DEFAULT 'OTHER' CHECK (market IN ('US','HK','CN','OTHER')),
  currency             TEXT    NOT NULL,                          -- ISO 4217
  timezone             TEXT    NOT NULL DEFAULT 'UTC',            -- IANA
  status               TEXT    NOT NULL DEFAULT 'active'
                       CHECK (status IN ('active','watch','removed','forbidden','delisted')),
  symbol_history       TEXT    NULL CHECK (symbol_history IS NULL OR json_valid(symbol_history)),
  corporate_action_note TEXT   NULL,
  notes                TEXT    NULL,
  created_at           TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at           TEXT    NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_im_symbol_current ON instrument_master (symbol_current);
CREATE INDEX IF NOT EXISTS idx_im_market_status ON instrument_master (market, status);

-- ── 2/9 market_snapshot（原 data_runs 批次語義併入：run_id/schema_version/code_commit） ──
CREATE TABLE IF NOT EXISTS market_snapshot (
  snapshot_id     TEXT    NOT NULL PRIMARY KEY,                    -- SNAP-…
  instrument_id   TEXT    NOT NULL,
  as_of_time      TEXT    NOT NULL,                                -- 數據截至時點（UTC）
  as_of_tz        TEXT    NOT NULL DEFAULT 'UTC',                  -- 原時區（HKT/ET/…）
  source          TEXT    NOT NULL,
  source_url      TEXT    NULL,
  adjustment_flag TEXT    NOT NULL DEFAULT 'raw'
                  CHECK (adjustment_flag IN ('raw','forward_adjusted','backward_adjusted')),
  data_hash       TEXT    NOT NULL,                                -- payload sha256
  payload_path    TEXT    NULL,                                    -- 行情大檔不入庫，只存指針
  row_count       INTEGER NULL,
  schema_version  TEXT    NULL,                                    -- Manifest v2 schema 版本
  run_id          TEXT    NOT NULL,                                -- 管道批次（原 data_runs 語義）
  code_commit     TEXT    NULL,
  quality_status  TEXT    NOT NULL
                  CHECK (quality_status IN ('verified','suspect','failed','stale','manual_pending')),
  quality_score   NUMERIC NULL,
  missing_status  TEXT    NULL
                  CHECK (missing_status IS NULL OR missing_status IN
                  ('not_applicable','not_available','failed','manual_pending','verified')),
  notes           TEXT    NULL,
  created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (instrument_id) REFERENCES instrument_master (instrument_id)
);
CREATE INDEX IF NOT EXISTS idx_ms_instrument ON market_snapshot (instrument_id, as_of_time);
CREATE INDEX IF NOT EXISTS idx_ms_run ON market_snapshot (run_id);

-- ── 3/9 experiment（試驗登記冊：DSR/PBO 試驗次數底冊） ─────────────────
CREATE TABLE IF NOT EXISTS experiment (
  experiment_id  TEXT    NOT NULL PRIMARY KEY,                      -- EXP-…
  title          TEXT    NOT NULL,
  hypothesis     TEXT    NOT NULL,                                  -- 預註冊假設（禁止只寫方向）
  rule_ids       TEXT    NULL CHECK (rule_ids IS NULL OR json_valid(rule_ids)),
  primary_metric TEXT    NULL,
  benchmark      TEXT    NULL,
  pass_criteria  TEXT    NULL,                                      -- go/no-go 預註冊門檻
  max_trials     INTEGER NULL,
  trials_used    INTEGER NOT NULL DEFAULT 0,
  status         TEXT    NOT NULL DEFAULT 'pre_registered'
                 CHECK (status IN ('pre_registered','running','completed','aborted')),
  result_summary TEXT    NULL CHECK (result_summary IS NULL OR json_valid(result_summary)),
  owner          TEXT    NULL,
  started_at     TEXT    NULL,
  finished_at    TEXT    NULL,
  notes          TEXT    NULL,
  created_at     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_exp_status ON experiment (status);

-- ── 4/9 rules（註冊冊：YAML 元數據＋Python 主體混合模式） ──────────────
CREATE TABLE IF NOT EXISTS rules (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,                  -- 內部代理鍵（supersedes 鏈用）
  rule_id       TEXT    NOT NULL,                                   -- C/R/N/D/K/W/G/P0…
  version       TEXT    NOT NULL,                                   -- semver
  status        TEXT    NOT NULL DEFAULT 'registered'
                CHECK (status IN ('registered','active','frozen','retired','rejected')),
  owner         TEXT    NOT NULL,
  scope         TEXT    NULL CHECK (scope IS NULL OR json_valid(scope)),
  inputs        TEXT    NULL CHECK (inputs IS NULL OR json_valid(inputs)),
  parameters    TEXT    NULL CHECK (parameters IS NULL OR json_valid(parameters)),
  logic_ref     TEXT    NULL,                                       -- module.path::func（含單測）
  logic_desc    TEXT    NULL,
  entry_effective TEXT  NOT NULL DEFAULT 'next_tradable_bar'
                CHECK (entry_effective IN ('next_tradable_bar','same_bar_close','event_window')),
  invalidation  TEXT    NULL,
  validation_experiment_id TEXT NULL,
  supersedes_id INTEGER NULL,
  approved_by   TEXT    NULL,
  approved_at   TEXT    NULL,
  notes         TEXT    NULL,
  created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (supersedes_id) REFERENCES rules (id),
  FOREIGN KEY (validation_experiment_id) REFERENCES experiment (experiment_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_rules_id_version ON rules (rule_id, version);
CREATE INDEX IF NOT EXISTS idx_rules_status ON rules (status);

-- ── 5/9 "signal"（訊號與成交分離第一環） ─────────────────────────────
CREATE TABLE IF NOT EXISTS "signal" (
  signal_id       TEXT    NOT NULL PRIMARY KEY,
  instrument_id   TEXT    NOT NULL,
  rule_id         TEXT    NOT NULL,
  rule_version    TEXT    NOT NULL,
  direction       TEXT    NOT NULL CHECK (direction IN ('long','short','reduce','exit')),
  as_of_time      TEXT    NOT NULL,                                 -- 觸發時點（UTC）
  valid_until     TEXT    NULL,
  entry_condition TEXT    NULL,
  exit_condition  TEXT    NULL,
  confidence      NUMERIC NULL,
  snapshot_id     TEXT    NOT NULL,                                 -- 凍結快照引用
  run_id          TEXT    NOT NULL,                                 -- 數據批次冗餘欄（可重放最小集）
  status          TEXT    NOT NULL DEFAULT 'open'
                  CHECK (status IN ('open','expired','consumed','cancelled')),
  notes           TEXT    NULL,
  created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (instrument_id) REFERENCES instrument_master (instrument_id),
  FOREIGN KEY (snapshot_id) REFERENCES market_snapshot (snapshot_id),
  FOREIGN KEY (rule_id, rule_version) REFERENCES rules (rule_id, version)
);
CREATE INDEX IF NOT EXISTS idx_sig_instrument ON "signal" (instrument_id, as_of_time);
CREATE INDEX IF NOT EXISTS idx_sig_rule ON "signal" (rule_id, rule_version);
CREATE INDEX IF NOT EXISTS idx_sig_status ON "signal" (status);

-- ── 6/9 decision（裁決表：判例庫機檢化落點｜v1.1.0 首席八類收編版） ─────
-- delta vs MySQL DDL v1.0.0：reason_code 八類換版＋六字段最小集＋override 最小七列落點
-- （MySQL 側對齊 ALTER 見 MySQL九表_reasoncode對齊delta_20261011.sql，由全棧單寫者執行）
CREATE TABLE IF NOT EXISTS decision (
  decision_id       TEXT    NOT NULL PRIMARY KEY,
  signal_id         TEXT    NULL,                                   -- 否決/override 可無訊號
  chief_verdict     TEXT    NOT NULL CHECK (chief_verdict IN ('approve','reject','modify','defer')),
  -- 首席八類終版（reason_code_registry_v1_20261011.html 唯一基準；一主一輔）
  reason_code       TEXT    NULL CHECK (reason_code IS NULL OR reason_code IN
                    ('DATA_CONFLICT','MODEL_DISAGREEMENT','HUMAN_OVERRIDE','EXECUTION_SLIP',
                     'RULE_VIOLATION','GAP_FILL','LESSON_LEARNED','REGIME_CHANGE')),
  reason_code_sub   TEXT    NULL CHECK (reason_code_sub IS NULL OR reason_code_sub IN
                    ('DATA_CONFLICT','MODEL_DISAGREEMENT','HUMAN_OVERRIDE','EXECUTION_SLIP',
                     'RULE_VIOLATION','GAP_FILL','LESSON_LEARNED','REGIME_CHANGE')),
  -- 六字段最小集（code_id=reason_code(+sub)；as_of_time/snapshot_id/rule_ref/evidence/owner）
  as_of_time        TEXT    NULL,                                   -- 判定時點 UTC；不可回填篡改
  as_of_tz          TEXT    NOT NULL DEFAULT 'UTC',                 -- 雙時戳原時區（HKT/ET/…）
  snapshot_id       TEXT    NULL,                                   -- 判定所依據的凍結快照
  rule_ref          TEXT    NULL,                                   -- 收編 rule_id；無規則來源填 'N-A'
  evidence          TEXT    NULL CHECK (evidence IS NULL OR length(evidence) <= 300),
  owner             TEXT    NULL CHECK (owner IS NULL OR owner IN
                    ('chief','quantitative','macro','fullstack','general','user')),
  rationale         TEXT    NULL,
  -- override_log 最小七列落點（override_id 用 decision_id 前綴 OV-；不另立表）
  override_object   TEXT    NULL,                                   -- 被改對象，帶原值→新值
  override_original TEXT    NULL,                                   -- 原始建議全記錄
  override_reason   TEXT    NULL,                                   -- 用戶裁定/首席改判/緊急風控＋一句話依據
  override_validity TEXT    NULL
                    CHECK (override_validity IS NULL OR override_validity IN ('one_shot','term','permanent')),
  override_deadline TEXT    NULL,                                   -- review_due：復檢日（到期周檢亮紅）
  override_outcome  TEXT    NULL,                                   -- 三個月增值分析回填欄
  notes             TEXT    NULL,
  created_at        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (signal_id) REFERENCES "signal" (signal_id),
  FOREIGN KEY (snapshot_id) REFERENCES market_snapshot (snapshot_id)
);
CREATE INDEX IF NOT EXISTS idx_dec_signal ON decision (signal_id);
CREATE INDEX IF NOT EXISTS idx_dec_reason ON decision (reason_code);
CREATE INDEX IF NOT EXISTS idx_dec_rule_ref ON decision (rule_ref);

-- ── 7/9 paper_order ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS paper_order (
  order_id          TEXT    NOT NULL PRIMARY KEY,
  signal_id         TEXT    NULL,
  decision_id       TEXT    NULL,
  instrument_id     TEXT    NOT NULL,
  side              TEXT    NOT NULL CHECK (side IN ('buy','sell')),
  order_type        TEXT    NOT NULL CHECK (order_type IN ('market','limit')),
  limit_price       NUMERIC NULL,
  quantity          NUMERIC NOT NULL,
  currency          TEXT    NOT NULL,
  valid_until       TEXT    NULL,
  event_window_flag INTEGER NOT NULL DEFAULT 0 CHECK (event_window_flag IN (0,1)),  -- 事件窗只減不加
  risk_check_passed INTEGER NOT NULL DEFAULT 0 CHECK (risk_check_passed IN (0,1)),    -- 五閘風檢
  risk_note         TEXT    NULL,
  status            TEXT    NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','filled','partially_filled','expired','rejected','cancelled')),
  created_by        TEXT    NULL,
  notes             TEXT    NULL,
  created_at        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (signal_id) REFERENCES "signal" (signal_id),
  FOREIGN KEY (decision_id) REFERENCES decision (decision_id),
  FOREIGN KEY (instrument_id) REFERENCES instrument_master (instrument_id)
);
CREATE INDEX IF NOT EXISTS idx_po_instrument ON paper_order (instrument_id);
CREATE INDEX IF NOT EXISTS idx_po_status ON paper_order (status);

-- ── 8/9 paper_fill（三地微結構規格見 P1③ 規格書；venue_session 記 notes 前綴協議） ──
CREATE TABLE IF NOT EXISTS paper_fill (
  fill_id        TEXT    NOT NULL PRIMARY KEY,
  order_id       TEXT    NOT NULL,
  fill_price     NUMERIC NOT NULL,
  quantity       NUMERIC NOT NULL,
  fill_time      TEXT    NOT NULL,                                 -- 成交時點 UTC；假設=訊號確認後下一可成交 bar
  slippage       NUMERIC NULL,
  commission     NUMERIC NULL,
  tax_fee        NUMERIC NULL,
  liquidity_note TEXT    NULL,                                    -- 流動性拒絕原因（拒單率統計源；含場次前綴協議）
  notes          TEXT    NULL,
  created_at     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (order_id) REFERENCES paper_order (order_id)
);
CREATE INDEX IF NOT EXISTS idx_pf_order ON paper_fill (order_id);

-- ── 9/9 position_lot ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS position_lot (
  lot_id             TEXT    NOT NULL PRIMARY KEY,
  instrument_id      TEXT    NOT NULL,
  open_fill_id       TEXT    NULL,
  close_fill_id      TEXT    NULL,
  quantity_open      NUMERIC NOT NULL,
  quantity_remaining NUMERIC NOT NULL,
  avg_cost           NUMERIC NOT NULL,
  currency           TEXT    NOT NULL,
  stop_loss          NUMERIC NULL,
  mae                NUMERIC NULL,                                 -- Maximum Adverse Excursion
  mfe                NUMERIC NULL,                                 -- Maximum Favorable Excursion
  r_multiple         NUMERIC NULL,
  status             TEXT    NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed')),
  exit_reason_code   TEXT    NULL CHECK (exit_reason_code IS NULL OR exit_reason_code IN
                     ('STOP_HIT','MA_SLIDE_EXIT','EVENT_WINDOW_REDUCE','TARGET_HIT','MANUAL','REBALANCE','DATA_INVALID')),
  exit_note          TEXT    NULL,
  notes              TEXT    NULL,
  opened_at          TEXT    NULL,
  closed_at          TEXT    NULL,
  created_at         TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (instrument_id) REFERENCES instrument_master (instrument_id),
  FOREIGN KEY (open_fill_id) REFERENCES paper_fill (fill_id),
  FOREIGN KEY (close_fill_id) REFERENCES paper_fill (fill_id)
);
CREATE INDEX IF NOT EXISTS idx_pl_instrument ON position_lot (instrument_id, status);

-- =====================================================================
-- 附：與 MySQL DDL v1.0.0＋reasoncode delta 的結構對照（漂移檢查清單）
--   instrument_master/experiment/rules/"signal"/paper_order/paper_fill/position_lot：同構直譯
--   market_snapshot：同構直譯（run_id 承載 data_runs 語義）
--   decision：本檔已含首席八類＋六字段＋override 落點＝v1.1.0 目標結構；
--     MySQL 側現為 v1.0.0 結構，須由全棧執行 MySQL九表_reasoncode對齊delta_20261011.sql 後兩端同構
--   CHECK 約束：SQLite 端為硬約束；MySQL 5.7 端以 ENUM/應用層承載（全棧既定適配）
--   時間戳：SQLite CURRENT_TIMESTAMP 秒級；微秒由寫入方（引擎/ledger 服務）保證
-- =====================================================================
