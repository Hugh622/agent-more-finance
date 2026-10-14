# P1②｜九表 schema 定稿 v1.0.0——規則收編註冊冊＋reason code 對齊＋台賬遷移映射（量化技術專家）

日期：2026-10-12 ｜ 線別：方法學線（P1②）｜ 狀態：**定稿，交全棧對齊基座**

---

## 一、交付件清單（shared/方法學線_20261011/）

| # | 件 | 用途 |
|---|---|---|
| 1 | `rules_registry_20261011.yaml` | **規則註冊冊源文件**（混合模式：元數據/參數/版本 YAML 化，logic_ref 指向 Python 主體） |
| 2 | `規則收編種子_20261011.sql` | **MySQL 版種子**（交全棧單寫者執行，對齊 `warren_learning_db.rules`） |
| 3 | `規則收編種子_20261011.sqlite.sql` | SQLite 測試基座版種子（與 MySQL 版同構） |
| 4 | `reasoncode_enum_20261011.yaml` | reason code 枚舉（**以首席《reason_code_registry_v1_20261011.html》為唯一基準**，8/8 對齊） |
| 5 | `台賬reasoncode遷移映射_v1_20261011.csv` | 歷史台賬 → reason code 遷移映射（32 行，逐條帶 evidence/review_note） |
| 6 | `台賬遷移種子_20261011_v101.sql` | 遷移種子（按映射 CSV 生成） |
| 7 | `SQLite九表測試基座_DDL_20261011.sql` | 九表 DDL（rules/signal/decision/paper_order/paper_fill/position_lot/experiment/…，含 supersedes 自引用外鍵） |
| 8 | `MySQL九表_reasoncode對齊delta_20261011.sql` | 現存 MySQL 庫的增量對齊腳本（不動既有行，只加列/索引/約束） |
| 9 | `fixture_v110.db` | **已驗證**的 SQLite 基座庫（79 行規則實載，見 §四驗證） |
| 10 | `rules_engine_py_v1/`＋`test_rules.py`＋`test_engine_cost.py` | logic 主體 Python（rules_p0/exit/bubble/risk/sizing/prefilter）＋單測（26 例全綠） |

## 二、收編口徑（72 條，含歷史版本）

- **P0×8**：P0.C1/P0.C2/P0.C3/P0.E0/P0.E1（C1/C2/E0 各含 2 版）——**獨立命名空間 `P0.*`**
- **C×19** ｜ **R×10** ｜ **N×19**（v1.2 拒收終版①-⑪ 收編為 N9-N19 順延，N1-N8 為 v1.1 不採納清單）｜ **D×3** ｜ **K×6** ｜ **G×2** ｜ **W×5**
- 占位退役 7 條：`C@1.0.0…G@1.0.0` 占位行 status≠active（supersedes 鏈落點用）
- **三條命名決策**（入 meta.naming_decisions，防撞號）：
  1. P0 確認制獨立命名空間 `P0.*`——框架明文兩套並行系統，不與 v1.2 C 系列混號；
  2. v1.2 拒收終版①-⑪ → N9-N19；
  3. 23/5 研究報告新編「N1 隔夜假突破」→ 重編 **D3**（語義本屬記帳）。

## 三、機制設計

1. **supersedes 鏈**：`rules.id`（內部代理鍵）自引用外鍵；`supersedes_id` 指向被取代版本；業務鍵 UNIQUE(rule_id, version)。fixture 實載驗證**鏈條閉合（無懸掛指針）**。
2. **rules.yaml 混合模式**：元數據/參數/版本/狀態 YAML 化 → 種子 SQL 由 `gen_rules_sql.py` 機械生成（無手工抄寫）；logic 主體留在 Python（`logic_ref` 列名對應 `rules_engine_py_v1` 內函數名），每函數配單測。流程類規則 `logic.mode=process` 不掛代碼。
3. **reason code**：枚舉 8 值 `DATA_CONFLICT / MODEL_DISAGREEMENT / HUMAN_OVERRIDE / EXECUTION_SLIP / RULE_VIOLATION / GAP_FILL / LESSON_LEARNED / REGIME_CHANGE`，**與首席 HTML 逐一比對 8/8 一致**（首席為唯一基準，本地 yaml 僅落 SQL CHECK 約束形式）。欄位設計：`reason_code_main`（最初觸發原因，必填）＋`reason_code_sub`（處置結果，可空）。
4. **台賬遷移映射**：32 行（P-令/判例/缺口/教訓等逐條），欄位含 migration_priority/object_type/ledger_ref/main+sub code/rule_ref/evidence/review_note；**owner 與碼待周檢逐條簽名確認**（CSV 內逐行注記，不越權代簽）。
5. **MySQL 對齊 delta**：只 ADD COLUMN / ADD INDEX / ADD CHECK，不 UPDATE 既有行——零破壞原則；執行順序＝delta → 種子 → 遷移種子（全棧單寫者）。

## 四、驗證記錄（fixture_v110.db）

- rules 實載 **79 行**（72 收編＋7 占位）；
- supersedes 鏈閉合檢查：`count(supersedes_id NOT NULL AND 無父)` = **0** ✅；
- 單測 26/26 綠（含 P0 五件、退出四臂、bubble/risk/sizing/prefilter、引擎成交約定、成本三地分參、凍結層→池子→宇宙裝載鏈）；
- 測試期望與數據現實的兩處校準（透明記錄）：①ma50 合成數據構造修正（99<99.5 實已破線，屬測試數據錯誤非實現錯誤，另補「同 bar 雙破→clear 優先」用例）；②宇宙裝載斷言 120→100（212 池×240 根門檻實測 105 只，EXP-001 判決門檻是**觸發 n≥40** 非加載數）；③池子 US 代碼帶交易所後綴（usaapl.oq）與 daily 文件名（usaapl_oq.csv）點-下劃線歸一化——修復後 US/HK/CN 三市全入宇宙。

## 五、交全棧的對齊基座（執行順序）

1. `MySQL九表_reasoncode對齊delta_20261011.sql`（先跑，零破壞）
2. `規則收編種子_20261011.sql`（72＋7 行入 `rules`）
3. `台賬遷移種子_20261011_v101.sql`（遷移行入對應表，reason code 落列）
4. 驗收複驗：行數 79、鏈閉合 SQL、reason code CHECK 生效——全棧跑完回執，方法學線複核。

## 六、已知局限（誠實標注）

- 72 條規則的 `params` 部分以框架 v1.2/v1.1/P0 v1.0 文本為準機械抽取，數值型參數已單列，但**自由文本條件的結構化程度有限**（logic.mode=process 類不掛代碼，靠周檢補）；
- 台賬遷移 32 行中 owner 簽名權留白（待周檢）；
- N 族 19 條為「不採納」語義，status 一律 not-adopted，入庫是為了防重複提案（同案不二議），不是活躍規則。
