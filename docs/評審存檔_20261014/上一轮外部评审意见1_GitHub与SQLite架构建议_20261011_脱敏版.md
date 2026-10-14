# 上一轮外部评审意见 1：GitHub+SQLite 架构建议（脱敏版）

> **转档说明**：本文为上一轮外部评审意见之一（2026-10-11 晚用户转来），原文件＝`upload/6acb66d10730fd6cdd835697_粘贴文本1.txt`（9.3KB，10/11 18:37 上传）。支援腿 2026-10-14 转档收录，**全文保真转录、未删改任何内容**。脱敏检查：通篇为架构建议文本，未发现密钥/token、真实持仓数字或个人资料；文中仅以叙事方式提及"key 曾进入配置及日志的事故"（该事故已由团队在守则与 README 中公开记录并处置），无需脱敏处理。落实对照见同目录《上一轮意见落实对照表_20261014.md》（R1 条目）。

---

**有幫助，而且對你而家呢套 Agent 係幾關鍵嘅升級。**簡單講：**GitHub 管「程式、規則同版本」，SQLite 管「結構化事實、狀態同歷史紀錄」**；兩者配合，先可以將目前以 Markdown／HTML 為主嘅系統，變成真正可維護、可重播、可測試嘅 Agent。

## 分別有咩幫助

| 工具 | 最適合存放 | 對 Agent 嘅幫助 |
|---|---|---|
| GitHub 私有倉庫 | Python、Prompt、Skills、規則 YAML、SQL migration、測試、文件模板 | 知道邊個版本生效、每次改咗乜、可以回退、跑自動測試 |
| SQLite | 標的主檔、數據批次、訊號、裁決、紙面訂單、成交、持倉、復盤 | Agent 可以準確查詢、更新狀態、避免讀錯舊報告 |
| Markdown／HTML | 給人閱讀嘅報告 | 繼續保留，但應由 SQLite 資料生成，而唔係再做唯一事實來源 |
| CSV／Parquet | 大量歷史行情、回測輸入 | 比逐行塞入 SQLite 更適合保存大量時間序列 |

你現有工作區已有 672 個檔案、24 組內容完全重複，而且同一份報告會散落喺幾個目錄；GitHub 可以管理版本，但仍要先定義邊份先係 canonical 主檔，否則只會「有版本控制地繼續重複」。SQLite 就可以取代目前靠檔名、自然語言及 Markdown 表格維持狀態嘅方法。[1]

## GitHub實際價值

GitHub 最有用嘅地方唔係單純「擺檔案上網」，而係建立一條正式改動流程：

1. Agent 建立 branch。
2. 修改規則、程式或 Prompt。
3. 自動執行測試、schema 檢查及 secret scan。
4. 產生變更摘要。
5. 由你批准 Pull Request。
6. 合併後先成為正式版本。

如此一來，Agent 唔應該直接偷偷改正式規則；每次由 P0 v1.2 改成 v1.3，都會保留 diff、原因、測試結果及批准紀錄。你亦可以設定 `main` 為受保護分支，規定測試通過同你批准之後先可以合併。

## SQLite實際價值

SQLite 最適合你目前「單一 Mac、本地 Agent、紙面交易、寫入量不高」嘅階段。開啟 WAL 後，讀取和寫入可以並行，但 SQLite 一般仍然同一時間只容許一個 writer，所以應維持你現有嘅「單寫者」原則，由一個 ledger service 統一寫入。[2]

SQLite 可以令 Agent 直接回答：

- 「目前有幾多個有效掛單？」
- 「邊啲訊號即將過期？」
- 「P0 v1.3 過去半年觸發過幾多次？」
- 「哪些裁決引用咗過期數據？」
- 「所有 MSFT 決策當時用緊邊版規則？」
- 「同一標的有冇互相衝突嘅止損線？」
- 「上月人工 override 最後有冇增值？」

目前紙面台賬已有唯一編號、狀態、觸發條件及紙面成交假設，但規則版本、資料快照、證據連結、責任人、R multiple、退出原因與事後歸因仍未完整結構化。SQLite 正好補呢個缺口。[3]

## 唔好錯誤使用

### GitHub唔好放

- 真實 API key、token、券商憑證。
- 未脫敏持倉或個人資料。
- 大量原始行情 CSV。
- SQLite 正式資料庫本體。
- `.db-wal`、`.db-shm` 或執行日誌。

GitHub Secrets 可以保存工作流程所需憑證，亦會在 Actions 日誌中遮罩已登記秘密；但 GitHub 同時提醒，具寫入權限嘅人可能接觸 repository secrets，所以仍須採用最小權限及定期輪換。尤其你之前已有 key 進入配置及日誌嘅事故，舊 key 應先作廢，而唔係只搬去私人倉庫。[4][5][6]

### SQLite唔好用嚟做

- 多部機器同時高頻寫入。
- 網絡共享磁碟上的多人中央資料庫。
- 儲存每隻股票多年分鐘級／逐筆行情。
- 直接經 Git 同步運行中嘅 `.db` 檔。

如果將來變成多 Agent、多容器或多人同時寫入，就應將交易與狀態資料遷移去 PostgreSQL；SQLite 可以繼續用作本地 cache、測試及研究快照。

## 建議架構

