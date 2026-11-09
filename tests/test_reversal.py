"""Unit tests for src.reversal: rank transform, WLS reversal, period statistics."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import reversal


def test_scaled_rank_bounds_and_monotonicity(synthetic_panel: pd.DataFrame) -> None:
    ranked = reversal.scaled_rank(synthetic_panel, value_col="rod3")
    assert ranked["q"].min() >= -0.5 - 1e-9
    assert ranked["q"].max() <= 0.5 + 1e-9
    one_day = ranked[ranked["date"] == ranked["date"].iloc[0]].sort_values("rod3")
    assert one_day["q"].is_monotonic_increasing


def test_daily_wls_recovers_known_negative_slope(synthetic_panel: pd.DataFrame) -> None:
    ranked = reversal.scaled_rank(synthetic_panel, value_col="rod3")
    wls = reversal.daily_wls_slope(ranked)
    assert len(wls) == synthetic_panel["date"].nunique()
    assert wls["b"].mean() == pytest.approx(-0.01, abs=0.01)


def test_daily_reversal_series_sign(synthetic_panel: pd.DataFrame) -> None:
    ranked = reversal.scaled_rank(synthetic_panel, value_col="rod3")
    wls = reversal.daily_wls_slope(ranked)
    R_t = reversal.daily_reversal_series(wls)
    assert R_t.mean() > 0  # losers beat winners into the close, by construction


def test_newey_west_mean_matches_sample_mean_on_iid_series() -> None:
    rng = np.random.default_rng(0)
    series = pd.Series(rng.normal(0.001, 0.0002, size=500))
    result = reversal.newey_west_mean(series, lags=5)
    assert result["mean"] == pytest.approx(series.mean())
    assert result["se"] > 0
    assert result["n"] == 500


def test_newey_west_mean_empty_series() -> None:
    result = reversal.newey_west_mean(pd.Series(dtype=float))
    assert result["n"] == 0
    assert np.isnan(result["mean"])


def test_quintile_spread_sign(synthetic_panel: pd.DataFrame) -> None:
    spread = reversal.quintile_spread_series(synthetic_panel)
    assert len(spread) > 0
    assert spread.mean() > 0  # bottom-ROD3 (losers) outperform top-ROD3 (winners), by construction


def test_change_test_formula() -> None:
    result = reversal.change_test(mean_e=3.13e-4, se_e=4.16e-5, mean_l=3.05e-4, se_l=1.02e-4)
    assert result["delta"] == pytest.approx(-0.08e-4, abs=1e-6)
    assert result["se"] == pytest.approx(np.sqrt(4.16e-5**2 + 1.02e-4**2))


def test_one_sided_decline_bound_matches_paper_order_of_magnitude() -> None:
    # Period E and L point estimates from the paper's primary-sample result (Sec. 4.2):
    # reversal_E = 3.13 bps/day (t=7.52), reversal_L = 3.05 bps/day (t=2.98), so
    # se_E = mean_E / t_E and se_L = mean_L / t_L.
    mean_e, t_e = 3.13e-4, 7.52
    mean_l, t_l = 3.05e-4, 2.98
    se_e, se_l = mean_e / t_e, mean_l / t_l
    result = reversal.one_sided_decline_bound(mean_e, se_e, mean_l, se_l)
    assert result["bound_bps"] == pytest.approx(1.9e-4, rel=0.25)
    assert result["fraction_of_e"] == pytest.approx(0.61, rel=0.25)


def test_reproduction_test_gate() -> None:
    assert reversal.reproduction_test(mean_e=3.13e-4, t_e=7.52) is True
    assert reversal.reproduction_test(mean_e=-1e-4, t_e=7.52) is False
    assert reversal.reproduction_test(mean_e=1e-4, t_e=1.0) is False


def test_verdict_rules() -> None:
    no_weak = reversal.change_test(3.13e-4, 4.16e-5, 3.05e-4, 1.02e-4)
    assert reversal.verdict(mean_l=3.05e-4, t_l=2.98, change=no_weak) == "no weakening"

    weakened = reversal.change_test(3.40e-4, 5.1e-5, 0.74e-4, 1.3e-4)
    assert reversal.verdict(mean_l=0.74e-4, t_l=0.55, change=weakened) in ("inconclusive", "weakened")

    strongly_weakened = {"delta": -3.0e-4, "se": 0.8e-4, "t": -3.75}
    assert reversal.verdict(mean_l=0.1e-4, t_l=0.2, change=strongly_weakened) == "weakened"


def test_apply_stock_day_filters_drops_low_price_and_large_moves() -> None:
    panel = pd.DataFrame(
        {
            "ticker": ["A", "B", "C"],
            "date": pd.to_datetime(["2021-01-01"] * 3),
            "prior_close": [4.0, 100.0, 50.0],
            "open": [4.1, 150.0, 51.0],
            "overnight_return": [0.025, 0.5, 0.02],
            "prior_month_dollar_volume": [1e6, 1e6, 1e6],
        }
    )
    out = reversal.apply_stock_day_filters(panel)
    assert set(out["ticker"]) == {"C"}
