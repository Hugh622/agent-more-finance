# 三地行情统一抓取模块 v1（market_fetcher）

> 全栈开发 ｜ 2026-09-12 ｜ 数据落地: `/shared/market_data/`
> 支撑团队：量化技术专家（K线/诊断）、首席投资策略师（配置模板）、宏观基本面研究员（P0数据）
> 上游依据：量化专家集成约定 ＋ 宏观研究员《官方数据第三方可靠来源清单与核验标准 v1》

## 1. 快速开始

```bash
python3 scripts/run_all.py               # 全量: K线250根 + 实时快照 + 宏观P0 (约5-8分钟)
python3 scripts/run_all.py --no-kline    # 盘中轻量: 快照 + 宏观通道
python3 scripts/verify_symbols.py        # 全池标的验证(美股映射表重建)
python3 scripts/finnhub_verify.py        # Finnhub key 全端点实测矩阵(30用例, --quick 6用例)

# 库内调用（与量化工具v1同约定）
from market_fetcher import tencent_api, runner
df = tencent_api.fetch_kline("usNVDA.OQ", count=250)   # 单只, 无效代码返回None
m  = runner.run_kline_batch({"美股": pool}, count=250) # 批量, 单只失败不中断
```

## 1.5 Finnhub 美股主力源（v1.2 接入）

- **定位**：美股「主力源」（个股/ETF 日K、实时报价、基本面指标、SEC filings、财报/经济日历、新闻），腾讯通道自动兜底；A/HK/指数固定腾讯。
- **key 管理**：仅存 `config/finnhub.json`，代码零硬编码；`proxy` 字段供受限出口环境配置代理；`enabled` 一键开关。
- **自动切换逻辑**：每次批次启动先跑 `health_check()`（/quote 探测，结果缓存10分钟于 `config/finnhub_health.json`）→ 通过则美股走 Finnhub（60/min 滑动窗口限流），不通过全量回腾讯，行为与 v1.1 完全一致。
- **落盘标注**：Finnhub 输出 source=`Finnhub-finnhub.io行情通道(美股主力源)-{ts}`，等级 L2 行情商（美股免费档实时）；manifest 增加 `source_mix`（finnhub/tencent 条数）与 `finnhub_health`。
- **新增输出**：`sec/finnhub_filings_crosscheck.csv`（SEC 交叉核验，EDGAR 仍为 L1 主源）、`calendar/us_earnings_calendar.json`、`calendar/us_economic_calendar.json`、`fundamentals/us_metrics_latest.csv`（美股池 P/E·P/B·ROE·Beta·股息率）。
- **⚠️ 本环境已知限制（2026-09-12 实测）**：当前运行环境出口对 Cloudflare 托管域（finnhub.io、www.cloudflare.com）TCP 不可达；对照组 sec.gov(1.1s)/FRED(1.7s)/腾讯(0.2s) 均可达 → 判定为环境出口策略限制，非 key 问题。端点级实测矩阵（key 有效性、免费档各端点开放度、x-ratelimit 头）需在具备出口的环境执行 `scripts/finnhub_verify.py` 获得；在此之前美股全量走腾讯兜底，管道输出不受影响。

## 2. 数据输出与来源等级（每类数据标注）

等级口径（对齐用户指示与核验标准v1）：
**L1 官方直连**(S级官网/联储系统) → **L2 第三方可靠来源**(A/B级传媒白名单核验；行情类=授权行情商) → **L3 检索兜底**(录入模板/单源待核)。
所有输出强制带 `fetched_at`(时间戳) + `source`(机构-媒体-时间戳) + `source_level`(等级) 字段。

