"""Experiment 1: main end-of-day reversal test on the primary sample (Sec. 3-4).

Builds the point-in-time S&P 500 run universe, drops a fixed list of the
most heavily traded names (a substitute for the paper's unpublished ~80-name
exclusion, Sec. 3.1), and estimates the daily reversal R_t = -b_t from the
cross-sectional WLS regression of Eq. 1. The reproduction-test gate on
period E (Sec. 3.4) must pass before period L's confirmatory statistics are
read; this ordering is enforced in code, not only documented.

Run: python -m exp.exp1 [--full]
"""

from __future__ import annotations

import argparse
import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src import config, data_pipeline, reversal, samples

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("exp1")


def run(use_cache: bool = True) -> dict:
    table, run_universe, universe_info = data_pipeline.build_run_universe(use_cache=use_cache)
    logger.info("run universe: %d tickers (of %d point-in-time S&P 500 members)",
                len(run_universe), universe_info["sp500_members_at_ranking_date"])

    panel, panel_info = data_pipeline.build_filtered_panel(
        run_universe, table, config.SAMPLE_START, config.SAMPLE_END, use_cache=use_cache
    )
    logger.info("filtered panel: %d rows, %d sessions, %d tickers, range %s",
                len(panel), panel_info["sessions_total"], panel_info["tickers_total"], panel_info["date_range"])

    excluded = samples.static_heavy_traded_list(panel, exclude_count=config.EXCLUDE_COUNT_RUN)
    primary = samples.exclude_static(panel, excluded)
    logger.info("primary sample: excluded %d of %d run-universe tickers, %d rows remain",
                len(excluded), len(run_universe), len(primary))

    ranked = reversal.scaled_rank(primary, value_col="rod3")
    wls = reversal.daily_wls_slope(ranked)
    R_t = reversal.daily_reversal_series(wls)
    quintile = reversal.quintile_spread_series(primary)

    stats = {}
    for name, period in [("E", config.PERIOD_E), ("T", config.PERIOD_T), ("L", config.PERIOD_L)]:
        stats[name] = reversal.period_reversal(R_t, *period)
        stats[name]["quintile_spread"] = reversal.newey_west_mean(
            quintile[(quintile.index >= period[0]) & (quintile.index <= period[1])]
        )
    all_later = reversal.period_reversal(R_t, config.PERIOD_T[0], config.PERIOD_L[1])

    passed = reversal.reproduction_test(stats["E"]["mean"], stats["E"]["t"])
    logger.info("reproduction test on period E: R_E=%.4f bps t=%.2f -> %s",
                stats["E"]["mean"] * 1e4, stats["E"]["t"], "PASSED" if passed else "FAILED")

    result = {
        "universe_info": universe_info,
        "panel_info": panel_info,
        "excluded_tickers": excluded,
        "run_universe": run_universe,
        "n_sessions_primary": int(primary["date"].nunique()),
        "reproduction_test_passed": passed,
        "period_stats_bps": {
            k: {
                "reversal_mean_bps": v["mean"] * 1e4, "t": v["t"], "n": v["n"],
                "quintile_spread_bps": v["quintile_spread"]["mean"] * 1e4,
                "quintile_spread_t": v["quintile_spread"]["t"],
            }
            for k, v in stats.items()
        },
        "all_later_sessions_bps": {"reversal_mean_bps": all_later["mean"] * 1e4, "t": all_later["t"], "n": all_later["n"]},
    }

    if passed:
        change = reversal.change_test(stats["E"]["mean"], stats["E"]["se"], stats["L"]["mean"], stats["L"]["se"])
        bound = reversal.one_sided_decline_bound(stats["E"]["mean"], stats["E"]["se"], stats["L"]["mean"], stats["L"]["se"])
        verdict = reversal.verdict(stats["L"]["mean"], stats["L"]["t"], change)
        change_all = reversal.change_test(
            stats["E"]["mean"], stats["E"]["se"], all_later["mean"], all_later["se"]
        )
        bound_all = reversal.one_sided_decline_bound(
            stats["E"]["mean"], stats["E"]["se"], all_later["mean"], all_later["se"]
        )
        result["confirmatory"] = {
            "change_l_minus_e_bps": change["delta"] * 1e4, "change_t": change["t"],
            "one_sided_95_decline_bound_bps": bound["bound_bps"] * 1e4,
            "one_sided_95_decline_fraction_of_e": bound["fraction_of_e"],
            "verdict": verdict,
            "all_later_change_bps": change_all["delta"] * 1e4, "all_later_change_t": change_all["t"],
            "all_later_decline_bound_bps": bound_all["bound_bps"] * 1e4,
            "all_later_decline_fraction_of_e": bound_all["fraction_of_e"],
        }
    else:
        result["confirmatory"] = None
        logger.warning("reproduction test failed: no confirmatory statistic computed on period L")

    data_pipeline.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    R_t.rename("R_t").to_csv(data_pipeline.RESULTS_DIR / "exp1_daily_reversal.csv")
    data_pipeline.save_json("exp1_results.json", result)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(R_t.index, R_t.values * 1e4, linewidth=0.8)
    ax.axhline(0, color="black", linewidth=0.5)
    for period, label in [(config.PERIOD_E, "E"), (config.PERIOD_T, "T"), (config.PERIOD_L, "L")]:
        ax.axvspan(period[0], period[1], alpha=0.08)
    ax.set_title("Primary-sample daily end-of-day reversal R_t (Sec. 3.3-3.4)")
    ax.set_xlabel("date")
    ax.set_ylabel("R_t (bps)")
    fig.tight_layout()
    fig.savefig(data_pipeline.RESULTS_DIR / "exp1_daily_reversal.png", dpi=120)
    plt.close(fig)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="use the paper's full point-in-time S&P 500 universe")
    parser.add_argument("--no-cache", action="store_true", help="bypass the on-disk data cache")
    args = parser.parse_args()
    if args.full:
        config.UNIVERSE_SIZE_RUN = config.UNIVERSE_SIZE_PAPER
    run(use_cache=not args.no_cache)
