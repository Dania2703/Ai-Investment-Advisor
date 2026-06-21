"""
src/analysis/indicators.py
==========================
Audited, dependency-light technical-indicator calculations.

Why native (NumPy/pandas) instead of pandas-ta?
-----------------------------------------------
TradingView's built-in indicators use very specific conventions:

* **Wilder's smoothing (RMA)** for RSI, ATR and ADX — *not* a simple moving
  average. RMA is an EWMA with ``alpha = 1 / period``.
* **EMA** (``alpha = 2 / (period + 1)``) for MACD.
* **Population standard deviation** (``ddof = 0``) for Bollinger Bands.

Off-the-shelf libraries silently mix these conventions, which is the usual
reason a home-grown engine disagrees with TradingView. Implementing the maths
explicitly here makes every number reproducible, unit-testable and aligned with
TradingView's methodology.

Design rules enforced throughout
--------------------------------
* **No look-ahead bias** — every indicator uses only the current and past bars
  (``rolling`` / ``ewm`` / ``cumsum`` / ``diff``; never a forward ``shift``).
* **NaN-safe warm-up** — values are ``NaN`` until enough history exists
  (``min_periods``), so an under-warmed indicator is never silently 0.
* **Alignment** — all series share the input DataFrame's index, so callers can
  combine them without re-indexing surprises.

Every function takes plain pandas Series/DataFrame and returns the same, so the
module is trivial to test against known values.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Smoothing primitives
# --------------------------------------------------------------------------- #
def rma(series: pd.Series, period: int) -> pd.Series:
    """
    Wilder's Running Moving Average (a.k.a. SMMA / RMA).

    Equivalent to an EWMA with ``alpha = 1 / period``. This is the smoothing
    TradingView uses internally for RSI, ATR and ADX.
    """
    return series.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average (``alpha = 2 / (period + 1)``)."""
    return series.ewm(span=period, min_periods=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period, min_periods=period).mean()


# --------------------------------------------------------------------------- #
# Momentum
# --------------------------------------------------------------------------- #
def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index using Wilder's smoothing — matches TradingView.

    RSI = 100 - 100 / (1 + RS),  RS = avg_gain / avg_loss.
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = rma(gain, period)
    avg_loss = rma(loss, period)

    # Where avg_loss == 0 the stock only rose over the window -> RSI = 100.
    rs = avg_gain / avg_loss
    out = 100.0 - (100.0 / (1.0 + rs))
    out = out.where(avg_loss != 0, 100.0)
    out = out.where(~((avg_gain == 0) & (avg_loss == 0)), 50.0)
    # Keep the warm-up NaNs (first `period` bars have no defined RSI).
    out[avg_gain.isna() | avg_loss.isna()] = np.nan
    return out


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """
    Moving Average Convergence Divergence.

    Returns a DataFrame with columns ``macd``, ``signal`` and ``hist``.
    """
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line.dropna(), signal).reindex(close.index)
    hist = macd_line - signal_line
    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "hist": hist},
        index=close.index,
    )


def stoch_rsi(
    close: pd.Series,
    period: int = 14,
    k: int = 3,
    d: int = 3,
) -> pd.DataFrame:
    """
    Stochastic RSI — the stochastic oscillator applied to RSI.

    Returns a DataFrame with columns ``k`` and ``d`` on a 0-100 scale.
    """
    r = rsi(close, period)
    lowest = r.rolling(period, min_periods=period).min()
    highest = r.rolling(period, min_periods=period).max()
    rng = (highest - lowest)
    stoch = (r - lowest) / rng.where(rng != 0, np.nan)
    k_line = (stoch.rolling(k, min_periods=k).mean()) * 100.0
    d_line = k_line.rolling(d, min_periods=d).mean()
    return pd.DataFrame({"k": k_line, "d": d_line}, index=close.index)


# --------------------------------------------------------------------------- #
# Volatility
# --------------------------------------------------------------------------- #
def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """True Range = max(H-L, |H-prevC|, |L-prevC|)."""
    prev_close = close.shift(1)
    ranges = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range (Wilder-smoothed)."""
    return rma(true_range(high, low, close), period)


def bollinger_bands(
    close: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
) -> pd.DataFrame:
    """
    Bollinger Bands using *population* standard deviation (ddof=0), as
    TradingView does.

    Returns columns ``middle``, ``upper``, ``lower`` and ``percent_b``
    (price position within the band: 0 = lower, 1 = upper).
    """
    middle = sma(close, period)
    std = close.rolling(period, min_periods=period).std(ddof=0)
    upper = middle + num_std * std
    lower = middle - num_std * std
    width = (upper - lower)
    percent_b = (close - lower) / width.where(width != 0, np.nan)
    return pd.DataFrame(
        {"middle": middle, "upper": upper, "lower": lower, "percent_b": percent_b},
        index=close.index,
    )


# --------------------------------------------------------------------------- #
# Trend strength
# --------------------------------------------------------------------------- #
def adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.DataFrame:
    """
    Average Directional Index with +DI / -DI (Wilder) — matches TradingView.

    Returns columns ``adx``, ``plus_di`` and ``minus_di``.
    """
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=high.index)
    minus_dm = pd.Series(minus_dm, index=high.index)

    atr_ = rma(true_range(high, low, close), period)
    plus_di = 100.0 * rma(plus_dm, period) / atr_
    minus_di = 100.0 * rma(minus_dm, period) / atr_

    di_sum = (plus_di + minus_di)
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum.where(di_sum != 0, np.nan)
    adx_line = rma(dx, period)
    return pd.DataFrame(
        {"adx": adx_line, "plus_di": plus_di, "minus_di": minus_di},
        index=high.index,
    )


# --------------------------------------------------------------------------- #
# Volume
# --------------------------------------------------------------------------- #
def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    On-Balance Volume — cumulative volume signed by daily price direction.
    """
    direction = np.sign(close.diff().fillna(0.0))
    return (direction * volume).cumsum()


def volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
    """Simple moving average of volume (the 'normal' volume baseline)."""
    return volume.rolling(period, min_periods=period).mean()


# --------------------------------------------------------------------------- #
# Support / Resistance
# --------------------------------------------------------------------------- #
def support_resistance(
    high: pd.Series,
    low: pd.Series,
    lookback: int = 60,
) -> tuple[float | None, float | None]:
    """
    Estimate the nearest swing support and resistance over ``lookback`` bars.

    A pragmatic, explainable definition: support is the lowest low and
    resistance the highest high in the recent window. Uses only past/current
    bars, so there is no look-ahead.
    """
    if len(low) == 0 or len(high) == 0:
        return None, None
    window_low = low.tail(lookback).dropna()
    window_high = high.tail(lookback).dropna()
    support = float(window_low.min()) if not window_low.empty else None
    resistance = float(window_high.max()) if not window_high.empty else None
    return support, resistance
