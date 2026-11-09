"""Experiment 3: full-index reversal test, no exclusions (Sec. 3.1, 4.2, 4.5).

Runs the same estimator on every run-universe member with no exclusion, and
adds the descriptive weight/outlier diagnoses of Sec. 4.5: equal weights,
square-root dollar-volume weights, 1%/99% winsorized LH, dropping the 5/10/20
largest members each day, leave-one-out range, effective number of stocks,
the 80-largest-only estimate, and the paired proxy-vs-80-largest difference.

Run: python -m exp.exp3 [--full]
"""

from __future__ import annotations

import argparse
import logging

import numpy as np
import pandas as pd

from src import config, data_pipeline, reversal, samples

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("exp3")


def _period_table(R_t: pd.Series) -> dict:
    stats = {name: reversal.period_reversal(R_t, *period)
             for name, period in [("E", config.PERIOD_E), ("T", config.PERIOD_T), ("L", config.PERIOD_L)]}
    all_later = reversal.period_reversal(R_t, config.PERIOD_T[0], config.PERIOD_L[1])
    change = reversal.change_test(stats["E"]["mean"], stats["E"]["se"], stats["L"]["mean"], stats["L"]["se"])
    return {
        "period_stats_bps": {k: {"reversal_mean_bps": v["mean"] * 1e4, "t": v["t"], "n": v["n"]} for k, v in stats.items()},
        "all_later_sessions_bps": {"reversal_mean_bps": all_later["mean"] * 1e4, "t": all_later["t"], "n": all_later["n"]},
        "change_l_minus_e_bps": change["delta"] * 1e4,
        "change_t": change["t"],
    }, stats


def run(use_cache: bool = True) -> dict:
    table, run_universe, universe_info = data_pipeline.build_run_universe(use_cache=use_cache)
    panel, panel_info = data_pipeline.build_filtered_panel(
        run_universe, table, config.SAMPLE_START, config.SAMPLE_END, use_cache=use_cache
    )
    logger.info("full-index panel (no exclusions): %d rows, %d sessions", len(panel), panel_info["sessions_total"])

    ranked = reversal.scaled_rank(panel, value_col="rod3")
    result: dict = {"universe_info": universe_info, "panel_info": panel_info}

    main_wls = reversal.daily_wls_slope(ranked)
    R_main = reversal.daily_reversal_series(main_wls)
    result["dollar_volume_weighted"], main_stats = _period_table(R_main)

    equal = ranked.assign(_equal_weight=1.0)
    R_equal = reversal.daily_reversal_series(reversal.daily_wls_slope(equal, weight_col="_equal_weight"))
    result["equal_weighted"], _ = _period_table(R_equal)

    sqrt_w = ranked.assign(_sqrt_dv=np.sqrt(ranked["prior_month_dollar_volume"].clip(lower=0)))
    R_sqrt = reversal.daily_reversal_series(reversal.daily_wls_slope(sqrt_w, weight_col="_sqrt_dv"))
    result["sqrt_dollar_volume_weighted"], _ = _period_table(R_sqrt)

    def _winsorize(group: pd.Series, pct: float) -> pd.Series:
        lo, hi = group.quantile(pct), group.quantile(1 - pct)
        return group.clip(lo, hi)

    wins = ranked.copy()
    wins["lh"] = wins.groupby("date")["lh"].transform(lambda s: _winsorize(s, config.WINSORIZE_PCT))
    R_wins = reversal.daily_reversal_series(reversal.daily_wls_slope(wins))
    result["winsorized_lh"], _ = _period_table(R_wins)

    for n in config.DROP_LARGEST_N_PAPER:
        dropped = samples.exclude_dynamic_daily_top_n(panel, n=n)
        ranked_dropped = reversal.scaled_rank(dropped, value_col="rod3")
        R_dropped = reversal.daily_reversal_series(reversal.daily_wls_slope(ranked_dropped))
        result[f"drop_top_{n}"], _ = _period_table(R_dropped)

    eighty_only = samples.keep_dynamic_daily_top_n(panel, n=config.EXCLUDE_COUNT_RUN)
    ranked_80 = reversal.scaled_rank(eighty_only, value_col="rod3")
    R_80 = reversal.daily_reversal_series(reversal.daily_wls_slope(ranked_80))
    result["among_largest_only"], stats_80 = _period_table(R_80)

    proxy = samples.exclude_dynamic_daily_top_n(panel, n=config.EXCLUDE_COUNT_RUN)
    ranked_proxy = reversal.scaled_rank(proxy, value_col="rod3")
    R_proxy = reversal.daily_reversal_series(reversal.daily_wls_slope(ranked_proxy))
    paired = pd.concat([R_proxy.rename("proxy"), R_80.rename("largest")], axis=1).dropna()
    paired_diff = reversal.newey_west_mean(paired["proxy"] - paired["largest"])
    result["paired_proxy_minus_largest_bps"] = {
        "mean_bps": paired_diff["mean"] * 1e4, "t": paired_diff["t"], "n": paired_diff["n"]
    }

    eff_n = samples.effective_n_series(panel)
    result["effective_n"] = {
        "E_mean": float(eff_n[(eff_n.index >= config.PERIOD_E[0]) & (eff_n.index <= config.PERIOD_E[1])].mean()),
        "L_mean": float(eff_n[(eff_n.index >= config.PERIOD_L[0]) & (eff_n.index <= config.PERIOD_L[1])].mean()),
    }
    result["leave_one_out_L"] = samples.leave_one_out_range(panel, config.PERIOD_L)

    data_pipeline.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    R_main.rename("R_t").to_csv(data_pipeline.RESULTS_DIR / "exp3_daily_reversal_full_index.csv")
    data_pipeline.save_json("exp3_results.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()
    if args.full:
        config.UNIVERSE_SIZE_RUN = config.UNIVERSE_SIZE_PAPER
    run(use_cache=not args.no_cache)
