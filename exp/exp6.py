"""Experiment 6: change-point test for a structural break in the daily reversal (Sec. 4.4).

A sup-Wald test (Andrews, 1993) for a single shift in the mean of the daily
reversal series R_t over 2016-2026, 15% trimmed, with a block-bootstrap
p-value (999 draws, 21-day blocks) on the primary, proxy and full-index
series, plus a linearly detrended version, a descriptive three-period
chi-squared(2) test, and a Monte Carlo power simulation against a dip that
reverses.

Run: python -m exp.exp6 [--full]
"""

from __future__ import annotations

import argparse
import logging

import pandas as pd

from src import changepoint, config, data_pipeline, reversal, samples

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("exp6")


def _reversal_series(sample):
    ranked = reversal.scaled_rank(sample, value_col="rod3")
    wls = reversal.daily_wls_slope(ranked)
    return reversal.daily_reversal_series(wls)


def _registered_rule(sup_wald: dict, p: float, detrended_p: float) -> bool:
    """Break declared only if p < 0.01, date in 2020-2024, and the detrended test also gives p < 0.01 (Sec. 4.4)."""
    start, end = config.CHANGEPOINT_BREAK_WINDOW
    in_window = pd.Timestamp(start) <= sup_wald["break_date"] <= pd.Timestamp(end)
    return bool(p < config.CHANGEPOINT_BREAK_P_BAR and in_window and detrended_p < config.CHANGEPOINT_BREAK_P_BAR)


def _break_test(series) -> dict:
    sup_wald = changepoint.sup_wald_test(series)
    p = changepoint.block_bootstrap_pvalue(series, sup_wald["stat"])
    interval = changepoint.break_date_interval(series)
    detrended = changepoint.linear_detrend(series)
    sup_wald_detrended = changepoint.sup_wald_test(detrended)
    p_detrended = changepoint.block_bootstrap_pvalue(detrended, sup_wald_detrended["stat"])
    declared = _registered_rule(sup_wald, p, p_detrended)
    return {
        "stat": sup_wald["stat"],
        "p": p,
        "break_date": str(sup_wald["break_date"].date()),
        "break_date_90pct_interval": [str(interval["lower_date"].date()), str(interval["upper_date"].date())],
        "detrended_stat": sup_wald_detrended["stat"],
        "detrended_p": p_detrended,
        "break_declared": declared,
    }


def run(use_cache: bool = True) -> dict:
    table, run_universe, universe_info = data_pipeline.build_run_universe(use_cache=use_cache)
    panel, panel_info = data_pipeline.build_filtered_panel(
        run_universe, table, config.SAMPLE_START, config.SAMPLE_END, use_cache=use_cache
    )
    excluded = samples.static_heavy_traded_list(panel, exclude_count=config.EXCLUDE_COUNT_RUN)
    sample_defs = {
        "primary": samples.exclude_static(panel, excluded),
        "proxy": samples.exclude_dynamic_daily_top_n(panel, n=config.EXCLUDE_COUNT_RUN),
        "full_index": panel,
    }

    result = {"universe_info": universe_info, "panel_info": panel_info, "samples": {}}
    series_by_sample = {}
    for name, sample in sample_defs.items():
        series = _reversal_series(sample)
        series_by_sample[name] = series
        logger.info("%s: %d daily reversal observations", name, series.dropna().shape[0])
        break_test = _break_test(series)
        chi2 = changepoint.three_period_chi2_test(series, config.PERIOD_E, config.PERIOD_T, config.PERIOD_L)
        result["samples"][name] = {"sup_wald_test": break_test, "three_period_chi2_test": chi2}

    primary_series = series_by_sample["primary"]
    period_means = {
        name: reversal.period_reversal(primary_series, *period)["mean"]
        for name, period in [("E", config.PERIOD_E), ("T", config.PERIOD_T), ("L", config.PERIOD_L)]
    }
    period_lengths = {
        name: int(
            ((primary_series.index >= period[0]) & (primary_series.index <= period[1])).sum()
        )
        for name, period in [("E", config.PERIOD_E), ("T", config.PERIOD_T), ("L", config.PERIOD_L)]
    }
    demeaned = primary_series.copy()
    for name, period in [("E", config.PERIOD_E), ("T", config.PERIOD_T), ("L", config.PERIOD_L)]:
        mask = (demeaned.index >= period[0]) & (demeaned.index <= period[1])
        demeaned.loc[mask] = demeaned.loc[mask] - period_means[name]
    residual_pool = demeaned.dropna().to_numpy()

    power = changepoint.power_simulation(period_means, residual_pool, period_lengths)
    result["power_simulation"] = power
    logger.info(
        "power simulation: sup-Wald rejects at 5%%=%.2f, 1%%=%.2f, full rule fires=%.3f",
        power["reject_rate_5pct"], power["reject_rate_1pct"], power["full_rule_fire_rate"],
    )

    primary_series.rename("R_t").to_csv(data_pipeline.RESULTS_DIR / "exp6_primary_reversal_series.csv")
    data_pipeline.save_json("exp6_results.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="use the paper's full point-in-time S&P 500 universe")
    parser.add_argument("--no-cache", action="store_true", help="bypass the on-disk data cache")
    args = parser.parse_args()
    if args.full:
        config.UNIVERSE_SIZE_RUN = config.UNIVERSE_SIZE_PAPER
    run(use_cache=not args.no_cache)
