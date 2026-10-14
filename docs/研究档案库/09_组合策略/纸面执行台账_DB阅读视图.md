# 纸面执行台账 · DB 阅读视图（机器生成）

> **性质**：本文件由 `ledger_view_generator.py`（只读）从唯一事实主档 **warren_learning_db**（MySQL 九表）实时渲染，属 E-P1-2 双轨收编产物；人工请勿直接编辑本文件。
> **生成时刻**：2026-10-11 16:37:21 UTC ｜ **主档**：warren_learning_db@hk-cynosdbmysql-grp-fpatiu1r.sql.tencentcdb.com
> **内容摘要指纹**：sha256(experiment×4, rules×7, instrument×3, snapshot×1) = a406c1dd853f4807

---

## §A 试验登记册 experiment（预注册先行 · DSR/PBO 试验次数底册）

| ID | 状态 | 拥有腿 | 标题 | 预算(用/额) | rule_ids |
|---|---|---|---|---|---|
| EXP-2026-001 | pre_registered | 量化腿 | P0突破確認制 vs 回調接反事實（三地池成本後單筆期望值） | 0/10 | ["P0.C1@1.2.0", "P0.C2@1.2.0", "P0.C3@1.2.0", "P0.E0@1.2.0"] |
| EXP-2026-002 | pre_registered | 量化腿 | MA滑動退出/減倉制 vs 固定止損-8% vs MA-only（退出政策族對比） | 0/6 | ["P0.C1@1.2.0", "P0.C2@1.2.0", "P0.C3@1.2.0"] |
| EXP-2026-003 | pre_registered | 量化腿 | E0事件窗全日曆回放＋隨機等待N日反事實（FOMC決議日±1交易日只減不加） | 0/3 | ["P0.E0@1.2.0"] |
| EXP-2026-SEED-001（SEED 示范） | pre_registered | quantitative | P0 突破確認 vs 回調接反事實（種子示範） | 0/10 | ["C@1.0.0"] |

### EXP-2026-001 · P0突破確認制 vs 回調接反事實（三地池成本後單筆期望值）
- **假设**：H0: 池內成本後P0確認制入場單筆expectancy(R倍數均值)<=0 || H1: expectancy>0且bootstrap(1000次)90%CI下界>0，觸發樣本n>=40
- **主指标**：成本後單筆expectancy（R=初始止損距離；成本三地分參數見回測最低規格）
- **基准**：buy_and_hold；回調接反事實（MA20回踩收復入場，同退出）——後者輸出踏空成本分布，不作判決條件
- **GO/NO-GO**：GO: H1成立且5x成本層expectancy仍>0 || NO-GO: expectancy<=0 或 5x成本層轉負 或 n<40 || 分層必報:市場(US/HK/CN)x20日實現波動率三分位
- **备注**：參數網格預列即凍結:突破窗{20,55}x緩衝{0.2%,0.5%}x量能{1.5,1.2}=8格+重跑預算2；數據窗2025-10-03~2026-10-09騰訊qfq日K；預註冊文檔sha256=ef92a89227215b03d0a0c686589f2f455e7f59b77ecfeea2e6165e742a98f601

### EXP-2026-002 · MA滑動退出/減倉制 vs 固定止損-8% vs MA-only（退出政策族對比）
- **假设**：H0: MA滑動退出成本後expectancy與MAE不優於固定止損-8%(C11硬頂)基準 || H1: 滑動制expectancy>0且(MAE中位更小 或 MFE捕獲率更高)，5x成本層不轉負
- **主指标**：成本後expectancy；次級主判=MFE捕獲率(平倉收益/MFE)與MAE中位數(position_lot原生欄位)
- **基准**：fixed_stop_-8%；ma_only(無確認純均線持有)
- **GO/NO-GO**：GO: H1成立 || NO-GO: expectancy<=0 或與兩基準均無改善(Δ<=0且MAE/MFE均不佔優) || 分層必報:市場x波動三分位；hit rate僅分層觀察不作判決
- **备注**：參數網格預列:{MA20減半+二連破清, MA20減半+MA50清, MA10減半+MA20清, 固定-8%, MA-only, 重跑預算1}；入場統一=P0確認制保證可對比

