"""
tests/test_indicators.py
========================
Audits the native indicator maths:

* correctness against hand-computed / closed-form values,
* TradingView-aligned conventions (Wilder smoothing, population stdev),
* NaN warm-up behaviour and index alignment,
* **no look-ahead bias** (truncating future bars never changes past values).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analysis import indicators as ind


# --------------------------------------------------------------------------- #
# Closed-form / hand-computed correctness
# --------------------------------------------------------------------------- #
def test_sma_known_value(small_close):
    out = ind.sma(small_close, 5)
    assert out.iloc[:4].isna().all()          # warm-up
    assert out.iloc[-1] == pytest.approx(3.0)  # mean(1..5)


def test_ema_recursive_formula(small_close):
    # adjust=False EMA: e0=x0; e_t = a*x_t + (1-a)*e_{t-1}; a = 2/(n+1)
    n = 3
    a = 2 / (n + 1)
    e = small_close.iloc[0]
    for x in small_close.iloc[1:]:
        e = a * x + (1 - a) * e
    out = ind.ema(small_close, n)
    assert out.iloc[-1] == pytest.approx(e)


def test_rsi_all_gains_is_100():
    close = pd.Series(np.arange(1, 30, dtype=float))
    out = ind.rsi(close, 14).dropna()
    assert (out > 99.999).all()


def test_rsi_bounds(synthetic_ohlcv):
    out = ind.rsi(synthetic_ohlcv["Close"], 14).dropna()
    assert out.between(0, 100).all()
    assert len(out) > 0


def test_macd_components(synthetic_ohlcv):
    close = synthetic_ohlcv["Close"]
    df = ind.macd(close, 12, 26, 9)
    expected_macd = ind.ema(close, 12) - ind.ema(close, 26)
    pd.testing.assert_series_equal(
        df["macd"].dropna(), expected_macd.dropna(), check_names=False
    )
    # histogram = macd - signal
    hist = (df["macd"] - df["signal"]).dropna()
    pd.testing.assert_series_equal(df["hist"].dropna(), hist, check_names=False)


def test_true_range_hand_value():
    high = pd.Series([10.0, 12.0])
    low = pd.Series([9.0, 8.0])
    close = pd.Series([9.5, 11.0])
    tr = ind.true_range(high, low, close)
    # bar 2: max(12-8, |12-9.5|, |8-9.5|) = max(4, 2.5, 1.5) = 4
    assert tr.iloc[1] == pytest.approx(4.0)


def test_bollinger_uses_population_std(synthetic_ohlcv):
    close = synthetic_ohlcv["Close"]
    bb = ind.bollinger_bands(close, 20, 2.0)
    manual_std = close.rolling(20).std(ddof=0)          # population
    manual_upper = close.rolling(20).mean() + 2 * manual_std
    pd.testing.assert_series_equal(
        bb["upper"].dropna(), manual_upper.dropna(), check_names=False
    )
    # %B within band should sit in [0, 1] for the middle
    assert bb["percent_b"].dropna().between(-0.5, 1.5).all()


def test_adx_bounds_and_direction(uptrend_ohlcv, downtrend_ohlcv):
    up = ind.adx(uptrend_ohlcv["High"], uptrend_ohlcv["Low"], uptrend_ohlcv["Close"], 14)
    down = ind.adx(downtrend_ohlcv["High"], downtrend_ohlcv["Low"], downtrend_ohlcv["Close"], 14)
    assert up["adx"].dropna().between(0, 100).all()
    # In a clean uptrend +DI dominates; in a downtrend -DI dominates.
    assert up["plus_di"].dropna().iloc[-1] > up["minus_di"].dropna().iloc[-1]
    assert down["minus_di"].dropna().iloc[-1] > down["plus_di"].dropna().iloc[-1]


def test_obv_direction():
    close = pd.Series([10, 11, 10, 12])     # up, down, up
    vol = pd.Series([100, 200, 300, 400])
    out = ind.obv(close, vol)
    # cumulative: 0, +200, -300, +400 -> 0, 200, -100, 300
    assert list(out) == [0, 200, -100, 300]


def test_support_resistance(synthetic_ohlcv):
    s, r = ind.support_resistance(synthetic_ohlcv["High"], synthetic_ohlcv["Low"], 60)
    assert s is not None and r is not None
    assert r >= s


# --------------------------------------------------------------------------- #
# Alignment + warm-up
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("fn", [
    lambda c: ind.rsi(c, 14),
    lambda c: ind.sma(c, 50),
    lambda c: ind.ema(c, 20),
    lambda c: ind.stoch_rsi(c)["k"],
    lambda c: ind.bollinger_bands(c)["percent_b"],
])
def test_index_alignment(synthetic_ohlcv, fn):
    close = synthetic_ohlcv["Close"]
    out = fn(close)
    assert out.index.equals(close.index)


def test_warmup_is_nan(synthetic_ohlcv):
    close = synthetic_ohlcv["Close"]
    assert ind.sma(close, 50).iloc[:49].isna().all()
    assert np.isnan(ind.rsi(close, 14).iloc[0])


# --------------------------------------------------------------------------- #
# No look-ahead bias: truncating future bars must not change past values.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("fn", [
    lambda c: ind.rsi(c, 14),
    lambda c: ind.macd(c)["macd"],
    lambda c: ind.macd(c)["signal"],
    lambda c: ind.ema(c, 50),
    lambda c: ind.sma(c, 50),
])
def test_no_lookahead(synthetic_ohlcv, fn):
    close = synthetic_ohlcv["Close"]
    cutoff = 300
    full = fn(close)
    truncated = fn(close.iloc[:cutoff])
    a = full.iloc[cutoff - 1]
    b = truncated.iloc[cutoff - 1]
    if pd.isna(a) and pd.isna(b):
        return
    assert a == pytest.approx(b, rel=1e-9, abs=1e-9)
