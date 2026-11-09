"""Experiment 5: next-morning price-pressure test, kappa reversal give-back (Sec. 4.6).

Tests whether the closing reversal gives back the following morning
(transitory price pressure, kappa close to -1) or persists (kappa close to
0). kappa = mean next-morning slope / mean closing slope is computed on the
primary, proxy, full-index and "among the 80 largest" samples for periods E
and L, together with the combined (closing + next-morning) reversal and a
set of descriptive robustness checks on the full index (Sec. 4.5-4.6).

Run: python -m exp.exp5 [--full]
"""

from __future__ import annotations

import argparse
import logging

import pandas as pd

from data import data_loader as dl
from src import config, data_pipeline, nextmorning, reversal, samples

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("exp5")


def _sample_kappa(with_next: pd.DataFrame) -> dict:
    ranked = reversal.scaled_rank(with_next, value_col="rod3")
    closing = reversal.daily_wls_slope(ranked)
    nxt = nextmorning.daily_next_morning_slope(ranked)
    out = {}
    for name, period in [("E", config.PERIOD_E), ("L", config.PERIOD_L)]:
        c = closing["b"][(closing.index >= period[0]) & (closing.index <= period[1])]
        n = nxt["b"][(nxt.index >= period[0]) & (nxt.index <= period[1])]
        kap = nextmorning.kappa_interval(c, n)
        combined = nextmorning.combined_reversal(c, n)
        out[name] = {
            "kappa": kap["kappa"], "kappa_lower": kap["lower"], "kappa_upper": kap["upper"],
            "combined_reversal_bps": combined["mean"] * 1e4, "combined_t": combined["t"], "n": kap["n"],
        }
    return out


def run(use_cache: bool = True) -> dict:
    table, run_universe, universe_info = data_pipeline.build_run_universe(use_cache=use_cache)
    panel, panel_info = data_pipeline.build_filtered_panel(
        run_universe, table, config.SAMPLE_START, config.SAMPLE_END, use_cache=use_cache
    )
    daily_bars, _ = dl.load_ohlcv(run_universe, config.SAMPLE_START, config.SAMPLE_END, timeframe="1d", use_cache=use_cache)

    excluded = samples.static_heavy_traded_list(panel, exclude_count=config.EXCLUDE_COUNT_RUN)
    sample_defs = {
        "primary": samples.exclude_static(panel, excluded),
        "proxy": samples.exclude_dynamic_daily_top_n(panel, n=config.EXCLUDE_COUNT_RUN),
        "full_index": panel,
        "among_80_largest": samples.keep_dynamic_daily_top_n(panel, n=config.EXCLUDE_COUNT_RUN),
    }

    result = {"universe_info": universe_info, "panel_info": panel_info, "samples": {}}
    for name, sample in sample_defs.items():
        with_next = nextmorning.add_next_morning_return(sample, daily_bars)
        result["samples"][name] = _sample_kappa(with_next)
        logger.info("%s: kappa_E=%.2f kappa_L=%.2f", name, result["samples"][name]["E"]["kappa"], result["samples"][name]["L"]["kappa"])

    # Descriptive robustness on the full index (Sec. 4.5-4.6): winsorized LH,
    # square-root weights, equal weights, dropping the 5 largest each day.
    full_with_next = nextmorning.add_next_morning_return(sample_defs["full_index"], daily_bars)
    robustness = {}

    winsorized = reversal.winsorize_column(full_with_next, "lh", out_col="lh")
    robustness["winsorized_lh"] = _sample_kappa(winsorized)

    sqrt_w = full_with_next.copy()
    sqrt_w["prior_month_dollar_volume"] = sqrt_w["prior_month_dollar_volume"].pow(0.5)
    robustness["sqrt_weights"] = _sample_kappa(sqrt_w)

    equal_w = full_with_next.copy()
    equal_w["prior_month_dollar_volume"] = 1.0
    robustness["equal_weights"] = _sample_kappa(equal_w)

    drop5 = samples.exclude_dynamic_daily_top_n(full_with_next, n=5)
    robustness["drop_5_largest"] = _sample_kappa(drop5)

    result["full_index_robustness"] = robustness

    # BDS-form descriptive coefficients (Sec. 4.6): daily regressions of the
    # raw (not rank-transformed) closing and next-morning returns on the raw
    # ROD3, both winsorized at 1%/99%, with dollar-volume weights and
    # Newey-West errors, as in BDS's own panel specification (Sec. 3.3).
    bds_panel = reversal.winsorize_column(full_with_next, "rod3", out_col="rod3_w")
    bds_panel = reversal.winsorize_column(bds_panel, "lh", out_col="lh_w")
    bds_panel = reversal.winsorize_column(bds_panel, "next_morning_return", out_col="next_morning_return_w")
    bds_close = reversal.daily_wls_slope(bds_panel, y_col="lh_w", x_col="rod3_w")
    bds_next_input = bds_panel.assign(q=bds_panel["rod3_w"], next_morning_return=bds_panel["next_morning_return_w"])
    bds_next = nextmorning.daily_next_morning_slope(bds_next_input)
    bds_form = {}
    for name, period in [("E", config.PERIOD_E), ("L", config.PERIOD_L)]:
        c = bds_close["b"][(bds_close.index >= period[0]) & (bds_close.index <= period[1])]
        n = bds_next["b"][(bds_next.index >= period[0]) & (bds_next.index <= period[1])]
        bds_form[name] = {
            "closing_coefficient": float(c.mean()) if len(c) else float("nan"),
            "next_morning_coefficient": float(n.mean()) if len(n) else float("nan"),
            "kappa": nextmorning.kappa(float(c.mean()), float(n.mean())) if len(c) and len(n) else float("nan"),
        }
    result["bds_form_full_index"] = bds_form

    data_pipeline.save_json("exp5_results.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="use the paper's full point-in-time S&P 500 universe")
    parser.add_argument("--no-cache", action="store_true", help="bypass the on-disk data cache")
    args = parser.parse_args()
    if args.full:
        config.UNIVERSE_SIZE_RUN = config.UNIVERSE_SIZE_PAPER
    run(use_cache=not args.no_cache)
