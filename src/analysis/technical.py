"""
src/analysis/technical.py
=========================
Turns a raw OHLCV history into a structured :class:`TechnicalSummary`:
the latest value of every indicator, a plain-language interpretation of each,
and a few convenience trend flags.

This module owns *measurement* only. It does not decide Buy/Hold/Sell — that is
the job of :mod:`src.analysis.scoring`, which consumes this summary.

All indicator maths lives in :mod:`src.analysis.indicators` (audited, native
NumPy/pandas implementations aligned with TradingView's conventions).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

from config import settings
from src.analysis import indicators as ind


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #
@dataclass
class Indicator:
    """A single indicator's latest reading, ready for transparent display."""

    key: str            # machine key, e.g. "rsi"
    label: str          # human label, e.g. "RSI (14)"
    value: Optional[float]
    display: str        # formatted value, e.g. "62.4"
    signal: str         # "Bullish" / "Bearish" / "Neutral" / "Overbought" ...
    note: str           # one-line interpretation


@dataclass
class TechnicalSummary:
    """Latest value of every indicator plus human-readable signals."""

    price: float
    as_of: Optional[pd.Timestamp]
    bars: int
    enough_data: bool

    # ---- Trend -----------------------------------------------------------
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    ema_200: Optional[float] = None

    # ---- Momentum --------------------------------------------------------
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    stoch_rsi_k: Optional[float] = None
    stoch_rsi_d: Optional[float] = None

    # ---- Volatility ------------------------------------------------------
    atr: Optional[float] = None
    atr_pct: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_percent_b: Optional[float] = None

    # ---- Trend strength --------------------------------------------------
    adx: Optional[float] = None
    plus_di: Optional[float] = None
    minus_di: Optional[float] = None

    # ---- Volume ----------------------------------------------------------
    volume: Optional[float] = None
    volume_sma: Optional[float] = None
    volume_ratio: Optional[float] = None
    obv: Optional[float] = None
    obv_ema: Optional[float] = None

    # ---- Support / Resistance -------------------------------------------
    support: Optional[float] = None
    resistance: Optional[float] = None

    # ---- Derived, human-friendly signals --------------------------------
    rsi_signal: str = "Unknown"
    macd_trend: str = "Unknown"
    ma_trend: str = "Unknown"
    composite_score: float = 0.0  # -1..+1, retained for backwards-compat

    # ---- Transparent per-indicator breakdown ----------------------------
    indicators: List[Indicator] = field(default_factory=list)

    def as_dict(self) -> dict:
        """Flat dict for persistence / logging (back-compatible keys kept)."""
        return {
            "RSI(14)": _round(self.rsi, 2),
            "MACD": _round(self.macd, 4),
            "MACD Signal": _round(self.macd_signal, 4),
            "MACD Histogram": _round(self.macd_hist, 4),
            "StochRSI %K": _round(self.stoch_rsi_k, 1),
            "StochRSI %D": _round(self.stoch_rsi_d, 1),
            "SMA 50": _round(self.sma_50, 2),
            "SMA 200": _round(self.sma_200, 2),
            "EMA 20": _round(self.ema_20, 2),
            "EMA 50": _round(self.ema_50, 2),
            "EMA 200": _round(self.ema_200, 2),
            "Bollinger Upper": _round(self.bb_upper, 2),
            "Bollinger Lower": _round(self.bb_lower, 2),
            "Bollinger %B": _round(self.bb_percent_b, 2),
            "ADX": _round(self.adx, 1),
            "+DI": _round(self.plus_di, 1),
            "-DI": _round(self.minus_di, 1),
            "ATR": _round(self.atr, 2),
            "ATR %": _round(self.atr_pct, 2),
            "OBV": _round(self.obv, 0),
            "Volume Ratio": _round(self.volume_ratio, 2),
            "Support": _round(self.support, 2),
            "Resistance": _round(self.resistance, 2),
            "RSI Signal": self.rsi_signal,
            "MACD Trend": self.macd_trend,
            "MA Trend": self.ma_trend,
        }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _latest(series: Optional[pd.Series]) -> Optional[float]:
    """Last non-NaN value of a series, or None."""
    if series is None:
        return None
    clean = series.dropna()
    return float(clean.iloc[-1]) if not clean.empty else None


def _round(value: Optional[float], digits: int) -> Optional[float]:
    return round(value, digits) if value is not None else None


