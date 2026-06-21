"""
tests/test_scoring.py
=====================
Audits the scoring engine end-to-end on top of the technical layer:

* a clean uptrend scores Buy/Strong Buy, a downtrend scores Sell/Strong Sell,
* rating thresholds map exactly per spec,
* weights renormalise when a category (e.g. news) is missing,
* the final score is bounded and reproducible.
"""

from __future__ import annotations

import pytest

from src.analysis.scoring import rating_for_score, score
from src.analysis.sentiment import SentimentResult
from src.analysis.technical import analyze


def _sentiment(avg: float, label: str = "Neutral") -> SentimentResult:
    return SentimentResult(
        engine="FinBERT", average_score=avg, label=label,
        positive=1, negative=0, neutral=1, details=[],
    )


def _no_news() -> SentimentResult:
    return SentimentResult("None", 0.0, "Neutral", 0, 0, 0, [])


# --------------------------------------------------------------------------- #
# Rating thresholds (exact, per spec)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("value,expected", [
    (0, "Strong Sell"), (30, "Strong Sell"),
    (31, "Sell"), (45, "Sell"),
    (46, "Hold"), (55, "Hold"),
    (56, "Buy"), (70, "Buy"),
    (71, "Strong Buy"), (100, "Strong Buy"),
])
def test_rating_thresholds(value, expected):
    assert rating_for_score(value) == expected


# --------------------------------------------------------------------------- #
# Directionality
# --------------------------------------------------------------------------- #
def test_uptrend_is_bullish(uptrend_ohlcv):
    tech = analyze(uptrend_ohlcv)
    result = score(tech, _sentiment(0.3, "Positive"))
    assert result.final_score >= 60
    assert result.rating in ("Buy", "Strong Buy")
    assert result.action == "Buy"


def test_downtrend_is_bearish(downtrend_ohlcv):
    tech = analyze(downtrend_ohlcv)
    result = score(tech, _sentiment(-0.3, "Negative"))
    assert result.final_score <= 45
    assert result.rating in ("Sell", "Strong Sell")
    assert result.action == "Sell"


def test_score_is_bounded(synthetic_ohlcv):
    tech = analyze(synthetic_ohlcv)
    result = score(tech, _sentiment(0.0))
    assert 0 <= result.final_score <= 100
    assert 0 <= result.confidence <= 100


# --------------------------------------------------------------------------- #
# Weight renormalisation when news is missing
# --------------------------------------------------------------------------- #
def test_missing_news_renormalises(uptrend_ohlcv):
    tech = analyze(uptrend_ohlcv)
    sent_cat = [c for c in score(tech, _no_news()).categories if c.name == "Sentiment"][0]
    assert not sent_cat.has_data
    # Still produces a valid, bullish score without the news category.
    result = score(tech, _no_news())
    assert result.rating in ("Buy", "Strong Buy")


def test_sentiment_moves_the_score(uptrend_ohlcv):
    tech = analyze(uptrend_ohlcv)
    bullish_news = score(tech, _sentiment(0.8, "Positive")).final_score
    bearish_news = score(tech, _sentiment(-0.8, "Negative")).final_score
    assert bullish_news > bearish_news


# --------------------------------------------------------------------------- #
# Reproducibility — the engine is deterministic.
# --------------------------------------------------------------------------- #
def test_reproducible(synthetic_ohlcv):
    tech = analyze(synthetic_ohlcv)
    a = score(tech, _sentiment(0.1))
    b = score(tech, _sentiment(0.1))
    assert a.final_score == b.final_score
    assert a.rating == b.rating


# --------------------------------------------------------------------------- #
# Transparency — every scored category exposes its sub-signals.
# --------------------------------------------------------------------------- #
def test_breakdown_is_populated(synthetic_ohlcv):
    tech = analyze(synthetic_ohlcv)
    result = score(tech, _sentiment(0.1))
    for cat in result.categories:
        if cat.has_data:
            assert cat.components, f"{cat.name} has a score but no components"
            for comp in cat.components:
                assert 0.0 <= comp.points <= 1.0
