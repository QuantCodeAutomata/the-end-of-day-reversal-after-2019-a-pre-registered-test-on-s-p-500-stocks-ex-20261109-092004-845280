"""Shared build of the run universe and the filtered stock-day panel (Sec. 3.1).

One place for the steps every experiment needs before it branches into its
own sample definition: point-in-time membership, the reduced run universe,
the raw stock-day panel from ``data/data_loader.py``, and the session/stock
filters of Sec. 3.1. Experiments 1-3 then apply their own ticker exclusion
(``src.samples``) to this one panel; experiments 4-6 reuse it unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src import config, reversal, universe

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def build_run_universe(use_cache: bool = True) -> tuple[pd.DataFrame, list[str], dict]:
    """Point-in-time S&P 500 membership table and the reduced run universe (Sec. 3.1).

    The run universe is the ``config.UNIVERSE_SIZE_RUN`` members of the
    ranking date (``config.UNIVERSE_RANKING_DATE``) with the highest prior
    reported dollar volume on Dataloader daily bars, a proxy for the paper's
    own liquidity ranking used only to size the universe for this
    replication (see results/RESULTS.md, "Deviations from the paper").
    """
    table = universe.load_membership_table(use_cache=use_cache)
    as_of = pd.Timestamp(config.UNIVERSE_RANKING_DATE)
    members = universe.members_on_date(table, as_of)

    from data import data_loader as dl

    ranking_start = (as_of - pd.Timedelta(days=45)).strftime("%Y-%m-%d")
    ranking_end = as_of.strftime("%Y-%m-%d")
    sample_tickers = sorted(members)
    bars, meta = dl.load_ohlcv(
        sample_tickers, ranking_start, ranking_end, timeframe="1d", use_cache=use_cache
    )
    bars = bars.copy()
    bars["dollar_volume"] = bars["close"] * bars["volume"]
    dollar_volume = bars.groupby("ticker")["dollar_volume"].mean()
    run_universe = universe.rank_universe_for_run(members, dollar_volume, config.UNIVERSE_SIZE_RUN)
    info = {
        "sp500_members_at_ranking_date": len(members),
        "universe_size_run": len(run_universe),
        "ranking_window": [ranking_start, ranking_end],
        "non_massive_source": meta.get("non_massive_source"),
        "failed": meta.get("failed"),
    }
    return table, run_universe, info


def build_filtered_panel(
    tickers: list[str], membership_table: pd.DataFrame, start: str, end: str, use_cache: bool = True
) -> tuple[pd.DataFrame, dict]:
    """Stock-day panel after the weight, price, overnight-move and session filters (Sec. 3.1)."""
    panel, load_meta = reversal.load_stock_day_panel(tickers, start, end, use_cache=use_cache)
    panel = reversal.add_prior_month_weight(panel)
    n_before_stock_filters = len(panel)
    panel = reversal.apply_stock_day_filters(panel)

    trading_days = pd.DatetimeIndex(sorted(panel["date"].unique()))
    membership_by_day = universe.membership_by_day(membership_table, trading_days)
    panel, session_info = reversal.apply_session_filters(panel, membership_by_day, start, end)

    info = {
        "load_meta": {
            "daily": load_meta["daily"].get("non_massive_source"),
            "thirty_min": load_meta["thirty_min"].get("non_massive_source"),
            "five_min": load_meta["five_min"].get("non_massive_source"),
            "failed": {
                k: load_meta[part].get("failed") for k, part in [("daily", "daily"), ("thirty_min", "thirty_min"), ("five_min", "five_min")]
            },
        },
        "rows_before_stock_filters": n_before_stock_filters,
        "rows_after_stock_filters": len(panel) + 0,  # updated below after session filters
        "session_filters": session_info,
        "sessions_total": panel["date"].nunique(),
        "tickers_total": panel["ticker"].nunique(),
        "date_range": [str(panel["date"].min().date()), str(panel["date"].max().date())] if len(panel) else None,
    }
    return panel, info


def save_json(name: str, payload: dict) -> Path:
    """Write ``payload`` as indented JSON under results/, converting Timestamps to strings."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / name
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path
