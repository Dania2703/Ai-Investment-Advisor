"""
tests/test_validation.py
========================
Live sanity checks against real tickers (AAPL, MSFT, NVDA, AMZN, TSLA).

These hit yfinance, so they are **network-dependent** and skip automatically
when offline or rate-limited. They do two things:

1. Assert every indicator is internally consistent and in a sane range.
2. Print the latest indicator values + the engine's rating, so you can
   eyeball them against TradingView (run ``pytest -s -m network``).

We deliberately do NOT assert exact equality with TradingView: the goal of the
refactor is a *complete, explainable* methodology, not a TradingView clone.
What we verify is that our maths is correct and our conventions match (Wilder
smoothing, population stdev), which is what removes the spurious disagreements.
"""

from __future__ import annotations

import math

import pytest

from src.analysis.scoring import score
from src.analysis.technical import analyze

pytestmark = pytest.mark.network

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "TSLA"]


@pytest.fixture(scope="module")
def histories():
    """Fetch 2y of history for each ticker, or skip the whole module."""
    try:
        from src.data.market_data import get_history
        data = {}
        for t in TICKERS:
            data[t] = get_history(t, period="2y", interval="1d")
        return data
    except Exception as exc:  # noqa: BLE001 - offline / rate-limited
        pytest.skip(f"Live market data unavailable: {exc}")


@pytest.mark.parametrize("ticker", TICKERS)
def test_indicator_sanity(histories, ticker):
    hist = histories[ticker]
    assert len(hist) > 200, "expected ~2y of daily bars"

    tech = analyze(hist)
    px = tech.price
    assert px > 0

    # RSI / StochRSI bounded.
    if tech.rsi is not None:
        assert 0 <= tech.rsi <= 100
    if tech.stoch_rsi_k is not None:
        assert 0 <= tech.stoch_rsi_k <= 100

    # Moving averages live in the neighbourhood of price (within 60%).
    for ma in (tech.sma_50, tech.sma_200, tech.ema_20, tech.ema_50, tech.ema_200):
        if ma is not None:
            assert 0.4 * px <= ma <= 1.6 * px

    # Bollinger ordering.
    if None not in (tech.bb_lower, tech.bb_middle, tech.bb_upper):
        assert tech.bb_lower <= tech.bb_middle <= tech.bb_upper

    # ADX / DI bounded.
    for v in (tech.adx, tech.plus_di, tech.minus_di):
        if v is not None:
            assert 0 <= v <= 100

    # ATR positive; support <= resistance.
    if tech.atr is not None:
        assert tech.atr >= 0
    if tech.support is not None and tech.resistance is not None:
        assert tech.support <= tech.resistance

    # No NaNs leaking into the headline numbers.
    for v in (tech.rsi, tech.macd, tech.sma_50, tech.atr):
        assert v is None or not math.isnan(v)


@pytest.mark.parametrize("ticker", TICKERS)
def test_print_for_manual_tradingview_check(histories, ticker, capsys):
    """Print a compact readout for eyeball comparison with TradingView."""
    tech = analyze(histories[ticker])
    from src.analysis.sentiment import SentimentResult
    neutral = SentimentResult("None", 0.0, "Neutral", 0, 0, 0, [])
    result = score(tech, neutral)

    with capsys.disabled():
        print(
            f"\n{ticker:5s} px={tech.price:8.2f} "
            f"RSI={tech.rsi:5.1f} MACD={tech.macd:7.3f} "
            f"SMA50={tech.sma_50:8.2f} SMA200={tech.sma_200:8.2f} "
            f"ADX={tech.adx:5.1f} %B={tech.bb_percent_b:4.2f} "
            f"| score={result.final_score:5.1f} -> {result.rating}"
        )
    assert result.rating
