"""Point-in-time S&P 500 membership and the paper's heavily-traded exclusions.

The membership table is the public, community-maintained history used by the
paper to make its sample reproducible (Sec. 3.1): fja05680's "S&P 500
Historical Components & Changes" table, giving, for each change date, the
full list of tickers that were members on that date.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import requests

from src import config

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
MEMBERSHIP_CACHE = CACHE_DIR / "sp500_membership.csv"


class UniverseError(RuntimeError):
    """A failure to load or parse the point-in-time membership table."""


def load_membership_table(use_cache: bool = True) -> pd.DataFrame:
    """Rows of (date, tickers) giving the full S&P 500 member list as of each change date.

    Source: fja05680's community-maintained GitHub repository (Sec. 3.1,
    "S&P 500 Historical Components & Changes"). Not Massive/Dataloader data:
    it is point-in-time index-membership reference data of the specific
    public form the paper names for reproducibility.
    """
    if use_cache and MEMBERSHIP_CACHE.exists():
        return pd.read_csv(MEMBERSHIP_CACHE, parse_dates=["date"])
    response = requests.get(config.SP500_MEMBERSHIP_URL, timeout=60)
    if response.status_code != 200:
        raise UniverseError(
            f"membership table fetch failed: HTTP {response.status_code}"
        )
    table = pd.read_csv(io.BytesIO(response.content))
    if "date" not in table.columns or "tickers" not in table.columns:
        raise UniverseError(f"unexpected membership columns: {list(table.columns)}")
    table["date"] = pd.to_datetime(table["date"])
    table = table.sort_values("date").reset_index(drop=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(MEMBERSHIP_CACHE, index=False)
    return table


def members_on_date(table: pd.DataFrame, as_of: pd.Timestamp) -> set[str]:
    """S&P 500 members as of ``as_of``, using the latest change row not after it."""
    prior = table[table["date"] <= as_of]
    if prior.empty:
        raise UniverseError(f"no membership row at or before {as_of}")
    row = prior.iloc[-1]
    return {t.strip() for t in str(row["tickers"]).split(",") if t.strip()}


def membership_by_day(
    table: pd.DataFrame, trading_days: pd.DatetimeIndex
) -> dict[pd.Timestamp, set[str]]:
    """Point-in-time member set for every trading day (Sec. 3.1, step 1)."""
    return {day: members_on_date(table, day) for day in trading_days}


def rank_universe_for_run(
    all_members: set[str],
    dollar_volume_by_ticker: pd.Series,
    universe_size: int,
) -> list[str]:
    """Reduce the full point-in-time membership to ``universe_size`` names.

    Selects the most liquid members as of ``config.UNIVERSE_RANKING_DATE`` by
    prior-month dollar volume, the paper's own liquidity measure (Sec. 3.1),
    so that the daily/30-minute/5-minute history for 2016-2026 fits the time
    available for this replication (see results/RESULTS.md, "Deviations from
    the paper").
    """
    candidates = dollar_volume_by_ticker[
        dollar_volume_by_ticker.index.isin(all_members)
    ].dropna()
    ranked = candidates.sort_values(ascending=False)
    return list(ranked.index[:universe_size])