def _fmt(value: Optional[float], digits: int = 2) -> str:
    return f"{value:,.{digits}f}" if value is not None else "N/A"


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #
def analyze(history: pd.DataFrame) -> TechnicalSummary:
    """
    Compute every indicator on an OHLCV history and derive readable signals.

    The history is expected to have ``Open/High/Low/Close/Volume`` columns and
    a sorted DatetimeIndex (see :func:`src.data.market_data.get_history`).
    """
    history = history.copy()
    close = history["Close"].astype(float)
    high = history["High"].astype(float)
    low = history["Low"].astype(float)
    volume = history.get("Volume")
    volume = volume.astype(float) if volume is not None else pd.Series(index=close.index, dtype=float)

    bars = int(close.dropna().shape[0])
    enough_data = bars >= settings.min_history_bars
    price = _latest(close) or 0.0
    as_of = close.dropna().index[-1] if bars else None

    # ---- Compute all indicator series -----------------------------------
    sma50 = ind.sma(close, settings.sma_short)
    sma200 = ind.sma(close, settings.sma_long)
    ema20 = ind.ema(close, settings.ema_fast)
    ema50 = ind.ema(close, settings.ema_mid)
    ema200 = ind.ema(close, settings.ema_slow)

    rsi_s = ind.rsi(close, settings.rsi_period)
    macd_df = ind.macd(close, settings.macd_fast, settings.macd_slow, settings.macd_signal)
    srsi = ind.stoch_rsi(
        close, settings.stoch_rsi_period, settings.stoch_rsi_k, settings.stoch_rsi_d
    )

    atr_s = ind.atr(high, low, close, settings.atr_period)
    bb = ind.bollinger_bands(close, settings.bb_period, settings.bb_std)
    adx_df = ind.adx(high, low, close, settings.adx_period)

    obv_s = ind.obv(close, volume)
    obv_ema_s = ind.ema(obv_s, settings.obv_ema_period)
    vol_sma_s = ind.volume_sma(volume, settings.volume_sma_period)
    support, resistance = ind.support_resistance(high, low, settings.sr_lookback)

    # ---- Latest scalar values -------------------------------------------
    summary = TechnicalSummary(
        price=price,
        as_of=as_of,
        bars=bars,
        enough_data=enough_data,
        sma_50=_latest(sma50),
        sma_200=_latest(sma200),
        ema_20=_latest(ema20),
        ema_50=_latest(ema50),
        ema_200=_latest(ema200),
        rsi=_latest(rsi_s),
        macd=_latest(macd_df["macd"]),
        macd_signal=_latest(macd_df["signal"]),
        macd_hist=_latest(macd_df["hist"]),
        stoch_rsi_k=_latest(srsi["k"]),
        stoch_rsi_d=_latest(srsi["d"]),
        atr=_latest(atr_s),
        bb_upper=_latest(bb["upper"]),
        bb_middle=_latest(bb["middle"]),
        bb_lower=_latest(bb["lower"]),
        bb_percent_b=_latest(bb["percent_b"]),
        adx=_latest(adx_df["adx"]),
        plus_di=_latest(adx_df["plus_di"]),
        minus_di=_latest(adx_df["minus_di"]),
        volume=_latest(volume),
        volume_sma=_latest(vol_sma_s),
        obv=_latest(obv_s),
        obv_ema=_latest(obv_ema_s),
        support=support,
        resistance=resistance,
    )

    if summary.atr is not None and price:
        summary.atr_pct = summary.atr / price * 100.0
    if summary.volume is not None and summary.volume_sma:
        summary.volume_ratio = summary.volume / summary.volume_sma

    _derive_signals(summary)
    summary.indicators = _build_breakdown(summary)
    return summary


