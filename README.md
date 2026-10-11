# agent-more-finance — AI 投研團隊框架

三地行情數據管道（A股／港股／美股）＋四腿協作（宏觀基本面／量化技術／首席統合／數據工程）的投研框架與代碼倉。由清言 AgentMore 團隊維護，倉庫定位＝框架代碼與版本管理單一真相源。

## 目錄導航

| 目錄 | 內容 |
|---|---|
| `packages/` | 五件外發包脫敏終版（zip 原封歸檔，與 2026-10-11 群內交付逐字節一致） |
| `code/` | 代碼內核 `team_framework` v1.3（規則引擎：閘門/條款/倉位/信號/覆核，可跑，含單測） |
| `pipeline/` | 數據工程補充包（23 小時交易管道腳手架＋11 項單測、年檢數據作業、運維自愈、掃描仲裁工具、安全脫敏件、數據樣本） |
| `docs/` | 倉庫治理文檔（初始化與安全推送守則等） |
| `scripts/` | `scan_secrets.py` 推送前密鑰掃描器（每次 commit 必跑） |

## 五包清單與閱讀順序

1. 宏觀組織層增補包（`packages/宏观组织层增补包_20261011.zip`）
2. 框架與檔案全套 · 脫敏修復版（`packages/AI投研团队_框架与档案全套_20261010_脱敏修复版.zip`，16:14 終版）
3. 代碼內核（即 `code/`，zip 為 `packages/team_framework_code_v1.3_20261011.zip`）
4. 數據工程補充包（即 `pipeline/`，zip 為 `packages/數據工程補充包_全棧開發_20261011.zip`，16:23 重建版）
5. 運作系統層（`packages/tri_market_research_system_運作系統層_20261011.zip`）

閱讀序：**組織層 → 全檔案（脫敏修復版）→ 規則引擎（code/）→ 數據工程（pipeline/）→ 運作系統**。

## 運行環境

- Python 3.12+（注意：`re` 內聯旗標 `(?i)` 已於 3.11+ 禁用，須用 `re.compile(pattern, re.IGNORECASE)`）。
- `code/`：`pip install -e code/` 後 `pytest code/tests`。
- finnhub API key 一律環境變量注入，模板見 `pipeline/05_安全脫敏/finnhub.json.example`；**本倉不含任何真實密鑰**。

## 安全約定

- 每次提交前必跑：`python3 scripts/scan_secrets.py .`（0 命中方可推送；`.git/hooks/pre-commit` 已掛同款關卡）。
- 禁放清單見 `.gitignore`：事故版原始包、config/finnhub.json、.env*、token/secret/credentials 類檔名、verify/health 日誌等永不入庫。
- 版本規範：tag `v1.0-20261011` 格式（語義版本＋日期）；main 分支保護＝禁 force push、禁刪除。

## 免責聲明

本倉全部內容（含規則引擎、信號、倉位與紙面交易臺賬）**僅為研究與紙面交易（paper trading）用途**，不構成任何證券投資建議或要約；數據樣本僅展示管道輸出格式。實盤風險自負。

---
版本：v1.0-20261011　|　維護：AI 投研團隊（全棧開發·數據工程腿）