### EXP-2026-003 · E0事件窗全日曆回放＋隨機等待N日反事實（FOMC決議日±1交易日只減不加）
- **假设**：H0: 真事件窗規避效果與隨機等待窗無差異 || H1: 真窗事後組合回撤<隨機窗分布10%分位，且機會成本不落在隨機分布最差25%分位
- **主指标**：事件窗規避回撤(窗內事後1/3/5日組合跌幅避免值) vs 機會成本(避免掉的漲幅)；真窗統計量在隨機分布之分位=顯著性
- **基准**：隨機等待N日反事實(事件日平移N∈{1..10}交易日，種子42，抽樣1000次)
- **GO/NO-GO**：GO: H1成立 || NO-GO: 真窗與隨機窗無差異 或 規避收益<機會成本x1/2 || 樣本局限:8事件/250根窗口，結論僅方向性證據，與EXP-001/002合併裁量
- **备注**：事件日曆8次:2025-10-29,2025-12-10(標準公開日程⚠️靜態核對)+2026-01-28,03-18,04-29,06-17,07-29,09-16(fomc_calendar.json✅)；窗寬預列{±1主判,±2,±3}

## §B 规则注册册 rules（混合模式：YAML 元数据 + Python 主体）

| rule_id | 版本 | 状态 | 拥有腿 | scope | logic_ref | 摘要 |
|---|---|---|---|---|---|---|
| C | 1.0.0 | registered | quantitative | ["US", "HK", "CN"] | — | 種子收編佔位：正式參數/logic 待 Rule Registry 四週收編確認（混合模式：YAML 元數據＋Python 主體） |
| D | 1.0.0 | registered | quantitative | ["US", "HK", "CN"] | — | 種子收編佔位：正式參數/logic 待 Rule Registry 四週收編確認（混合模式：YAML 元數據＋Python 主體） |
| G | 1.0.0 | registered | quantitative | ["US", "HK", "CN"] | — | 種子收編佔位：正式參數/logic 待 Rule Registry 四週收編確認（混合模式：YAML 元數據＋Python 主體） |
| K | 1.0.0 | registered | quantitative | ["US", "HK", "CN"] | — | 種子收編佔位：正式參數/logic 待 Rule Registry 四週收編確認（混合模式：YAML 元數據＋Python 主體） |
| N | 1.0.0 | registered | quantitative | ["US", "HK", "CN"] | — | 種子收編佔位：正式參數/logic 待 Rule Registry 四週收編確認（混合模式：YAML 元數據＋Python 主體） |
| R | 1.0.0 | registered | quantitative | ["US", "HK", "CN"] | — | 種子收編佔位：正式參數/logic 待 Rule Registry 四週收編確認（混合模式：YAML 元數據＋Python 主體） |
| W | 1.0.0 | registered | quantitative | ["US", "HK", "CN"] | — | 種子收編佔位：正式參數/logic 待 Rule Registry 四週收編確認（混合模式：YAML 元數據＋Python 主體） |

## §C 标的主档 instrument_master

| instrument_id | 现用代码 | 名称 | 市场 | 币种 | 池内状态 | 备注 |
|---|---|---|---|---|---|---|
| INST-US-CVX | CVX.N | Chevron | US | USD | active | SEED 最小校驗資料（非正式台賬） |
| INST-HK-02269 | 02269.HK | 藥明生物 | HK | HKD | active | SEED 最小校驗資料（非正式台賬） |
| INST-CN-600519 | 600519.SH | 貴州茅台 | CN | CNY | active | SEED 最小校驗資料（非正式台賬） |

## §D 数据冻结层 market_snapshot（可重放最小集）

| snapshot_id | 标的 | as_of(UTC) | 原时区 | 来源 | 复权 | 质量 | 缺失态 | run_id |
|---|---|---|---|---|---|---|---|---|
| SNAP-SEED-20261011-001 | INST-HK-02269 | 2026-10-09 08:00:00 | Asia/Hong_Kong | tencent_qt+ifzq_dual_check | raw | verified | verified | RUN-SEED-20261011-001 |

## §E 过渡区（phase-2 迁移前人读条目）

纸面令 P-001~P-013、终审执行计划总表、判例增补等**人读条目**在 10/16 台账 v2 正式收编前，
仍以《纸面执行台账_v1.1_20261010.md》为过渡阅读层（该册自 2026-10-12 起同为视图性质）；
增量记账一律**先入 DB 后刷视图**，phase-2 收编后订单五表（signal/decision/paper_order/paper_fill/position_lot）入册，本区缩为纯指针。

---

*本视图为模型打磨阶段的纸面记录体系之一部分，全部条目无真实成交，不构成投资建议。*