| 数据类型 | 降级链（依次尝试） | 实测等级 | 落盘路径 |
|---|---|---|---|
| 三地日K线（个股/指数/ETF/板块ETF） | 腾讯授权行情通道(3域名故障转移) | L2·行情商·T+0 | `daily/{code}.csv` |
| 实时快照（142只全池） | 腾讯 qt.gtimg.cn | L2·行情商·实时 | `realtime/latest.csv` |
| 美债2Y/10Y/30Y | 财政部官网 → FRED(DGS2/10/30) → L2登记簿 | **L1官方直连** | `rates/us10y.csv` 等 |
| 联邦基金利率/VIX官方/信用利差 | FRED(DFF/VIXCLS/BAMLH0A0HYM2) → L2登记簿 | **L1官方直连** | `rates/fedfunds.csv` 等 |
| 中国国债收益率 | CFETS中国货币网（⚠️待逆向v2）→ L2检索录入 | 暂L2录入 | `rates/cn10y.csv` |
| 汇率矩阵 USDCNY/USDHKD/HKDCNY/美元指数 | 腾讯外汇通道 | L2·行情商·T+0 | `fx/fx_matrix.csv` |
| AH溢价（18对自算） | 腾讯行情自算 → 恒指公司HSAHP传媒转引(B+B)交叉 | L2 | `ah/ah_premium.csv` |
| SEC财报摘要（美股池10-K/10-Q/8-K） | SEC EDGAR官方直连（规范UA+官方CIK表） | **L1官方直连** | `sec/us_recent_filings.csv` |
| FOMC日历/南向资金/中间价 | 静态配置+L2/L3检索录入登记簿 | L3/L2 | `calendar/*.json` |
| 波动率 VHSI/VIX代理 | 腾讯 hkVHSI 直连；VIX官方以FRED VIXCLS为准 | L2/L1 | `volatility/*.csv` |

**L2 登记簿**：`config/third_party_records.json` —— 权威传媒检索录入统一入口，字段与核验状态
（double_verified / single_A / single_B / institutional）完全对齐核验标准v1；管道在读入时
自动只取滞后时限内记录，下游文件自动携带 `grade`。核验白名单（路透/彭博/财新/智通等）见宏观研究员文档§2。

## 3. 行情集成约定（源自资深量化技术专家，严格沿用）

1. K线 param 必须为 `"{code},day,,,{count},qfq"`（count 第4段，日期留空）；
2. 美股后缀**严格区分交易所**：NASDAQ→`.OQ`、NYSE→`.N`、ETF(Arca/AMEX)→`.AM`。
   ⚠️ 2026-09-12 17:40 二次实测推翻早期"接口忽略后缀"结论（当时系批量限流误判）：
   `usBABA.OQ`/`usJPM.OQ` 等全部失败，`usBABA.N`/`usJPM.N` 正常返回250根；
   `usSPY.N` 仅回1行而 `usSPY.AM` 回250根全量。映射表 `config/us_symbols.json` 按官方后缀维护；
3. 美股指数（usDJI/IXIC/INX/NDX）在 fqkline 端点仅回1行，**已增加 usfqkline 端点自动降级**：
   `fetch_kline` 对美股代码行数不足时自动切换 `appstock/app/usfqkline/get`（3域名同样轮转），
   道指/纳指综合/标普500/纳指100 实测250根全量通过；
4. 无效/退市标的接口返回 `v_pv_none_match` → `fetch_kline` 返回 `None`，批次不中断；
5. 腾讯原始行序 `[date,open,close,high,low,volume]`，落盘重排为标准
   `date,open,high,low,close,volume`（策略师约定）；`amount_raw` 为接口附带原始成交额，未归一，跨市场比较一律用比率；
6. **主域名偶发 501 JS风控挑战**（2026-09-12 实测，疑似突发限流触发），已实现
   web.ifzq.gtimg.cn → ifzq.gtimg.cn → proxy.finance.qq.com 三域名轮转故障转移，实测全通；
   首轮跑批曾因连发限流致43只失败，重跑即恢复——批次失败>0时直接原样重跑即可；
7. 频率：日K每日收盘后一次（A/H 16:30后，美股北京时间清晨）；美股分钟线 v2。

## 4. 标的池（全部实测通过，详见 config/verify_report.json）

- 指数 10：沪深300/上证/深成/创业板 + 恒指/恒生科技 + 道指/纳指综合/标普500/纳指100
- A股65只龙头 ＋ 港股24只蓝筹 ＋ 美股48只（36主池+候补+12只宏观观察新增，映射表全量复验）
- **美股板块个股观察池18只**（宏观研究员《观察清单v1》即插即用，2026-09-12新增）：
  AI电力链 ETN/VRT/GEV/CAT ｜ AI计算核心 NVDA/TSM/AVGO/CRWV ｜ 能源 XOM/CVX/COP/SLB ｜
  核电 CEG/VST/TLN/BE ｜ 金融备选 JPM/GS —— 配置于 `market_fetcher/pools.py::US_WATCH_POOL`
