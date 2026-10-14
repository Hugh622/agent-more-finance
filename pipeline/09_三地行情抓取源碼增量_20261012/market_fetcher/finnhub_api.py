# -*- coding: utf-8 -*-
"""
Finnhub API 统一封装（美股主力源: 行情/基本面/SEC/财报/宏观/新闻）
================================================================
角色定位（2026-09-12 管理员派单）:
  - 美股「主力源」，腾讯通道为兜底；健康检查不通过时调用方自动回退腾讯，行为与 v1.1 一致。
  - key 只从 config/finnhub.json 读取，不硬编码；支持 proxy 出口配置。

与腾讯通道的对接约定:
  - fetch_kline() 返回与 tencent_api.fetch_kline() 完全一致的列序:
    [date, open, close, high, low, volume, amount_raw]（腾讯口径），
    由 runner 重排为标准 OHLC 落盘 —— 上游消费方零改动。
  - 无效/无数据返回 None，单只失败不中断批次（量化专家约定 #4）。

限频: 免费档 60 calls/min → RateLimiter 滑动窗口强制节流（默认间隔≥1.05s）。
网络异常/401/403/429 一律抛 FinnhubError 或返回 None，绝不阻塞主流程。
"""
import json
import os
import time
from datetime import datetime, timedelta

import requests
import pandas as pd

from market_fetcher import storage

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "config", "finnhub.json")
HEALTH_CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "config", "finnhub_health.json")

_RAW_COLS = ["date", "open", "close", "high", "low", "volume", "amount_raw"]


class FinnhubError(Exception):
    """Finnhub 请求失败（网络/权限/限频），调用方据此回退兜底源。"""


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


class _Limiter:
    """滑动窗口限频器: 每分钟最多 limit 次。"""

    def __init__(self, per_min: int, min_interval: float):
        self.window = 60.0
        self.per_min = max(1, per_min)
        self.min_interval = min_interval
        self._hits = []
        self._last = 0.0

    def wait(self):
        now = time.monotonic()
        gap = now - self._last
        if gap < self.min_interval:
            time.sleep(self.min_interval - gap)
        now = time.monotonic()
        self._hits = [t for t in self._hits if now - t < self.window]
        if len(self._hits) >= self.per_min:
            sleep_s = self.window - (now - self._hits[0]) + 0.05
            time.sleep(max(sleep_s, 0.1))
        self._last = time.monotonic()
        self._hits.append(self._last)


