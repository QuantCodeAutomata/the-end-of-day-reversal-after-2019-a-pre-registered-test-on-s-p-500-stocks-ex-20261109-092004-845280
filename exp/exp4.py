"""Experiment 4: mechanism tests (Sec. 5).

Four pre-registered mechanism tests on the primary sample, judged together as
one Holm-corrected family at alpha=0.05 (Sec. 5.1): the change in the
market-component reversal from E to L, the change in the idiosyncratic
component, and the weekday same-day-option-expiry difference-in-differences.
A fourth, exploratory test of single-stock leveraged-ETF launches (Sec. 5.2)
requires at least ``config.LEVERAGED_ETF_MIN_TREATED`` treated stocks inside
the sample to be judged; when fewer are available it is reported but left out
of the Holm family, exactly as the pre-registered rule requires.

Run: python -m exp.exp4 [--full]
"""

from __future__ import annotations

import argparse
import logging

import numpy as np
import pandas as pd
from scipy.stats import norm

from data import data_loader as dl
from src import config, data_pipeline, mechanism, reversal, samples

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("exp4")


def _t_to_p(t: float) -> float:
    return float(2.0 * (1.0 - norm.cdf(abs(t)))) if np.isfinite(t) else np.nan


def _period_stats(series: pd.Series) -> dict:
    return {
        name: reversal.period_reversal(series, *period)
        for name, period in [("E", config.PERIOD_E), ("T", config.PERIOD_T), ("L", config.PERIOD_L)]
    }


def _match_controls(launch_dates: dict, dollar_volume: pd.Series, universe: list[str]) -> dict:
    """``config.LEVERAGED_ETF_CONTROLS_PER_TREATED`` untreated stocks of nearest dollar volume (Sec. 5.2)."""
    treated = set(launch_dates)
    pool = dollar_volume[dollar_volume.index.isin(universe) & ~dollar_volume.index.isin(treated)]
    control_map = {}
    for ticker, dv in dollar_volume.items():
        if ticker not in treated:
            continue
        ranked = (pool - dv).abs().sort_values()
        control_map[ticker] = list(ranked.index[: config.LEVERAGED_ETF_CONTROLS_PER_TREATED])
    return control_map


