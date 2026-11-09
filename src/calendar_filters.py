"""NYSE scheduled 1 p.m. early-close sessions (Sec. 3.1, methodology step 2).

The paper drops 21 sessions with a scheduled early close inside its
2016-2026 window. These are the NYSE's publicly scheduled 1 p.m. closes (the
day after Thanksgiving, the session before July 4th when it falls on a
midweek trading day, and December 24th when it falls on a business day),
exactly 21 dates over the sample period.
"""

from __future__ import annotations

import pandas as pd

# NYSE scheduled 1 p.m. early closes, 2016-2026 (Sec. 3.1, methodology step 2):
# the day after Thanksgiving, the session before July 4th (when it falls on a
# Tue-Fri midweek session), and December 24th (when it falls on a business
# day). Exactly 21 dates over the sample period.
EARLY_CLOSE_DATES = {
    "2016-11-25", "2017-07-03", "2017-11-24", "2018-07-03", "2018-11-23",
    "2018-12-24", "2019-07-03", "2019-11-29", "2019-12-24", "2020-11-27",
    "2020-12-24", "2021-11-26", "2022-11-25", "2023-07-03", "2023-11-24",
    "2024-07-03", "2024-11-29", "2024-12-24", "2025-07-03", "2025-11-28",
    "2025-12-24",
}


def nyse_early_close_dates(start: str, end: str) -> set[pd.Timestamp]:
    """Scheduled 1 p.m. early closes between ``start`` and ``end`` (inclusive)."""
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    dates = {pd.Timestamp(d) for d in EARLY_CLOSE_DATES}
    return {d for d in dates if start_ts <= d <= end_ts}
