"""
tests/conftest.py
=================
Shared fixtures: a small hand-checkable OHLCV frame and a larger deterministic
synthetic series for property-based indicator tests.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def small_close() -> pd.Series:
    """A tiny, hand-verifiable close series."""
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    return pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=idx, name="Close")


@pytest.fixture
def synthetic_ohlcv() -> pd.DataFrame:
    """
    A 400-bar deterministic random walk with OHLCV columns.

    Deterministic (seeded) so indicator values are reproducible across runs,
    which is what lets us test 'no look-ahead' and stability.
    """
    rng = np.random.default_rng(42)
    n = 400
    idx = pd.date_range("2022-01-01", periods=n, freq="B")  # business days
    steps = rng.normal(0.0005, 0.02, n)
    close = 100 * np.exp(np.cumsum(steps))
    close = pd.Series(close, index=idx)

    high = close * (1 + rng.uniform(0, 0.015, n))
    low = close * (1 - rng.uniform(0, 0.015, n))
    open_ = close.shift(1).fillna(close.iloc[0])
    volume = pd.Series(rng.integers(1_000_000, 5_000_000, n), index=idx, dtype=float)

    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


@pytest.fixture
def uptrend_ohlcv() -> pd.DataFrame:
    """A clean, strong uptrend — every bullish trend signal should fire."""
    n = 300
    idx = pd.date_range("2022-01-01", periods=n, freq="B")
    close = pd.Series(np.linspace(50, 150, n), index=idx)
    high = close * 1.01
    low = close * 0.99
    open_ = close.shift(1).fillna(close.iloc[0])
    volume = pd.Series(np.linspace(1e6, 3e6, n), index=idx)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


@pytest.fixture
def downtrend_ohlcv() -> pd.DataFrame:
    """A clean, strong downtrend — every bearish trend signal should fire."""
    n = 300
    idx = pd.date_range("2022-01-01", periods=n, freq="B")
    close = pd.Series(np.linspace(150, 50, n), index=idx)
    high = close * 1.01
    low = close * 0.99
    open_ = close.shift(1).fillna(close.iloc[0])
    volume = pd.Series(np.linspace(3e6, 1e6, n), index=idx)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )
