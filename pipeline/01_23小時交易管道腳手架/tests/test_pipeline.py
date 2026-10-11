"""Unit tests for the US-24h data pipeline scaffold.

Run:  python3 -m pytest tests -q     (or)     python3 tests/test_pipeline.py
"""

import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from anchor import archive_dates, is_activated, observe, roll_forward  # noqa: E402
from verify import CloseReport, verify  # noqa: E402
from windows import ET, HKT, boundary_after, in_maintenance, to_hkt  # noqa: E402


# ---------- windows ----------

def test_maintenance_window_membership():
    assert in_maintenance(datetime(2026, 12, 6, 20, 30, tzinfo=ET)) is True
    assert in_maintenance(datetime(2026, 12, 6, 19, 59, tzinfo=ET)) is False
    assert in_maintenance(datetime(2026, 12, 6, 21, 0, tzinfo=ET)) is False
    assert in_maintenance(datetime(2026, 12, 7, 3, 0, tzinfo=ET)) is False  # overnight tail


def test_bar_boundary_cut_at_maintenance_edges():
    mon = datetime(2026, 12, 7, tzinfo=ET)  # EST
    assert boundary_after(mon.replace(hour=19, minute=0)) == datetime(2026, 12, 7, 20, 0, tzinfo=ET)
    assert boundary_after(mon.replace(hour=20, minute=30)) == datetime(2026, 12, 7, 21, 0, tzinfo=ET)
    assert boundary_after(mon.replace(hour=22, minute=0)) == datetime(2026, 12, 8, 20, 0, tzinfo=ET)


def test_dst_hkt_mapping_matches_macro_leg_numbers():
    # Winter (EST, +13h): week-open Sun 2026-12-06 21:00 ET -> Mon 10:00 HKT
    assert to_hkt(datetime(2026, 12, 6, 21, 0, tzinfo=ET)) == datetime(2026, 12, 7, 10, 0, tzinfo=HKT)
    # Summer (EDT, +12h): Sun 2027-03-14 21:00 ET -> Mon 09:00 HKT (full HK/A coverage)
    assert to_hkt(datetime(2027, 3, 14, 21, 0, tzinfo=ET)) == datetime(2027, 3, 15, 9, 0, tzinfo=HKT)
    # Maintenance window mapping: winter 20:30 ET -> 09:30 HKT; summer -> 08:30 HKT
    assert to_hkt(datetime(2026, 12, 7, 20, 30, tzinfo=ET)) == datetime(2026, 12, 8, 9, 30, tzinfo=HKT)
    assert to_hkt(datetime(2027, 3, 15, 20, 30, tzinfo=ET)) == datetime(2027, 3, 16, 8, 30, tzinfo=HKT)


# ---------- anchor ----------

def test_calendar_activation_vs_actual_t0():
    assert is_activated(date(2026, 12, 5)) is False
    assert is_activated(date(2026, 12, 6)) is True

    # activated but SEC readiness gate not effective -> harmless idle (keep polling)
    idle = observe(date(2026, 12, 6), overnight_ran=False)
    assert idle.activated and not idle.effective and idle.t0 is None

    # actual first overnight session day -> T-0
    t0 = observe(date(2026, 12, 6), overnight_ran=True)
    assert t0.effective and t0.t0 == date(2026, 12, 6)

    # pre-activation observation can never be effective
    early = observe(date(2026, 12, 5), overnight_ran=True)
    assert not early.activated and not early.effective and early.t0 is None


def test_archive_checkpoints_t0_plus_1_2():
    assert archive_dates(date(2026, 12, 6)) == {"partial": date(2026, 12, 7),
                                                "final": date(2026, 12, 8)}
    # Friday anchor: +1 lands Saturday -> rolls to Sunday (week opens Sun 21:00 ET);
    # +2 lands Sunday -> stays (Sunday has a 21:00 ET session open, no roll needed)
    assert roll_forward(date(2026, 12, 11)) == date(2026, 12, 11)  # Fri stays
    assert roll_forward(date(2026, 12, 12)) == date(2026, 12, 13)  # Sat -> Sun
    assert archive_dates(date(2026, 12, 11)) == {"partial": date(2026, 12, 13),
                                                 "final": date(2026, 12, 13)}


# ---------- verify ----------

def test_verify_official_corroborated():
    r = CloseReport("SPY", "2026-12-07", {"S1": 773.93, "S2": 773.90, "S3": None})
    out = verify(r)
    assert out["status"] == "verified" and out["corroborated_by"] == ["S2"]
    assert out["deviants"] == [] and out["missing"] == ["S3"]


def test_verify_official_not_corroborated_manual():
    r = CloseReport("SPY", "2026-12-07", {"S1": 773.93, "S2": 771.0, "S3": None})
    assert verify(r)["status"] == "manual_review"


def test_verify_deviants_listed_but_still_verified():
    r = CloseReport("NVDA", "2026-12-07", {"S1": 187.30, "S2": 187.35, "S3": 190.0})
    out = verify(r)
    assert out["status"] == "verified" and out["deviants"] == ["S3"]


def test_verify_insufficient_sources():
    r = CloseReport("MU", "2026-12-07", {"S1": 951.6, "S2": None, "S3": None})
    out = verify(r)
    assert out["status"] == "insufficient" and out["present"] == ["S1"]


def test_verify_no_official_all_agree():
    r = CloseReport("GLDM", "2026-12-07", {"S1": None, "S2": 85.29, "S3": 85.30})
    assert verify(r)["status"] == "verified_no_official"


def test_verify_no_official_disagree():
    r = CloseReport("GLDM", "2026-12-07", {"S1": None, "S2": 85.29, "S3": 86.0})
    assert verify(r)["status"] == "manual_review"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)} tests passed.")
