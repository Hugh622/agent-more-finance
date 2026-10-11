# JGB 財務省通道定案（2026-10-09）

**問題**：日本 JGB（金利情報）日文路徑 404，多數镜像失效。

**定案**：英文路徑復通可用——
`https://www.mof.go.jp/english/policy/jgbs/reference/interest/`（現月 historical CSV）
歷史全量：`jgbcme_all.csv` 結構（日期, 基準割引短期国庫証券…1/2/3/4/5/7/10/15/20/25/30/40年利回り），`-` 表無發行/ holiday。

**要點**：
- 裸碼文件是垃圾；須用帶說明（EN）版本對齊列義
- 列序歷史上有變動，解析要按表頭健壯匹配（勿按固定列號）
- 本腿落檔：`jgb_backfill/mof_jgbcme_all_EN_20261009.csv`（帶說明）與解析器 `parse_mof.py`