class FinnhubClient:
    def __init__(self, cfg: dict = None):
        self.cfg = cfg or load_config()
        self.base = self.cfg["base_url"].rstrip("/")
        self.key = self.cfg["api_key"]
        self.timeout = self.cfg.get("timeout_sec", 12)
        self.retries = self.cfg.get("retries", 2)
        self.limiter = _Limiter(self.cfg.get("rate_limit_per_min", 60),
                                self.cfg.get("min_interval_sec", 1.05))
        self.session = requests.Session()
        proxy = self.cfg.get("proxy")
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

    # ---------- 底层 ----------
    def get(self, path: str, params: dict = None):
        """GET 请求，成功返回 dict/list，失败抛 FinnhubError。"""
        p = dict(params or {})
        p["token"] = self.key
        last_err = None
        for i in range(self.retries + 1):
            self.limiter.wait()
            try:
                r = self.session.get(self.base + path, params=p, timeout=self.timeout)
                if r.status_code == 429:
                    last_err = FinnhubError("429 rate limited")
                    time.sleep(2 + i * 2)
                    continue
                if r.status_code in (401, 403):
                    try:
                        detail = r.json().get("error", "")
                    except Exception:
                        detail = r.text[:120]
                    raise FinnhubError(f"{r.status_code} forbidden/upgrade required: {detail}")
                if r.status_code == 404:
                    raise FinnhubError(f"404 not found: {path} {params}")
                r.raise_for_status()
                return r.json()
            except FinnhubError:
                raise
            except Exception as e:
                last_err = e
                time.sleep(min(2 ** i, 8) * 0.8)  # 指数退避 0.8/1.6/3.2/6.4s, 适应间歇性出口
        # 2026-10-11 安全修复: requests 网络异常文本内嵌完整 URL(含 token=key),
        # 若原样进入 health 缓存/日志会复发 verify_result 的泄漏形态 → 抛出前擦除 key。
        msg = f"{type(last_err).__name__}: {last_err}"
        if self.key:
            msg = msg.replace(self.key, "REDACTED_FINNHUB_KEY")
        raise FinnhubError(msg)

    # ---------- 行情 ----------
    def quote(self, symbol: str) -> dict:
        """美股实时报价（免费档实时，含盘前盘后 pc 字段外另计）。"""
        return self.get("/quote", {"symbol": symbol.upper()})

    def fetch_kline(self, symbol: str, count: int = 250,
                    resolution: str = "D") -> "pd.DataFrame | None":
        """美股/ETF 日K → 与 tencent_api.fetch_kline 同构 DataFrame。
        Finnhub 无前复权口径参数（美股通常返回未复权），qfq 需求仍以腾讯为主时注意。
        amount_raw: Finnhub candle 无成交额字段, 置 None（README §3 口径: 跨市场比较用比率）。
        """
        to = int(time.mktime(datetime.now().timetuple()))
        days = {"D": 400, "W": 1900, "M": 4000}.get(resolution, 400)
        frm = int(time.mktime((datetime.now() - timedelta(days=days)).timetuple()))
        try:
            body = self.get("/stock/candle", {"symbol": symbol.upper(),
                                              "resolution": resolution,
                                              "from": frm, "to": to})
        except FinnhubError as e:
            print(f"[finnhub][warn] candle {symbol}: {e}")
            return None
        if body.get("s") != "ok" or not body.get("t"):
            return None
        n = min(len(body["t"]), len(body.get("c", [])))
        df = pd.DataFrame({
            "date": [datetime.fromtimestamp(t) for t in body["t"][:n]],
            "open": (body.get("o") or [None] * n)[:n],
            "close": (body.get("c") or [None] * n)[:n],
            "high": (body.get("h") or [None] * n)[:n],
            "low": (body.get("l") or [None] * n)[:n],
            "volume": (body.get("v") or [None] * n)[:n],
            "amount_raw": [None] * n,
        })
        df = df.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
        return df.tail(count)[_RAW_COLS] if len(df) else None

    # ---------- 基本面 / SEC / 财报 ----------
    def profile(self, symbol: str) -> dict:
        return self.get("/stock/profile2", {"symbol": symbol.upper()})

    def metrics(self, symbol: str, metric: str = "all") -> dict:
        return self.get("/stock/metric", {"symbol": symbol.upper(), "metric": metric})

    def financials_reported(self, symbol: str, statement: str = "bs",
                            freq: str = "annual") -> dict:
        """10-K/10-Q 原始报表数据（官方口径转引源；SEC EDGAR 仍为 L1 主源）。"""
        return self.get("/stock/financials-reported",
                        {"symbol": symbol.upper(), "statement": statement, "freq": freq})

    def filings(self, symbol: str = None, form: str = None) -> list:
        """SEC 文件列表（10-K/10-Q/8-K…）。symbol/form 均可选。"""
        p = {}
        if symbol:
            p["symbol"] = symbol.upper()
        if form:
            p["form"] = form
        return self.get("/stock/filings", p)

    def earnings_surprises(self, symbol: str) -> list:
        """历史 4 季 EPS 预期 vs 实际。"""
        return self.get("/stock/earnings", {"symbol": symbol.upper()})

    def earnings_calendar(self, date_from: str = None, date_to: str = None,
                          symbol: str = None) -> list:
        """财报日历（免费档窗口受限，超出报错即回退静态日历）。"""
        p = {}
        if date_from:
            p["from"] = date_from
        if date_to:
            p["to"] = date_to
        if symbol:
            p["symbol"] = symbol.upper()
        return (self.get("/calendar/earnings", p) or {}).get("earningsCalendar") or []

    # ---------- 宏观 / 新闻 / 衍生 ----------
    def economic_calendar(self) -> list:
        return (self.get("/calendar/economic") or {}).get("economicCalendar") or []

    def market_news(self, category: str = "general") -> list:
        return self.get("/news", {"category": category})

    def company_news(self, symbol: str, days: int = 7) -> list:
        frm = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        to = datetime.now().strftime("%Y-%m-%d")
        return self.get("/company-news", {"symbol": symbol.upper(), "from": frm, "to": to})

    def recommendation(self, symbol: str) -> list:
        return self.get("/stock/recommendation", {"symbol": symbol.upper()})

    def price_target(self, symbol: str) -> dict:
        return self.get("/stock/price-target", {"symbol": symbol.upper()})

    def peers(self, symbol: str) -> list:
        return self.get("/stock/peers", {"symbol": symbol.upper()})

    def market_status(self, exchange: str = "US") -> dict:
        return self.get("/stock/market-status", {"exchange": exchange})

    def market_holiday(self, exchange: str = "US") -> list:
        return (self.get("/stock/market-holiday", {"exchange": exchange})
                or {}).get("data") or []

    def fx_rates(self, base: str = "USD") -> dict:
        return (self.get("/forex/rates", {"base": base}) or {}).get("quote") or {}


