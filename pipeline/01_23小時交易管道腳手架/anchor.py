"""T-0 anchor: calendar activation vs actual first overnight session.

Protocol v1.1 (2026-10-10, joint four-leg verification):
- Monitor clocks activate on calendar day >= 2026-12-06 ET ("date >= 12/6 auto-activate").
  Activation without effectiveness = harmless idle (keep polling, no action).
- SEC gate is "no earlier than 2026-12-06" (infrastructure readiness), so the true
  anchor T-0 = the ACTUAL first day an overnight session RUNS.
- Once T-0 observed (three-source check: overnight prints exist + 16:00 official
  close anchor clean), verification/archive checkpoints are anchored at T-0+1/+2
  -- actual session days, NOT calendar-derived from 12/6.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

CALENDAR_ACTIVATION = date(2026, 12, 6)  # ET calendar; "not earlier than"


@dataclass
class AnchorState:
    activated: bool            # calendar activation fired (d >= 12/6)
    effective: bool            # overnight session actually observed running
    t0: date | None = None     # actual first overnight-session day


def is_activated(d: date) -> bool:
    """Calendar-based activation (monitor clocks, regulatory watch)."""
    return d >= CALENDAR_ACTIVATION


def observe(d: date, overnight_ran: bool) -> AnchorState:
    """Fold one daily observation into anchor state."""
    activated = is_activated(d)
    effective = activated and overnight_ran
    return AnchorState(activated=activated, effective=effective,
                       t0=d if effective else None)


def roll_forward(d: date) -> date:
    """Skip Saturday (no session open). Sun-Fri all have opens (Sun 21:00 = week open)."""
    if d.weekday() == 5:  # Saturday
        return d + timedelta(days=1)
    return d


def archive_dates(t0: date) -> dict[str, date]:
    """Verification/archive checkpoints from the OBSERVED T-0 (not calendar 12/6).

    partial = T-0+1, final = T-0+2; Saturday checkpoints roll forward to Sunday
    (week opens Sun 21:00 ET).
    """
    return {"partial": roll_forward(t0 + timedelta(days=1)),
            "final": roll_forward(t0 + timedelta(days=2))}