# --------------------------------------------------------------------------- #
# Interpretation
# --------------------------------------------------------------------------- #
def _derive_signals(s: TechnicalSummary) -> None:
    """Populate the human-readable trend flags + a -1..+1 composite."""
    # RSI
    if s.rsi is None:
        s.rsi_signal = "Unknown"
    elif s.rsi >= 70:
        s.rsi_signal = "Overbought"
    elif s.rsi <= 30:
        s.rsi_signal = "Oversold"
    elif s.rsi >= 55:
        s.rsi_signal = "Bullish"
    elif s.rsi <= 45:
        s.rsi_signal = "Bearish"
    else:
        s.rsi_signal = "Neutral"

    # MACD
    if s.macd is None or s.macd_signal is None:
        s.macd_trend = "Unknown"
    elif s.macd > s.macd_signal:
        s.macd_trend = "Bullish"
    else:
        s.macd_trend = "Bearish"

    # Moving-average structure
    if s.sma_50 is not None and s.sma_200 is not None:
        if s.sma_50 > s.sma_200:
            s.ma_trend = "Golden Cross"
        elif s.sma_50 < s.sma_200:
            s.ma_trend = "Death Cross"
        else:
            s.ma_trend = "Neutral"
    else:
        s.ma_trend = "Insufficient data"

    # Lightweight -1..+1 composite (kept for the chatbot / DB; the real
    # rating comes from the scoring engine).
    parts: list[float] = []
    if s.rsi is not None:
        parts.append(np.clip((s.rsi - 50) / 30, -1, 1))
    if s.macd_trend != "Unknown":
        parts.append(1.0 if s.macd_trend == "Bullish" else -1.0)
    if s.ma_trend == "Golden Cross":
        parts.append(1.0)
    elif s.ma_trend == "Death Cross":
        parts.append(-1.0)
    s.composite_score = round(float(np.mean(parts)), 2) if parts else 0.0