- ETF：沪深300ETF/盈富/恒生ETF/黄金ETF + SPY/QQQ/GLD（SPY/GLD 后缀实测修正为 `.AM`）
- 美股11大板块行业ETF（SECTOR_ETF_POOL，11/11实测通，2026-09-12新增）
- AH对18组（自算溢价）；波动率代理 VHSI/VIXY/VXX
- 候补池机制：主池失效标的由 spares 自动替补，保持编制规模

## 5. 每日定时调度（v1.3 已上线，2026-09-12）

```bash
python3 scripts/scheduler.py                 # 前台守护(调试用)
setsid nohup python3 scripts/scheduler.py --verify-two-rounds > logs/scheduler.out 2>&1 &
                                             # 生产启动: 先连续两轮自动验证, 再进入常驻守护
```

| 窗口(北京时间) | 作业 | 内容 |
|---|---|---|
| 周一~周五 16:40 | `ah_eod` | A/H收盘后全量：三地K线250根(含美股池+行业ETF) + 快照 + 宏观P0 |
| 周二~周六 06:30 | `us_morning` | 美股收盘后：美股段K线(主池59+行业ETF11) + 快照 + 宏观P0 |
| 周一 06:30 | `us_morning` 轻量 | 美股无新收盘，仅快照+宏观；周日跳过 |

- **幂等**：`config/scheduler_state.json` 每作业每天至多触发一次；进程重启或错过窗口自动补跑，不重复。
- **留痕**：每轮 manifest 带 `job`/`trigger` 字段（`scheduler` / `scheduler_verify_roundN`）；日志 `logs/scheduler.log`。
- **验证**：两轮自动验证报告 `config/scheduler_verify_report.json`（2026-09-12 已通过，round1 全量 ok/fail 见报告）。
- **自愈**：环境重启后由心跳检查拉起（进程不存在即重启，状态锁保证不重复跑批）。

## 5.5 更新节奏与调用建议

| 消费方 | 建议 |
|---|---|
| 量化专家 | `daily/*.csv` 直接进 K线诊断/MACD/BOLL/RSI 批量模块；注意列序为标准OHLC |
| 策略师 | `rates/`(股债锚) + `ah/ah_premium.csv`(再平衡) + `fx/fx_matrix.csv`(汇率侵蚀) + VIX/VHSI(波动率目标) |
| 宏观研究员 | `rates/fedfunds.csv`、`sec/us_recent_filings.csv`、`calendar/fomc_calendar.json`；中债/南向走您每日CSV，管道建成后对账 |
| 通用助手 | `config/third_party_records.json` 按模板检索录入（字段与核验状态必填） |

## 6. 已知缺口与降级路径（透明清单）

| 缺口 | 状态 | 降级路径 |
|---|---|---|
| USDCNH 离岸汇率 | 腾讯无通道 | USDCNY 在岸近似（点差极窄）+ L2检索 |
| 人民币中间价 | 无稳定通道 | L2检索：外汇局9:15通稿，登记簿录入 |
| 南向资金 | 腾讯/东财均不可达 | L2检索：智通/AASTOCKS，A+B双源 |
| 中债收益率 | CFETS端点仅回日期元信息 | L2录入：宏观每日CSV；v2逆向 |
| VIX 指数直连 | 腾讯无 | **已解**：FRED VIXCLS 官方收盘 |
| stooq/东财/Yahoo | JS挑战/不可达 | 不采用；主通道腾讯+官方源 |
| Finnhub(finnhub.io) | 本环境出口屏蔽 Cloudflare 托管域(TCP超时) | **已适配待启用**：代码/配置/限流/兜底全就绪，出口恢复或配置 proxy 后自动切美股主力源；期间腾讯全量兜底 |

## 7. 阻塞点

1. **Finnhub 端点级实测受阻（唯一阻塞）**：环境出口对 finnhub.io 不可达，key 有效性、免费档各端点开放度（尤其 /stock/candle 是否在免费档）、60/min 限频响应头均需实测确认——实测脚本 `scripts/finnhub_verify.py` 已就绪，在具备出口的环境跑一次即得完整矩阵。不阻塞当前管道运行（腾讯兜底）。
2. v2 待办：中债CFETS逆向、美股分钟线、FOMC决议自动播报、看板（研究看板另立项）。
