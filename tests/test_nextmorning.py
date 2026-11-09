"""Unit tests for src.nextmorning: kappa give-back ratio and next-morning slope."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import nextmorning


def test_kappa_full_giveback() -> None:
    assert nextmorning.kappa(closing_slope_mean=-0.01, next_morning_slope_mean=0.01) == -1.0


def test_kappa_zero_closing_slope_is_nan() -> None:
    assert np.isnan(nextmorning.kappa(0.0, 0.01))


def test_add_next_morning_return_uses_next_session_open() -> None:
    panel = pd.DataFrame(
        {
            "ticker": ["A", "A", "A"],
            "date": pd.to_datetime(["2021-01-04", "2021-01-05", "2021-01-06"]),
            "p1600m": [100.0, 102.0, 101.0],
        }
    )
    daily = pd.DataFrame(
        {
            "ticker": ["A", "A", "A"],
            "date": pd.to_datetime(["2021-01-04", "2021-01-05", "2021-01-06"]),
            "open": [100.0, 102.5, 101.5],
        }
    )
    out = nextmorning.add_next_morning_return(panel, daily)
    # 2021-01-04's next_morning_return uses 2021-01-05's open (102.5) over its own p1600m (100.0)
    first = out[out["date"] == "2021-01-04"].iloc[0]
    assert first["next_morning_return"] == pytest.approx(102.5 / 100.0 - 1.0)
    # the last date has no next session and must be dropped
    assert "2021-01-06" not in out["date"].astype(str).tolist()


def test_daily_next_morning_slope_runs(synthetic_panel: pd.DataFrame) -> None:
    from src import reversal

    panel = synthetic_panel.copy()
    panel["q"] = reversal.scaled_rank(panel, value_col="rod3")["q"]
    panel["next_morning_return"] = -0.005 * panel["q"] + np.random.default_rng(3).normal(
        0, 0.001, len(panel)
    )
    slopes = nextmorning.daily_next_morning_slope(panel, min_obs=5)
    assert len(slopes) == panel["date"].nunique()
    assert slopes["b"].mean() < 0
