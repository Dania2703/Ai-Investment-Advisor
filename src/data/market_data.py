"""
src/data/market_data.py
=======================
Fetches real-time and historical stock market data from Yahoo Finance
through the `yfinance` library.

`yfinance` requires no API key, which keeps the project free to run and
easy to deploy. The functions here return clean pandas DataFrames / dicts
that the rest of the pipeline consumes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd
import yfinance as yf


@dataclass
class Quote:
    """A lightweight snapshot of a ticker's current state."""

    ticker: str
    name: str
    currency: str
    price: float
    previous_close: float
    change: float
    change_pct: float
    market_cap: Optional[float]
    sector: Optional[str]
    as_of: datetime

    @property
    def is_up(self) -> bool:
        return self.change >= 0


class MarketDataError(Exception):
    """Raised when market data cannot be retrieved for a ticker."""


def _safe_float(value) -> Optional[float]:
    """Convert a possibly-missing numeric field to float or None."""
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def get_history(
    ticker: str,
    period: str = "1y",
    interval: str = "1d",
) -> pd.DataFrame:
    """
    Return historical OHLCV data for *ticker*.

    Parameters
    ----------
    ticker : str
        Stock symbol, e.g. "AAPL".
    period : str
        Look-back window accepted by yfinance ("1mo", "6mo", "1y", "5y", ...).
    interval : str
        Candle size ("1d", "1wk", "1mo", ...).

    Raises
    ------
    MarketDataError
        If no data is returned (invalid ticker or network issue).
    """
    ticker = ticker.strip().upper()
    if not ticker:
        raise MarketDataError("Ticker symbol is empty.")

    data = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
    if data.empty:
        raise MarketDataError(
            f"No market data found for '{ticker}'. Check the symbol and try again."
        )

    data.index = pd.to_datetime(data.index)
    return data


def get_quote(ticker: str) -> Quote:
    """
    Return a current Quote snapshot for *ticker*.

    Uses the fast `fast_info` endpoint where possible and falls back to the
    last two closes from history to compute the daily change.
    """
    ticker = ticker.strip().upper()
    yf_ticker = yf.Ticker(ticker)

    # `fast_info` is quicker than the full `.info` payload, but its properties
    # can internally trigger fetches that raise JSONDecodeError or KeyError.
    price = prev_close = None
    currency = "USD"
    try:
        fast = yf_ticker.fast_info
        price = _safe_float(fast.last_price)
        prev_close = _safe_float(fast.previous_close)
        currency = fast.currency or "USD"
    except Exception:
        pass

    # Fall back to recent history if fast_info is unavailable.
    if price is None or prev_close is None:
        hist = get_history(ticker, period="5d", interval="1d")
        closes = hist["Close"].dropna()
        if len(closes) < 1:
            raise MarketDataError(f"Could not determine a price for '{ticker}'.")
        price = float(closes.iloc[-1])
        prev_close = float(closes.iloc[-2]) if len(closes) >= 2 else price

    # The full `.info` dict gives us name / sector / market cap (best effort).
    try:
        info = yf_ticker.info or {}
    except Exception:  # noqa: BLE001 - yfinance occasionally throws here.
        info = {}

    name = info.get("shortName") or info.get("longName") or ticker
    sector = info.get("sector")
    market_cap = _safe_float(info.get("marketCap"))

    change = (price - prev_close) if prev_close else 0.0
    change_pct = (change / prev_close * 100.0) if prev_close else 0.0

    return Quote(
        ticker=ticker,
        name=name,
        currency=currency,
        price=price,
        previous_close=prev_close,
        change=change,
        change_pct=change_pct,
        market_cap=market_cap,
        sector=sector,
        as_of=datetime.utcnow(),
    )
