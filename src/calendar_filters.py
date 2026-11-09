"""NYSE scheduled 1 p.m. early-close sessions (Sec. 3.1, methodology step 2).

The paper drops 21 sessions with a scheduled early close inside its 2016-2026
window. No official exchange calendar is bundled with this replication, so
the three recurring NYSE early-close occasions are derived programmatically
from the calendar rule that has governed them for decades:
  - the Friday after Thanksgiving (4th Thursday of November + 1 day);
  - the session immediately before July 4th, when July 4th itself is a
    midweek trading day (Tue-Fri), so the preceding day is a genuine trading
    session distinct from a weekend;
  - December 24th, when it falls on a business day (Mon-Fri).
This is recorded as an assumption in results/RESULTS.md rather than sourced
from a vendor calendar.
"""

from __future__ import annotations

import pandas as pd


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> pd.Timestamp:
    """The n-th occurrence (1-indexed) of ``weekday`` (Mon=0) in a given month."""
    first = pd.Timestamp(year=year, month=month, day=1)
    offset = (weekday - first.weekday()) % 7
    return first + pd.Timedelta(days=offset + 7 * (n - 1))


def nyse_early_close_dates(start: str, end: str) -> set[pd.Timestamp]:
    """Scheduled 1 p.m. early closes between ``start`` and ``end`` (inclusive)."""
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    dates: set[pd.Timestamp] = set()
    for year in range(start_ts.year, end_ts.year + 1):
        thanksgiving = _nth_weekday_of_month(year, 11, weekday=3, n=4)  # 4th Thursday
        dates.add(thanksgiving + pd.Timedelta(days=1))

        july4 = pd.Timestamp(year=year, month=7, day=4)
        if july4.weekday() in (1, 2, 3, 4):  # Tue-Fri: a genuine midweek holiday
            dates.add(july4 - pd.Timedelta(days=1))

        christmas_eve = pd.Timestamp(year=year, month=12, day=24)
        if christmas_eve.weekday() <= 4:  # Mon-Fri
            dates.add(christmas_eve)
    return {d for d in dates if start_ts <= d <= end_ts}