def _build_breakdown(s: TechnicalSummary) -> List[Indicator]:
    """Build the per-indicator transparency rows."""
    rows: List[Indicator] = []

    rows.append(Indicator(
        "rsi", "RSI (14)", s.rsi, _fmt(s.rsi, 1), s.rsi_signal,
        {
            "Overbought": "Above 70 — stretched to the upside, pullback risk.",
            "Oversold": "Below 30 — stretched to the downside, bounce potential.",
            "Bullish": "Above 55 — momentum favours buyers.",
            "Bearish": "Below 45 — momentum favours sellers.",
            "Neutral": "Between 45 and 55 — no momentum edge.",
            "Unknown": "Not enough data.",
        }[s.rsi_signal],
    ))

    macd_note = "Not enough data."
    if s.macd is not None and s.macd_signal is not None:
        macd_note = (
            f"MACD {'above' if s.macd > s.macd_signal else 'below'} its signal line; "
            f"histogram {'positive' if (s.macd_hist or 0) > 0 else 'negative'} "
            f"({'rising' if (s.macd_hist or 0) > 0 else 'falling'} momentum)."
        )
    rows.append(Indicator(
        "macd", "MACD (12,26,9)", s.macd, _fmt(s.macd, 3), s.macd_trend, macd_note
    ))

    srsi_sig = "Unknown"
    srsi_note = "Not enough data."
    if s.stoch_rsi_k is not None:
        if s.stoch_rsi_k >= 80:
            srsi_sig, srsi_note = "Overbought", "Above 80 — momentum exhaustion risk."
        elif s.stoch_rsi_k <= 20:
            srsi_sig, srsi_note = "Oversold", "Below 20 — potential momentum turn up."
        elif s.stoch_rsi_d is not None and s.stoch_rsi_k > s.stoch_rsi_d:
            srsi_sig, srsi_note = "Bullish", "%K above %D — short-term momentum up."
        else:
            srsi_sig, srsi_note = "Bearish", "%K below %D — short-term momentum down."
    rows.append(Indicator(
        "stoch_rsi", "Stochastic RSI %K", s.stoch_rsi_k, _fmt(s.stoch_rsi_k, 1),
        srsi_sig, srsi_note
    ))

    rows.append(Indicator(
        "sma_50", "SMA 50", s.sma_50, _fmt(s.sma_50, 2),
        _above_below(s.price, s.sma_50),
        f"Price is {_above_below(s.price, s.sma_50).lower()} the 50-day average.",
    ))
    rows.append(Indicator(
        "sma_200", "SMA 200", s.sma_200, _fmt(s.sma_200, 2),
        _above_below(s.price, s.sma_200),
        f"Price is {_above_below(s.price, s.sma_200).lower()} the 200-day average "
        f"(primary trend).",
    ))
    rows.append(Indicator(
        "ema_20", "EMA 20", s.ema_20, _fmt(s.ema_20, 2),
        _above_below(s.price, s.ema_20),
        "Short-term trend reference.",
    ))
    rows.append(Indicator(
        "ema_50", "EMA 50", s.ema_50, _fmt(s.ema_50, 2),
        _cross(s.ema_20, s.ema_50, "EMA20", "EMA50"),
        "Medium-term trend reference.",
    ))
    rows.append(Indicator(
        "ema_200", "EMA 200", s.ema_200, _fmt(s.ema_200, 2),
        _above_below(s.price, s.ema_200),
        "Long-term trend reference.",
    ))

    adx_sig = "Unknown"
    adx_note = "Not enough data."
    if s.adx is not None:
        strength = "strong" if s.adx >= 25 else "weak" if s.adx < 20 else "developing"
        direction = "up" if (s.plus_di or 0) > (s.minus_di or 0) else "down"
        adx_sig = f"{strength.title()} {'Up' if direction == 'up' else 'Down'}trend"
        adx_note = (
            f"ADX {s.adx:.1f} → {strength} trend; "
            f"+DI {s.plus_di:.1f} vs -DI {s.minus_di:.1f} → trending {direction}."
        )
    rows.append(Indicator("adx", "ADX (14)", s.adx, _fmt(s.adx, 1), adx_sig, adx_note))

    bb_sig = "Unknown"
    bb_note = "Not enough data."
    if s.bb_percent_b is not None:
        if s.bb_percent_b >= 1.0:
            bb_sig, bb_note = "Above Upper", "Price above upper band — overextended."
        elif s.bb_percent_b <= 0.0:
            bb_sig, bb_note = "Below Lower", "Price below lower band — oversold."
        elif s.bb_percent_b >= 0.5:
            bb_sig, bb_note = "Upper Half", "Trading in the upper half of the band."
        else:
            bb_sig, bb_note = "Lower Half", "Trading in the lower half of the band."
    rows.append(Indicator(
        "bollinger", "Bollinger %B", s.bb_percent_b, _fmt(s.bb_percent_b, 2), bb_sig, bb_note
    ))

    atr_note = "Not enough data."
    if s.atr_pct is not None:
        level = "high" if s.atr_pct >= 4 else "low" if s.atr_pct < 1.5 else "moderate"
        atr_note = f"ATR is {s.atr_pct:.2f}% of price — {level} volatility."
    rows.append(Indicator(
        "atr", "ATR (14)", s.atr, _fmt(s.atr, 2),
        f"{(s.atr_pct or 0):.2f}% of price" if s.atr_pct is not None else "N/A", atr_note
    ))

    vol_sig = "Unknown"
    vol_note = "Not enough data."
    if s.volume_ratio is not None:
        if s.volume_ratio >= 1.5:
            vol_sig, vol_note = "Volume Spike", f"{s.volume_ratio:.1f}× the 20-day average volume."
        elif s.volume_ratio < 0.7:
            vol_sig, vol_note = "Light Volume", f"{s.volume_ratio:.1f}× average — weak participation."
        else:
            vol_sig, vol_note = "Normal", f"{s.volume_ratio:.1f}× the 20-day average volume."
    rows.append(Indicator(
        "volume", "Volume vs 20d Avg", s.volume_ratio, _fmt(s.volume_ratio, 2), vol_sig, vol_note
    ))

    obv_sig = "Unknown"
    obv_note = "Not enough data."
    if s.obv is not None and s.obv_ema is not None:
        rising = s.obv > s.obv_ema
        obv_sig = "Accumulation" if rising else "Distribution"
        obv_note = (
            f"OBV is {'above' if rising else 'below'} its 20-day EMA — "
            f"{'buyers accumulating' if rising else 'sellers distributing'}."
        )
    rows.append(Indicator("obv", "OBV Trend", s.obv, _fmt(s.obv, 0), obv_sig, obv_note))

    sr_note = "Not enough data."
    if s.support is not None and s.resistance is not None:
        sr_note = (
            f"Nearest support ≈ {s.support:,.2f}, resistance ≈ {s.resistance:,.2f} "
            f"(last {settings.sr_lookback} bars)."
        )
    rows.append(Indicator(
        "support_resistance", "Support / Resistance",
        s.support, f"{_fmt(s.support, 2)} / {_fmt(s.resistance, 2)}", "Levels", sr_note
    ))

    return rows


def _above_below(price: Optional[float], level: Optional[float]) -> str:
    if price is None or level is None:
        return "Unknown"
    return "Above" if price >= level else "Below"


def _cross(fast: Optional[float], slow: Optional[float], fast_name: str, slow_name: str) -> str:
    if fast is None or slow is None:
        return "Unknown"
    return f"{fast_name}>{slow_name}" if fast > slow else f"{fast_name}<{slow_name}"
