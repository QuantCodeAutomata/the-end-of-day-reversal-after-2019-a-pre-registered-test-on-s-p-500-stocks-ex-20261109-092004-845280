"""Shared pytest fixtures: synthetic stock-day panels and the market-data marker."""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "market_data: test loads a reduced real slice through data/data_loader.py"
    )


@pytest.fixture(scope="session")
def rng() -> np.random.Generator:
    return np.random.default_rng(20190813)


@pytest.fixture
def synthetic_panel(rng: np.random.Generator) -> pd.DataFrame:
    """A stock-day panel with a known, injected reversal: LH = -0.01 * q + noise.

    40 tickers x 60 trading days. ``rod3`` drives the cross-sectional rank
    ``q`` used by ``src.reversal.scaled_rank``; ``lh`` is built so the true
    WLS slope is close to -0.01 (i.e. reversal R_t = -b_t is close to +0.01).
    """
    n_tickers, n_days = 40, 60
    dates = pd.bdate_range("2021-01-04", periods=n_days)
    tickers = [f"T{i:02d}" for i in range(n_tickers)]
    rows = []
    for date in dates:
        rod3 = rng.normal(0, 0.01, size=n_tickers)
        rank = pd.Series(rod3).rank(method="average").to_numpy()
        q = (rank - 1) / (n_tickers - 1) - 0.5
        lh = -0.01 * q + rng.normal(0, 0.002, size=n_tickers)
        weight = rng.uniform(1e6, 1e8, size=n_tickers)
        for i, ticker in enumerate(tickers):
            rows.append(
                {
                    "ticker": ticker,
                    "date": date,
                    "prior_close": 100.0,
                    "open": 100.0 * (1 + rng.normal(0, 0.002)),
                    "rod3": rod3[i],
                    "lh": lh[i],
                    "overnight_return": rng.normal(0, 0.002),
                    "prior_month_dollar_volume": weight[i],
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture
def daily_slice(request: pytest.FixtureRequest) -> tuple[pd.DataFrame, dict]:
    """A reduced real slice (a few tickers, ~1 year) loaded through data/data_loader.py.

    Cached across test runs with pytest's cache so repeated sessions do not
    re-download it. Skipped when DATALOADER_API_KEY is not set.
    """
    if not os.environ.get("DATALOADER_API_KEY"):
        pytest.skip("DATALOADER_API_KEY not set: market-data test skipped")
    from data import data_loader as dl

    cache_key = "market_data/daily_slice_v1"
    cached = request.config.cache.get(cache_key, None)
    if cached is not None:
        bars = pd.DataFrame(cached["bars"])
        bars["date"] = pd.to_datetime(bars["date"])
        bars["timestamp"] = pd.to_datetime(bars["timestamp"])
        return bars, cached["meta"]
    bars, meta = dl.load_ohlcv(
        ["AAPL", "MSFT"], "2023-01-03", "2023-06-30", timeframe="1d", use_cache=True
    )
    request.config.cache.set(
        cache_key,
        {"bars": bars.astype(str).to_dict(orient="list"), "meta": {}},
    )
    return bars, meta
