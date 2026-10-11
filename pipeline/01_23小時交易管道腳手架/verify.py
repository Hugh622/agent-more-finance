"""16:00 official close anchor: multi-source verification (scaffold).

Locked design (four-leg joint verification, 2026-10-10):
- Daily close determination MUST anchor on the 16:00 ET official closing auction.
  Vendor daily-K fields (e.g. Tencent) may embed other session conventions and
  are treated as polluted for close determination -- never primary. In practice
  S1 = official print via Tencent/Sina dual-engine cross-check (dedicated 16:00
  anchor pull, NOT the vendor daily-K field).
- Sources, ranked:
    S1  official print / exchange official close                     (primary)
    S2  news close reviews (收评/新闻源)
    S3  z-ai web_search page snapshot ("At close: <date> 4:00 PM EDT <px>")
        -- 4th source is redundancy-only cross-check; live trial 2026-12-08
- Decision rule:
    S1 + >=1 corroborating source within tol        -> verified
    no S1, all present sources pairwise-consistent  -> verified_no_official
    fewer than MIN_SOURCES present                  -> insufficient
    otherwise                                       -> manual_review (full payload logged)
"""

from __future__ import annotations

from dataclasses import dataclass, field

MIN_SOURCES = 2
DEFAULT_TOL_PCT = 0.1


@dataclass
class CloseReport:
    symbol: str
    session_date: str  # ET date of the 16:00 official close, ISO-8601
    prices: dict[str, float | None] = field(default_factory=dict)  # {"S1":..., "S2":..., "S3":...}


def _within(a: float, b: float, tol_pct: float) -> bool:
    if a == 0 or b == 0:
        return a == b
    return abs(a - b) / max(abs(a), abs(b)) * 100.0 <= tol_pct


def verify(report: CloseReport, tol_pct: float = DEFAULT_TOL_PCT) -> dict:
    present = {k: v for k, v in report.prices.items() if v is not None}
    missing = sorted(set(report.prices) - set(present))
    base = {"symbol": report.symbol, "session_date": report.session_date,
            "present": sorted(present), "missing": missing}

    if len(present) < MIN_SOURCES:
        return {**base, "status": "insufficient",
                "reason": f"{len(present)} source(s) present, need >= {MIN_SOURCES}"}

    s1 = present.get("S1")
    if s1 is not None:
        corrob = sorted(k for k, v in present.items()
                        if k != "S1" and _within(s1, v, tol_pct))
        deviants = sorted(k for k, v in present.items()
                          if k != "S1" and not _within(s1, v, tol_pct))
        if corrob:
            return {**base, "status": "verified", "anchor": "S1",
                    "corroborated_by": corrob, "deviants": deviants}
        return {**base, "status": "manual_review",
                "reason": "official print S1 not corroborated within tolerance"}

    vals = list(present.values())
    if all(_within(vals[i], vals[j], tol_pct)
           for i in range(len(vals)) for j in range(i + 1, len(vals))):
        return {**base, "status": "verified_no_official",
                "reason": "S1 absent; all present sources consistent"}
    return {**base, "status": "manual_review",
            "reason": "S1 absent and present sources disagree beyond tolerance"}
