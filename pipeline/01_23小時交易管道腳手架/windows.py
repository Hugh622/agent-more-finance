"""US 23x5 session geometry: maintenance cut, bar boundaries, ET<->HKT mapping.

Locked facts (four-leg joint verification, 2026-10-10; federal-register chain):
- Continuous trading 21:00 ET -> 20:00 ET next calendar day = 23h; the only daily
  pause is the maintenance window 20:00-21:00 ET. Week opens Sun 21:00 ET, ends
  Fri 20:00 ET (Fri maintenance merges into the 49h weekend gap).
- Daily close anchor = 16:00 ET official closing auction (explicitly preserved).
- DST mapping to HKT: EST (UTC-5) -> +13h; EDT (UTC-4) -> +12h.
    winter 2026-12-06 ~ 2027-03-13: overnight = 10:00-17:00 HKT (partial overlap)
    summer from 2027-03-14:         overnight = 09:00-16:00 HKT (full HK/A coverage)
- Bar rule (protocol v1.1): no bar may span the maintenance window; bars are cut
  at 20:00 and resume at 21:00. Anchor-pull windows align to these edges.

All functions expect tz-aware datetimes.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
HKT = ZoneInfo("Asia/Hong_Kong")

MAINTENANCE_START = time(20, 0)  # inclusive
MAINTENANCE_END = time(21, 0)    # exclusive
OFFICIAL_CLOSE = time(16, 0)     # official closing auction, daily anchor


def to_hkt(ts: datetime) -> datetime:
    """Map an ET timestamp to HKT (DST-safe)."""
    return ts.astimezone(HKT)


def in_maintenance(ts: datetime) -> bool:
    """True if ts falls in the daily 20:00-21:00 ET maintenance window."""
    t = ts.astimezone(ET).time()
    return MAINTENANCE_START <= t < MAINTENANCE_END


def boundary_after(ts: datetime) -> datetime:
    """Earliest allowed bar boundary strictly after ts (ET, tz-aware).

    Any bar that would contain 20:00:00 ET is cut to close at 20:00; bars
    resume at 21:00. After 21:00 the next cut is the following day's 20:00.
    Finer (intra-session) bar boundaries layer on top of these cuts.
    """
    et_ts = ts.astimezone(ET)
    day = et_ts.date()
    m_start = datetime.combine(day, MAINTENANCE_START, tzinfo=ET)
    m_end = datetime.combine(day, MAINTENANCE_END, tzinfo=ET)
    if et_ts < m_start:
        return m_start
    if et_ts < m_end:
        return m_end
    return m_start + timedelta(days=1)