```text
ai-investment-system/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── config/
│   ├── markets.yaml
│   └── risk_limits.yaml
├── rules/
│   └── rules.yaml
├── prompts/
│   ├── macro.md
│   ├── quantitative.md
│   └── chief.md
├── src/
│   ├── data_pipeline/
│   ├── research/
│   ├── ledger/
│   ├── backtest/
│   └── reporting/
├── migrations/
│   ├── 001_initial.sql
│   └── 002_rule_versions.sql
├── tests/
├── docs/
└── reports/
```

本地運行資料則分開：

```text
local_data/
├── agent.db
├── raw/
├── silver/
├── gold/
└── backups/
```

`.gitignore` 至少加入：

```gitignore
.env
*.db
*.db-wal
*.db-shm
local_data/
logs/
__pycache__/
.DS_Store
```

## SQLite最小資料表

第一階段唔使起得太複雜，八張核心表已經足夠：

| 表 | 用途 |
|---|---|
| `instruments` | 永久標的 ID、ticker 歷史、交易所、幣種、時區 |
| `data_runs` | 每次拉數嘅來源、時間、狀態、schema、hash |
| `rules` | 規則 ID、版本、參數、狀態、批准人 |
| `signals` | 標的、方向、觸發時間、規則版本、資料快照 |
| `decisions` | 首席裁定、人工批准、否決及 override 原因 |
| `paper_orders` | 限價、數量、有效期及風險限制 |
| `paper_fills` | 模擬成交價、滑點、費用、成交時間 |
| `positions` | 逐 lot 成本、持倉、止損及退出原因 |

之後先增加 `experiments`、`backtest_runs`、`performance_metrics`、`evidence` 和 `agent_runs`。尤其要保存 `as_of_time`、`rule_version`、`data_run_id` 及 `model_version`，否則有 SQLite 都未必能夠真正重播決策。

## 對「呢個Agent」嘅限制

**只係開咗 GitHub repo，唔代表 Agent 自動識得使用。**你仍然要授權佢讀寫 repo，例如在本機 clone 倉庫、提供 GitHub App／細權限 token，或者配置 `gh` CLI；最好預設只讀，只有開 branch 和 Pull Request 權限，唔畀直接 push `main`。

SQLite 就直接得多：只要 `.db` 位於 Agent 可存取嘅本地工作目錄，並提供明確 schema，Agent 就可以透過 Python／SQL 操作。不過應經一層固定 repository/service API 寫入，而唔係容許每個 Agent 任意執行 `UPDATE` 或 `DELETE`。

## 最適合你嘅方案

我會建議你採用：

- **一個 private GitHub repository**：放程式、Prompt、規則、migration、測試及模板。
- **一個本地 SQLite**：作研究狀態、紙面台賬、訊號與實驗 metadata 嘅唯一事實來源。
- **行情歷史另存 Parquet**：SQLite 只存檔案位置、日期範圍、hash 和品質狀態。
- **所有報告由資料庫生成**：Markdown／HTML 變成人類閱讀介面。
- **所有 Agent 只提交建議**：由單一 ledger writer 入庫；重要改動經 GitHub PR 及你批准。
- **每日 SQLite 備份**：使用 SQLite backup API 或一致性快照，而唔係直接複製運行中嘅資料庫。

所以答案係：**非常有幫助，而且 GitHub + SQLite 正正係你下一步最合理嘅組合；但 GitHub 應管版本，SQLite 應管狀態，兩者唔好互相代替。**你目前單機、紙面執行、多 Agent 研究嘅規模，未需要一開始就上 PostgreSQL、向量資料庫或複雜雲端架構。

來源
[2] Write-Ahead Logging https://www.sqlite.org/wal.html
[3] docs.github.com › en › actionsSecrets - GitHub Docs https://docs.github.com/en/actions/concepts/security/secrets
[4] Secure use reference - GitHub Docs https://docs.github.com/en/actions/reference/security/secure-use
[5] github.com › actions › referencedocs/content/actions/reference/security/secrets.md ... - GitHub https://github.com/github/docs/blob/main/content/actions/reference/security/secrets.md
[6] Using secrets in GitHub Actions - GitHub Enterprise Server 3.11 Docs https://docs.github.com/en/enterprise-server@3.11/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions
[7] Understanding GitHub secret types - GitHub Enterprise ... https://docs.github.com/en/enterprise-cloud@latest/code-security/reference/secret-security/secret-types
[8] Understanding GitHub secret types https://docs.github.com/en/code-security/reference/secret-security/secret-types
[9] docs - content - actions - how-tos - write-workflows https://github.com/github/docs/blob/main/content/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets.md
[10] 1. Overview https://www.sqlite.org/draft/wal.html
[11] REST API endpoints for GitHub Actions Secrets https://docs.github.com/en/rest/actions/secrets
[12] Secrets - GitHub Enterprise Server 3.17 Docs https://docs.github.com/en/enterprise-server@3.17/actions/concepts/security/secrets
[13] Secrets - GitHub Enterprise Server 3.18 Docs https://docs.github.com/en/enterprise-server@3.18/actions/concepts/security/secrets
[14] GitHub Docs https://docs.github.com/api/article?pathname=/en/actions/reference/security/secure-use
[15] hctree: Begin Concurrent - sqlite.org https://sqlite.org/hctree/doc/begin-concurrent/doc/begin_concurrent.md
[16] Secure use reference - GitHub Enterprise Cloud Docs https://docs.github.com/en/enterprise-cloud@latest/actions/reference/security/secure-use

---

*轉檔：通用助手（支援腿）｜2026-10-14｜來源檔保留於 upload/，本件為入包脫敏版*