def run(use_cache: bool = True) -> dict:
    table, run_universe, universe_info = data_pipeline.build_run_universe(use_cache=use_cache)
    panel, panel_info = data_pipeline.build_filtered_panel(
        run_universe, table, config.SAMPLE_START, config.SAMPLE_END, use_cache=use_cache
    )
    excluded = samples.static_heavy_traded_list(panel, exclude_count=config.EXCLUDE_COUNT_RUN)
    primary = samples.exclude_static(panel, excluded)
    logger.info("primary sample for mechanism tests: %d rows, %d tickers", len(primary), primary["ticker"].nunique())

    spy_panel, _ = reversal.load_stock_day_panel(["SPY"], config.MECHANISM_START, config.SAMPLE_END, use_cache=use_cache)
    rod3_spy = spy_panel.set_index("date")["rod3"]
    spy_daily_return = (spy_panel["close"] / spy_panel["prior_close"] - 1.0)
    spy_daily_return.index = spy_panel["date"]

    daily = primary.sort_values(["ticker", "date"]).copy()
    daily["daily_return"] = daily["close"] / daily["prior_close"] - 1.0
    stock_returns = daily.pivot(index="date", columns="ticker", values="daily_return")

    betas = mechanism.rolling_beta(stock_returns, spy_daily_return)
    split = mechanism.split_market_idiosyncratic(primary, rod3_spy, betas)
    split = split[split["date"] >= pd.Timestamp(config.MECHANISM_START)]
    logger.info("market/idiosyncratic split panel: %d rows from %s", len(split), config.MECHANISM_START)

    two_factor = mechanism.daily_two_factor_wls(split)
    market_reversal = -two_factor["b_market"]
    idio_reversal = -two_factor["b_idio"]

    market_stats = _period_stats(market_reversal)
    idio_stats = _period_stats(idio_reversal)
    market_change = reversal.change_test(
        market_stats["E"]["mean"], market_stats["E"]["se"], market_stats["L"]["mean"], market_stats["L"]["se"]
    )
    idio_change = reversal.change_test(
        idio_stats["E"]["mean"], idio_stats["E"]["se"], idio_stats["L"]["mean"], idio_stats["L"]["se"]
    )

    weekday = mechanism.weekday_option_did(market_reversal, start=config.WEEKDAY_DID_START)

    # Leveraged-ETF launch test (Sec. 5.2): treated stocks are the run universe's
    # own-slope stack of ``config.LEVERAGED_ETF_LAUNCHES`` restricted to tickers
    # present in the primary sample.
    ranked_primary = reversal.scaled_rank(primary, value_col="rod3")
    treated_in_sample = {
        t: pd.Timestamp(d) for t, d in config.LEVERAGED_ETF_LAUNCHES.items() if t in set(primary["ticker"])
    }
    dollar_volume = primary.groupby("ticker")["prior_month_dollar_volume"].mean()
    control_map = _match_controls(treated_in_sample, dollar_volume, run_universe)
    etf_result = mechanism.leveraged_etf_stacked_did(ranked_primary, treated_in_sample, control_map)
    logger.info(
        "leveraged-ETF launch test: %d treated stocks in sample (need >= %d) -> %s",
        etf_result["n_treated"], config.LEVERAGED_ETF_MIN_TREATED,
        "judged" if etf_result.get("meets_min_treated") else "not judged (exploratory)",
    )

    p_values = {
        "market_component_change": _t_to_p(market_change["t"]),
        "idiosyncratic_component_change": _t_to_p(idio_change["t"]),
        "weekday_option_did": _t_to_p(weekday["t"]),
    }
    judged_names = list(p_values)
    if etf_result.get("meets_min_treated"):
        p_values["leveraged_etf_launch"] = _t_to_p(etf_result["t"])
        judged_names.append("leveraged_etf_launch")
    holm = mechanism.holm_family([p_values[name] for name in judged_names], alpha=config.HOLM_ALPHA)

    result = {
        "universe_info": universe_info,
        "panel_info": panel_info,
        "market_component_bps": {
            "E": market_stats["E"]["mean"] * 1e4, "L": market_stats["L"]["mean"] * 1e4,
            "T": market_stats["T"]["mean"] * 1e4,
            "change_bps": market_change["delta"] * 1e4, "change_t": market_change["t"],
        },
        "idiosyncratic_component_bps": {
            "E": idio_stats["E"]["mean"] * 1e4, "L": idio_stats["L"]["mean"] * 1e4,
            "T": idio_stats["T"]["mean"] * 1e4,
            "change_bps": idio_change["delta"] * 1e4, "change_t": idio_change["t"],
        },
        "weekday_option_did": weekday,
        "leveraged_etf_launch": etf_result,
        "leveraged_etf_treated_tickers": sorted(treated_in_sample),
        "holm_family": {
            "tests": judged_names,
            "p_values": [p_values[name] for name in judged_names],
            "adjusted_p": holm["adjusted_p"],
            "reject_at_alpha": holm["reject"],
            "any_test_passes": bool(any(holm["reject"])),
        },
    }

    data_pipeline.save_json("exp4_results.json", result)
    pd.DataFrame(
        {"market_reversal_bps": market_reversal * 1e4, "idiosyncratic_reversal_bps": idio_reversal * 1e4}
    ).to_csv(data_pipeline.RESULTS_DIR / "exp4_components.csv")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="use the paper's full point-in-time S&P 500 universe")
    parser.add_argument("--no-cache", action="store_true", help="bypass the on-disk data cache")
    args = parser.parse_args()
    if args.full:
        config.UNIVERSE_SIZE_RUN = config.UNIVERSE_SIZE_PAPER
    run(use_cache=not args.no_cache)
