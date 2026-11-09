"""Experiment 2: proxy-sample reversal test (Sec. 3.1, 4.2).

Drops, each day, the largest members of the run universe by prior-month
dollar volume (``config.EXCLUDE_COUNT_RUN``, the run-scaled analogue of the
paper's 80 largest names), giving a sample anyone can rebuild from public
data. Reported alongside the primary sample but not part of the registered
evidence (Sec. 3.1): no reproduction gate or verdict is applied here.

Run: python -m exp.exp2 [--full]
"""

from __future__ import annotations

import argparse
import logging

from src import config, data_pipeline, reversal, samples

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("exp2")


def run(use_cache: bool = True) -> dict:
    table, run_universe, universe_info = data_pipeline.build_run_universe(use_cache=use_cache)
    panel, panel_info = data_pipeline.build_filtered_panel(
        run_universe, table, config.SAMPLE_START, config.SAMPLE_END, use_cache=use_cache
    )
    logger.info("filtered panel: %d rows, %d sessions", len(panel), panel_info["sessions_total"])

    proxy = samples.exclude_dynamic_daily_top_n(panel, n=config.EXCLUDE_COUNT_RUN)
    logger.info("proxy sample: %d rows after dropping the %d largest members each day",
                len(proxy), config.EXCLUDE_COUNT_RUN)

    ranked = reversal.scaled_rank(proxy, value_col="rod3")
    wls = reversal.daily_wls_slope(ranked)
    R_t = reversal.daily_reversal_series(wls)

    stats = {name: reversal.period_reversal(R_t, *period)
             for name, period in [("E", config.PERIOD_E), ("T", config.PERIOD_T), ("L", config.PERIOD_L)]}
    all_later = reversal.period_reversal(R_t, config.PERIOD_T[0], config.PERIOD_L[1])
    change = reversal.change_test(stats["E"]["mean"], stats["E"]["se"], stats["L"]["mean"], stats["L"]["se"])

    result = {
        "universe_info": universe_info,
        "panel_info": panel_info,
        "n_sessions_proxy": int(proxy["date"].nunique()),
        "period_stats_bps": {
            k: {"reversal_mean_bps": v["mean"] * 1e4, "t": v["t"], "n": v["n"]} for k, v in stats.items()
        },
        "all_later_sessions_bps": {"reversal_mean_bps": all_later["mean"] * 1e4, "t": all_later["t"], "n": all_later["n"]},
        "change_l_minus_e_bps": change["delta"] * 1e4,
        "change_t": change["t"],
        "note": "exploratory, not part of the pre-registered confirmatory evidence (Sec. 3.1)",
    }

    data_pipeline.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    R_t.rename("R_t").to_csv(data_pipeline.RESULTS_DIR / "exp2_daily_reversal.csv")
    data_pipeline.save_json("exp2_results.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()
    if args.full:
        config.UNIVERSE_SIZE_RUN = config.UNIVERSE_SIZE_PAPER
    run(use_cache=not args.no_cache)
