#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
warren_learning_db 九表賬本引導腳本（CynosDB MySQL 5.7.18 適配）
================================================================
安全基線：
  - 憑據只經環境變數注入（DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME），本檔零硬編碼；
  - 隔離原則：只在目標庫 warren_learning_db 內操作，只建「九表賬本」名單內的表，
    絕不 DROP / ALTER / 觸碰任何既有表（如 daily_notes / rpg_progress / xp_log）；
  - 代理層限制：避開 SELECT @@variable 與 SET SESSION（會被連接復用代理重置），
    時區/字符集由應用層約定（全庫 UTC 存儲）＋ 表級 DDL 強制（utf8mb4）。
幂等：CREATE TABLE IF NOT EXISTS + INSERT IGNORE，可重複執行。
"""
import os
import sys
import json
import hashlib
import pymysql

REQUIRED_ENV = ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"]

# ── 隔離白名單：本腳本唯一允許建立/寫入的九張表 ──────────────────────────
LEDGER_TABLES = [
    "instrument_master", "market_snapshot", "experiment", "rules",
    "signal", "decision", "paper_order", "paper_fill", "position_lot",
]
# 既有表（他方業務，只讀不碰）：daily_notes / rpg_progress / xp_log
FOREIGN_TABLES_DO_NOT_TOUCH = {"daily_notes", "rpg_progress", "xp_log"}

DDL = [
# ── 1/9 instrument_master 標的主檔（文件1 instruments ＋ 文件2 instrument_master 合併）──
"""CREATE TABLE IF NOT EXISTS instrument_master (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='標的主檔：永久ID/代碼史/幣種/時區'""",

# ── 2/9 market_snapshot 數據凍結快照（文件2 market_snapshot ＋ 文件1 data_runs 批次欄位合併）──
"""CREATE TABLE IF NOT EXISTS market_snapshot (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='數據凍結層：訊號可重放的最小前提'""",

# ── 3/9 experiment 試驗登記冊（P0 共識：go/no-go 預註冊先行）──
"""CREATE TABLE IF NOT EXISTS experiment (
  experiment_id  VARCHAR(40) NOT NULL COMMENT '試驗ID（EXP-…）',
  title          VARCHAR(256) NOT NULL,
  hypothesis     TEXT        NOT NULL COMMENT '預先定義假設（禁止只寫方向）',
  rule_ids       JSON        NULL     COMMENT '涉及規則 [\"C@1.0.0\",…]',
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='試驗登記冊：DSR/PBO 的試驗次數底冊'""",

# ── 4/9 rules 規則註冊冊（C/R/N/D/K/W/G 收編 rule_id；混合模式）──
"""CREATE TABLE IF NOT EXISTS rules (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '內部代理鍵（supersedes 鏈用）',
  rule_id       VARCHAR(16)  NOT NULL COMMENT '規則家族編號（C/R/N/D/K/W/G/P0…）',
  version       VARCHAR(16)  NOT NULL COMMENT '語義化版本 semver',
  status        ENUM('registered','active','frozen','retired','rejected') NOT NULL DEFAULT 'registered' COMMENT '舊版只可 retired 不可覆寫',
  owner         VARCHAR(32)  NOT NULL COMMENT '規則擁有腿（quantitative/chief/macro）',
  scope         JSON         NULL     COMMENT '適用範圍 [\"US\",\"HK\",\"CN\"]',
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='規則註冊冊：YAML元數據+Python主體混合模式'""",

# ── 5/9 `signal` 訊號表（凍結最小集：as_of_time＋rule_version＋run_id；signal 為 MySQL 保留字須反引號）──
"""CREATE TABLE IF NOT EXISTS `signal` (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='訊號表：訊號與成交分離的第一環'""",  # noqa: `signal` 保留字

# ── 6/9 decision 裁決表（reason code 枚舉＋override 全記錄）──
"""CREATE TABLE IF NOT EXISTS decision (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='裁決表：判例庫機檢化的落點'""",

# ── 7/9 paper_order 紙面訂單──
"""CREATE TABLE IF NOT EXISTS paper_order (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='紙面訂單：限價/數量/期限/風險限制'""",

# ── 8/9 paper_fill 紙面成交──
"""CREATE TABLE IF NOT EXISTS paper_fill (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='紙面成交：模擬成交價/滑點/費用'""",

# ── 9/9 position_lot 逐 lot 持倉（文件1 positions ＋ 文件2 position_lot 合併）──
"""CREATE TABLE IF NOT EXISTS position_lot (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='逐lot持倉：成本/MAE-MFE/止損/退出原因'""",
]


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def utc(dt: str) -> str:
    """種子時間一律顯式 UTC 字面量，避免伺服器 session 時區不確定性。"""
    return dt


SEEDS = {
    "instrument_master": [
        ("INST-HK-02269", "02269.HK", "藥明生物", "HKEX", "HK", "HKD", "Asia/Hong_Kong", "active",
         '[{"symbol":"02269.HK","from":"2017-06-13","to":null,"source":"HKEX"}]',
         "種子示例；真實 corporate action 以管道校驗為準", "SEED 最小校驗資料（非正式台賬）"),
        ("INST-US-CVX", "CVX.N", "Chevron", "NYSE", "US", "USD", "America/New_York", "active",
         '[{"symbol":"CVX.N","from":"2001-10-09","to":null,"source":"NYSE"}]',
         "XOM/CVX 區帶誤標判例對照標的", "SEED 最小校驗資料（非正式台賬）"),
        ("INST-CN-600519", "600519.SH", "貴州茅台", "SSE", "CN", "CNY", "Asia/Shanghai", "active",
         '[{"symbol":"600519.SH","from":"2001-08-27","to":null,"source":"SSE"}]',
         None, "SEED 最小校驗資料（非正式台賬）"),
    ],
    # instrument_master 插入語句需自訂（JSON 列），故不套用通用佔位循環
}


def main() -> int:
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        print(json.dumps({"error": f"MISSING_ENV: {missing}"}))
        return 2

    conn = pymysql.connect(
        host=os.environ["DB_HOST"], port=int(os.environ["DB_PORT"]),
        user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"], charset="utf8mb4",
        connect_timeout=15, read_timeout=60, write_timeout=60, autocommit=False,
    )
    report = {"db": None, "existing_tables_before": None, "created": [], "skipped_existing": [],
              "seed_counts": {}, "integrity": {}, "foreign_tables_untouched": sorted(FOREIGN_TABLES_DO_NOT_TOUCH)}
    try:
        with conn.cursor() as cur:
            # ── 隔離斷言：必須在目標庫內 ──
            cur.execute("SELECT DATABASE()")
            report["db"] = cur.fetchone()[0]
            assert report["db"] == os.environ["DB_NAME"], "未連上目標庫，中止"

            cur.execute("SHOW TABLES")
            before = {r[0] for r in cur.fetchall()}
            report["existing_tables_before"] = sorted(before)
            # 隔離斷言：既有表只允許在白名單外，絕不觸碰
            collision = before & set(LEDGER_TABLES)
            report["skipped_existing"] = sorted(collision)

            # ── 建表（僅九表白名單，IF NOT EXISTS）──
            for ddl in DDL:
                tname = ddl.split("CREATE TABLE IF NOT EXISTS ", 1)[1].split(" ", 1)[0].strip("`")
                if tname not in LEDGER_TABLES:
                    raise RuntimeError(f"白名單外表被拒：{tname}")
                cur.execute(ddl)
                (report["created"] if tname not in collision else report["skipped_existing"]).append(tname)
            conn.commit()

            # ── 最小種子校驗數據（INSERT IGNORE 幂等；全部 SEED 標記）──
            seeds_sql = []
            for r in SEEDS["instrument_master"]:
                seeds_sql.append((
                    """INSERT IGNORE INTO instrument_master
                       (instrument_id, symbol_current, name, exchange, market, currency, timezone,
                        status, symbol_history, corporate_action_note, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", r))
            seed_snapshot = ("SNAP-SEED-20261011-001", "INST-HK-02269",
                             utc("2026-10-09 08:00:00.000000"), "Asia/Hong_Kong",
                             "tencent_qt+ifzq_dual_check", None, "raw",
                             sha256("SEED-SNAPSHOT-02269.HK-20261009"), None, 0,
                             "manifest_v2", "RUN-SEED-20261011-001", None,
                             "verified", 100.00, "verified",
                             "SEED 最小校驗資料（非正式台賬）")
            seeds_sql.append((
                """INSERT IGNORE INTO market_snapshot
                   (snapshot_id, instrument_id, as_of_time, as_of_tz, source, source_url,
                    adjustment_flag, data_hash, payload_path, row_count, schema_version, run_id,
                    code_commit, quality_status, quality_score, missing_status, notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", seed_snapshot))
            seed_exp = ("EXP-2026-SEED-001", "P0 突破確認 vs 回調接反事實（種子示範）",
                        "預註冊示範：P0 突破確認制樣本外 expectancy ≥ 回調接基準（正式註冊由量化腿另行預冊）",
                        '["C@1.0.0"]', "expectancy", "ma_only",
                        "OOS expectancy 增量>0 且 bootstrap CI 下界>0", 10, 0,
                        "pre_registered", None, "quantitative", None, None,
                        "SEED 最小校驗資料（非正式台賬）")
            seeds_sql.append((
                """INSERT IGNORE INTO experiment
                   (experiment_id, title, hypothesis, rule_ids, primary_metric, benchmark,
                    pass_criteria, max_trials, trials_used, status, result_summary, owner,
                    started_at, finished_at, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                seed_exp))
            for rid in ["C", "R", "N", "D", "K", "W", "G"]:
                seeds_sql.append((
                    """INSERT IGNORE INTO rules
                       (rule_id, version, status, owner, scope, inputs, parameters, logic_ref,
                        logic_desc, entry_effective, invalidation, notes)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (rid, "1.0.0", "registered", "quantitative", '["US","HK","CN"]', None, None, None,
                     "種子收編佔位：正式參數/logic 待 Rule Registry 四週收編確認（混合模式：YAML 元數據＋Python 主體）",
                     "next_tradable_bar", None,
                     "SEED 最小校驗資料（非正式台賬）；佔位收編 C/R/N/D/K/W/G 編號體系")))
            seed_signal = ("SIG-SEED-20261011-001", "INST-HK-02269", "C", "1.0.0", "long",
                           utc("2026-10-09 08:00:00.000000"), None,
                           "種子示例：非真實觸發", "種子示例：非真實退出", 0.5000,
                           "SNAP-SEED-20261011-001", "RUN-SEED-20261011-001", "open",
                           "SEED 最小校驗資料（非正式台賬）")
            seeds_sql.append((
                """INSERT IGNORE INTO `signal`
                   (signal_id, instrument_id, rule_id, rule_version, direction, as_of_time,
                    valid_until, entry_condition, exit_condition, confidence, snapshot_id,
                    run_id, status, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                seed_signal))
            seed_dec = ("DEC-SEED-20261011-001", "SIG-SEED-20261011-001", "approve", None,
                        "種子示例：審批鏈演示", "human-admin", None, None, None, None,
                        "SEED 最小校驗資料（非正式台賬）")
            seeds_sql.append((
                """INSERT IGNORE INTO decision
                   (decision_id, signal_id, chief_verdict, reason_code, rationale, approved_by,
                    override_original, override_reason, override_deadline, override_outcome, notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", seed_dec))
            seed_order = ("ORD-SEED-20261011-001", "SIG-SEED-20261011-001", "DEC-SEED-20261011-001",
                          "INST-HK-02269", "buy", "limit", 20.000000, 2000, "HKD",
                          None, 0, 1, "種子示例", "filled", "ledger-service(seed)",
                          "SEED 最小校驗資料（非正式台賬）")
            seeds_sql.append((
                """INSERT IGNORE INTO paper_order
                   (order_id, signal_id, decision_id, instrument_id, side, order_type, limit_price,
                    quantity, currency, valid_until, event_window_flag, risk_check_passed, risk_note,
                    status, created_by, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                seed_order))
            seed_fill = ("FLL-SEED-20261011-001", "ORD-SEED-20261011-001", 20.050000, 2000,
                         utc("2026-10-09 08:30:00.000000"), 0.010000, 100.000000, 0.000000,
                         "種子示例", "SEED 最小校驗資料（非正式台賬）")
            seeds_sql.append((
                """INSERT IGNORE INTO paper_fill
                   (fill_id, order_id, fill_price, quantity, fill_time, slippage, commission,
                    tax_fee, liquidity_note, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                seed_fill))
            seed_lot = ("LOT-SEED-20261011-001", "INST-HK-02269", "FLL-SEED-20261011-001", None,
                        2000, 2000, 20.050000, "HKD", 18.000000, None, None, None,
                        "open", None, None, utc("2026-10-09 08:30:00.000000"), None,
                        "SEED 最小校驗資料（非正式台賬）")
            seeds_sql.append((
                """INSERT IGNORE INTO position_lot
                   (lot_id, instrument_id, open_fill_id, close_fill_id, quantity_open,
                    quantity_remaining, avg_cost, currency, stop_loss, mae, mfe, r_multiple,
                    status, exit_reason_code, exit_note, opened_at, closed_at, notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", seed_lot))

            for sql, params in seeds_sql:
                cur.execute(sql, params)
            conn.commit()

            # ── 校驗：九表存在＋行數＋FK 鏈完整性 ──
            cur.execute("SHOW TABLES")
            after = {r[0] for r in cur.fetchall()}
            created_now = sorted(after - before)
            report["created_new"] = created_now
            counts = {}
            for t in LEDGER_TABLES:
                cur.execute(f"SELECT COUNT(*) FROM `{t}`")  # t 來自白名單常量，無注入面
                counts[t] = cur.fetchone()[0]
            report["seed_counts"] = counts
            cur.execute("""SELECT COUNT(*) FROM `signal` s
                           JOIN market_snapshot ms ON s.snapshot_id=ms.snapshot_id
                           JOIN rules r ON s.rule_id=r.rule_id AND s.rule_version=r.version
                           JOIN instrument_master i ON s.instrument_id=i.instrument_id
                           JOIN decision d ON d.signal_id=s.signal_id
                           JOIN paper_order po ON po.signal_id=s.signal_id
                           JOIN paper_fill pf ON pf.order_id=po.order_id
                           JOIN position_lot pl ON pl.open_fill_id=pf.fill_id""")
            report["integrity"]["fk_chain_signal_to_lot"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM rules WHERE status='registered'")
            report["integrity"]["rules_registered_seeds"] = cur.fetchone()[0]
            conn.commit()
            report["result"] = "OK"
    finally:
        conn.close()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("result") == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
