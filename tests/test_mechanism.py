"""Unit tests for src.mechanism: beta estimation, two-factor split, Holm correction."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import mechanism


def test_rolling_beta_recovers_known_slope() -> None:
    rng = np.random.default_rng(1)
    n = 400
    dates = pd.bdate_range("2019-01-02", periods=n)
    market = pd.Series(rng.normal(0, 0.01, n), index=dates)
    stock = 1.5 * market + rng.normal(0, 0.0005, n)
    betas = mechanism.rolling_beta(stock.to_frame("A"), market, window=252, min_periods=200)
    tail_beta = betas["A"].dropna().iloc[-20:].mean()
    assert tail_beta == pytest.approx(1.5, abs=0.2)


def test_holm_family_more_conservative_than_raw() -> None:
    p_values = [0.01, 0.03, 0.2, 0.5]
    result = mechanism.holm_family(p_values, alpha=0.05)
    assert all(adj >= raw for adj, raw in zip(result["adjusted_p"], p_values))
    assert result["reject"][0] is True or result["adjusted_p"][0] <= 0.05


def test_daily_two_factor_wls_runs_on_split_panel() -> None:
    rng = np.random.default_rng(2)
    n_tickers, n_days = 20, 10
    dates = pd.bdate_range("2021-01-04", periods=n_days)
    rows = []
    for date in dates:
        rod3_market = rng.normal(0, 0.005, n_tickers)
        rod3_idio = rng.normal(0, 0.008, n_tickers)
        lh = -0.02 * rod3_market - 0.01 * rod3_idio + rng.normal(0, 0.001, n_tickers)
        for i in range(n_tickers):
            rows.append(
                {
                    "ticker": f"T{i}",
                    "date": date,
                    "rod3_market": rod3_market[i],
                    "rod3_idio": rod3_idio[i],
                    "lh": lh[i],
                    "prior_month_dollar_volume": rng.uniform(1e6, 1e7),
                }
            )
    panel = pd.DataFrame(rows)
    result = mechanism.daily_two_factor_wls(panel, min_obs=5)
    assert len(result) == n_days
    assert {"b_market", "b_idio", "se_market", "se_idio"}.issubset(result.columns)
