# -*- coding: utf-8 -*-
"""标准化落盘：所有输出强制带 fetched_at(时间戳) + source(来源) + source_level(来源等级) 字段。
来源等级三档（对齐管理员/用户口径与宏观研究员《官方数据第三方可靠来源清单与核验标准 v1》第六节）:
  L1 官方直连        —— 机构官网/API 原始数据（treasury.gov/FRED/SEC EDGAR/CFETS中国货币网 等），grade=S
  L2 第三方可靠来源  —— 权威传媒/通讯社白名单(A/B级)经核验后引用；行情类为授权行情服务商通道(腾讯)，grade=S~B
  L3 检索兜底        —— 检索录入/静态模板/单源待核，强制标注核验状态与滞后，grade=C 或 unverified
source 字段规范统一为「机构-媒体-时间戳」。
CSV 统一 UTF-8(-sig)；JSON 统一 UTF-8 缩进2格。

P0-1 (2026-10-11): 全部落盘切换 atomic_io 原子写入
(tmp -> fsync -> os.replace 原子rename), kill -9 任意时刻不产生半档。
"""
import io
import json
import os

import pandas as pd

from market_fetcher import atomic_io

LEVEL_OFFICIAL = "官方直连"
LEVEL_THIRD_PARTY = "第三方可靠来源"
LEVEL_SEARCH = "检索兜底"

SOURCE_TENCENT_KLINE = "腾讯财经-fqkline行情通道(web/ifzq.gtimg.cn)-{ts}"
SOURCE_TENCENT_RT = "腾讯财经-qt.gtimg.cn行情通道-{ts}"
SOURCE_FINNHUB_KLINE = "Finnhub-finnhub.io行情通道(美股主力源)-{ts}"
SOURCE_FINNHUB_API = "Finnhub-finnhub.io-{endpoint}-{ts}"
SOURCE_TREASURY = "美国财政部-home.treasury.gov-{ts}"
SOURCE_FRED = "圣路易斯联储FRED-fred.stlouisfed.org-{ts}"
SOURCE_CHINAMONEY = "CFETS中国货币网-chinamoney.com.cn-{ts}"
SOURCE_SEC_EDGAR = "SEC EDGAR-sec.gov-{ts}"


def stamp(source_tpl: str, ts: str) -> str:
    """把时间戳写进 source，落实「机构-媒体-时间戳」规范。"""
    return source_tpl.format(ts=ts)


def add_meta(df: "pd.DataFrame", fetched_at: str, source: str,
             source_level: str = None, grade: str = None) -> "pd.DataFrame":
    df = df.copy()
    df["fetched_at"] = fetched_at
    df["source"] = source
    df["source_level"] = source_level or LEVEL_OFFICIAL
    if grade:
        df["grade"] = grade
    return df


def save_csv(df: "pd.DataFrame", path: str, fetched_at: str, source: str,
             source_level: str = None, grade: str = None) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    buf = io.BytesIO()
    add_meta(df, fetched_at, source, source_level, grade).to_csv(
        buf, index=False, encoding="utf-8-sig")
    return atomic_io.atomic_write_bytes(path, buf.getvalue())


def save_json(obj, path: str, fetched_at: str = None, source: str = None,
              source_level: str = None) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if isinstance(obj, dict) and (fetched_at or source or source_level):
        obj = {**obj,
               **({"fetched_at": fetched_at} if fetched_at else {}),
               **({"source": source} if source else {}),
               **({"source_level": source_level} if source_level else {})}
    return atomic_io.atomic_write_text(
        path, json.dumps(obj, ensure_ascii=False, indent=2))