# ---------- 健康检查与代码转换 ----------
def health_check(force: bool = False) -> dict:
    """探测 Finnhub 连通性+key有效性，结果缓存 config/finnhub_health.json。
    返回 {"ok": bool, "reason": str, "checked_at": ts, "latency_ms": int}。
    缓存有效期内直接读缓存，避免每次跑批重复探测。
    """
    cfg = load_config()
    if not cfg.get("enabled", False):
        return {"ok": False, "reason": "disabled", "checked_at": None, "latency_ms": None}
    if not force:
        try:
            with open(HEALTH_CACHE_PATH, encoding="utf-8") as f:
                cache = json.load(f)
            age = time.time() - cache.get("_ts", 0)
            if age < cfg.get("health_cache_sec", 600):
                return {k: v for k, v in cache.items() if k != "_ts"}
        except Exception:
            pass
    cli = FinnhubClient(cfg)
    t0 = time.time()
    try:
        q = cli.quote("AAPL")
        ok = bool(q.get("c"))
        result = {"ok": ok, "reason": "ok" if ok else "empty quote",
                  "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                  "latency_ms": int((time.time() - t0) * 1000)}
    except FinnhubError as e:
        result = {"ok": False, "reason": str(e)[:200],
                  "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                  "latency_ms": int((time.time() - t0) * 1000)}
    result["_ts"] = time.time()
    try:
        # P0-1: 原子写入(此前安全修复的运行时key擦除逻辑保持不变——result写入前不再含token)
        storage.save_json(result, HEALTH_CACHE_PATH)
    except Exception:
        pass
    return {k: v for k, v in result.items() if k != "_ts"}


def us_symbol_from_code(code: str) -> str:
    """模块K线码 → Finnhub symbol: usAAPL.OQ/usBABA.N/usSPY.AM → AAPL/BABA/SPY。
    指数码（usDJI/usIXIC/usINX/usNDX）非个股, Finnhub 指数 symbol 体系不同(^DJI等),
    腾讯通道已稳定覆盖 → 返回 None, 调用方直接走腾讯。"""
    if not code.startswith("us"):
        return None
    sym = code[2:]
    if "." in sym:
        sym = sym.split(".")[0]
    if sym in {"DJI", "IXIC", "INX", "NDX"}:  # 指数排除, 固定腾讯通道
        return None
    return sym if sym.isalpha() and 1 <= len(sym) <= 6 else None
