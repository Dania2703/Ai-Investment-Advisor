"""
src/analysis/scoring.py
=======================
The recommendation engine.

This module — *not* the LLM — decides Buy / Hold / Sell. It converts the
:class:`~src.analysis.technical.TechnicalSummary` and the news
:class:`~src.analysis.sentiment.SentimentResult` into a single, explainable
**0-100 score** and a rating.

Methodology
-----------
Five weighted categories, each scored 0-100 from a set of yes/no or graded
sub-signals, then blended:

============  ======  ============================================
Category      Weight  Drivers
============  ======  ============================================
Trend          40%    Price vs SMA200/SMA50, SMA50 vs SMA200,
                      EMA20/50/200 stack, ADX trend confirmation
Momentum       25%    RSI, MACD, Stochastic RSI
Volume         15%    OBV trend, volume spike confirmation
Volatility     10%    ATR%, Bollinger %B position
Sentiment      10%    FinBERT / VADER news sentiment
============  ======  ============================================

Each sub-signal contributes a *bullishness* in ``[0, 1]`` (0 = bearish,
0.5 = neutral, 1 = bullish). A category score is the mean of its sub-signals
× 100. The final score is the weighted average of the category scores, with
weights **renormalised** over whichever categories have enough data — so a
missing news feed or an under-warmed indicator never silently drags the score
to the middle.

Rating thresholds (per spec)::

     0-30  Strong Sell
    31-45  Sell
    46-55  Hold
    56-70  Buy
    71-100 Strong Buy
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from config import settings
from src.analysis.sentiment import SentimentResult
from src.analysis.technical import TechnicalSummary


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #
@dataclass
class Component:
    """A single sub-signal inside a category."""

    name: str
    detail: str
    points: float  # bullishness in [0, 1]


@dataclass
class CategoryScore:
    """One scored category (e.g. Trend) with its sub-signal breakdown."""

    name: str
    weight: float                 # nominal weight (before renormalisation)
    score: Optional[float]        # 0-100, or None if no data
    components: List[Component] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return self.score is not None


@dataclass
class ScoreResult:
    """The final, explainable recommendation."""

    final_score: float            # 0-100
    rating: str                   # "Strong Buy" ... "Strong Sell"
    confidence: int               # 0-100
    categories: List[CategoryScore]

    @property
    def action(self) -> str:
        """Collapse the 5-way rating onto the legacy Buy/Hold/Sell axis."""
        if self.rating in ("Strong Buy", "Buy"):
            return "Buy"
        if self.rating in ("Strong Sell", "Sell"):
            return "Sell"
        return "Hold"

    def breakdown_dict(self) -> dict:
        return {
            "final_score": round(self.final_score, 1),
            "rating": self.rating,
            "confidence": self.confidence,
            "categories": {
                c.name: {
                    "score": round(c.score, 1) if c.score is not None else None,
                    "weight": c.weight,
                    "components": [
                        {"name": x.name, "detail": x.detail, "points": round(x.points, 2)}
                        for x in c.components
                    ],
                }
                for c in self.categories
            },
        }


# --------------------------------------------------------------------------- #
# Scoring helpers
# --------------------------------------------------------------------------- #
def _flag(condition: Optional[bool]) -> Optional[float]:
    """1.0 for True, 0.0 for False, None for unknown."""
    if condition is None:
        return None
    return 1.0 if condition else 0.0


def _mean_component_score(components: List[Component]) -> Optional[float]:
    if not components:
        return None
    return sum(c.points for c in components) / len(components) * 100.0


# --------------------------------------------------------------------------- #
# Category scorers
# --------------------------------------------------------------------------- #
def _score_trend(t: TechnicalSummary) -> CategoryScore:
    comps: List[Component] = []
    p = t.price

    def add(name: str, cond: Optional[bool], detail_true: str, detail_false: str):
        pts = _flag(cond)
        if pts is None:
            return
        comps.append(Component(name, detail_true if cond else detail_false, pts))

    add("Price > SMA200",
        (p > t.sma_200) if t.sma_200 is not None else None,
        "Price above the 200-day SMA — primary trend up.",
        "Price below the 200-day SMA — primary trend down.")
    add("Price > SMA50",
        (p > t.sma_50) if t.sma_50 is not None else None,
        "Price above the 50-day SMA.",
        "Price below the 50-day SMA.")
    add("SMA50 > SMA200",
        (t.sma_50 > t.sma_200) if (t.sma_50 is not None and t.sma_200 is not None) else None,
        "Golden-cross structure (SMA50 above SMA200).",
        "Death-cross structure (SMA50 below SMA200).")
    add("EMA20 > EMA50",
        (t.ema_20 > t.ema_50) if (t.ema_20 is not None and t.ema_50 is not None) else None,
        "Short-term EMA above medium-term EMA.",
        "Short-term EMA below medium-term EMA.")
    add("EMA50 > EMA200",
        (t.ema_50 > t.ema_200) if (t.ema_50 is not None and t.ema_200 is not None) else None,
        "Medium-term EMA above long-term EMA.",
        "Medium-term EMA below long-term EMA.")
    add("Price > EMA20",
        (p > t.ema_20) if t.ema_20 is not None else None,
        "Price above the 20-day EMA — short-term up.",
        "Price below the 20-day EMA — short-term down.")

    # ADX confirms how *strong* and which direction the trend is.
    if t.adx is not None and t.plus_di is not None and t.minus_di is not None:
        if t.adx < 20:
            pts, detail = 0.5, f"ADX {t.adx:.0f}: trend too weak to confirm direction."
        else:
            up = t.plus_di > t.minus_di
            strong = t.adx >= 25
            pts = (1.0 if up else 0.0) if strong else (0.65 if up else 0.35)
            detail = (
                f"ADX {t.adx:.0f}: {'strong' if strong else 'developing'} "
                f"{'up' if up else 'down'}trend (+DI {t.plus_di:.0f} / -DI {t.minus_di:.0f})."
            )
        comps.append(Component("ADX trend confirmation", detail, pts))

    return CategoryScore("Trend", settings.weight_trend, _mean_component_score(comps), comps)


def _score_momentum(t: TechnicalSummary) -> CategoryScore:
    comps: List[Component] = []

    # RSI — favour strong-but-not-exhausted readings.
    if t.rsi is not None:
        r = t.rsi
        if r >= 70:
            pts, detail = 0.55, f"RSI {r:.0f}: strong but overbought — pullback risk."
        elif r >= 60:
            pts, detail = 1.0, f"RSI {r:.0f}: healthy bullish momentum."
        elif r >= 50:
            pts, detail = 0.75, f"RSI {r:.0f}: mildly bullish."
        elif r >= 45:
            pts, detail = 0.45, f"RSI {r:.0f}: mildly bearish."
        elif r > 30:
            pts, detail = 0.25, f"RSI {r:.0f}: bearish momentum."
        else:
            pts, detail = 0.40, f"RSI {r:.0f}: oversold — mean-reversion bounce possible."
        comps.append(Component("RSI", detail, pts))

    # MACD — line vs signal and histogram sign.
    if t.macd is not None and t.macd_signal is not None:
        above = t.macd > t.macd_signal
        hist_pos = (t.macd_hist or 0) > 0
        positive = t.macd > 0
        if above and hist_pos:
            pts = 1.0
        elif above:
            pts = 0.7
        elif not above and not hist_pos:
            pts = 0.0
        else:
            pts = 0.3
        if positive:
            pts = min(1.0, pts + 0.05)
        detail = (
            f"MACD {'>' if above else '<'} signal, histogram "
            f"{'positive' if hist_pos else 'negative'}, MACD "
            f"{'>' if positive else '<'} 0."
        )
        comps.append(Component("MACD", detail, pts))

    # Stochastic RSI
    if t.stoch_rsi_k is not None:
        k = t.stoch_rsi_k
        d = t.stoch_rsi_d
        if k >= 80:
            pts, detail = 0.55, f"StochRSI %K {k:.0f}: overbought."
        elif k <= 20:
            pts, detail = 0.45, f"StochRSI %K {k:.0f}: oversold — possible upturn."
        elif d is not None and k > d:
            pts, detail = 0.75, f"StochRSI %K {k:.0f} > %D {d:.0f}: momentum turning up."
        else:
            pts, detail = 0.30, f"StochRSI %K {k:.0f}: momentum soft."
        comps.append(Component("Stochastic RSI", detail, pts))

    return CategoryScore("Momentum", settings.weight_momentum, _mean_component_score(comps), comps)


def _score_volume(t: TechnicalSummary) -> CategoryScore:
    comps: List[Component] = []

    # OBV trend: accumulation vs distribution.
    if t.obv is not None and t.obv_ema is not None:
        rising = t.obv > t.obv_ema
        comps.append(Component(
            "OBV trend",
            "OBV above its EMA — accumulation." if rising else "OBV below its EMA — distribution.",
            1.0 if rising else 0.0,
        ))

    # Volume spike confirmation — a spike only counts in the trend's direction.
    if t.volume_ratio is not None:
        ratio = t.volume_ratio
        obv_up = (t.obv is not None and t.obv_ema is not None and t.obv > t.obv_ema)
        if ratio >= 1.5:
            pts = 1.0 if obv_up else 0.0
            detail = (
                f"Volume {ratio:.1f}× average confirming "
                f"{'accumulation' if obv_up else 'distribution'}."
            )
        elif ratio < 0.7:
            pts, detail = 0.5, f"Volume {ratio:.1f}× average — low conviction, neutral."
        else:
            pts = 0.6 if obv_up else 0.4
            detail = f"Volume {ratio:.1f}× average — normal participation."
        comps.append(Component("Volume confirmation", detail, pts))

    return CategoryScore("Volume", settings.weight_volume, _mean_component_score(comps), comps)


def _score_volatility(t: TechnicalSummary) -> CategoryScore:
    comps: List[Component] = []

    # Bollinger %B — healthy trends ride the upper half without going parabolic.
    if t.bb_percent_b is not None:
        b = t.bb_percent_b
        if b >= 1.0:
            pts, detail = 0.40, "Price above the upper band — overextended, reversion risk."
        elif b >= 0.8:
            pts, detail = 0.80, "Upper band region — strong but stretched."
        elif b >= 0.5:
            pts, detail = 1.0, "Upper half of the band — constructive."
        elif b >= 0.2:
            pts, detail = 0.45, "Lower half of the band — soft."
        elif b >= 0.0:
            pts, detail = 0.40, "Near the lower band — weak."
        else:
            pts, detail = 0.50, "Below the lower band — oversold, possible bounce."
        comps.append(Component("Bollinger %B", detail, pts))

    # ATR% — lower, orderly volatility makes a trend more reliable.
    if t.atr_pct is not None:
        a = t.atr_pct
        if a < 1.5:
            pts, detail = 1.0, f"ATR {a:.1f}% of price — calm, orderly."
        elif a < 3:
            pts, detail = 0.7, f"ATR {a:.1f}% of price — moderate volatility."
        elif a < 5:
            pts, detail = 0.45, f"ATR {a:.1f}% of price — elevated volatility."
        else:
            pts, detail = 0.3, f"ATR {a:.1f}% of price — high volatility / risk."
        comps.append(Component("ATR (volatility)", detail, pts))

    return CategoryScore("Volatility", settings.weight_volatility, _mean_component_score(comps), comps)


def _score_sentiment(s: SentimentResult) -> CategoryScore:
    comps: List[Component] = []
    if s is not None and s.engine != "None":
        # Map [-1, +1] onto [0, 1].
        pts = max(0.0, min(1.0, (s.average_score + 1) / 2))
        comps.append(Component(
            "News sentiment",
            f"{s.engine}: {s.label.lower()} ({s.average_score:+.2f}); "
            f"{s.positive} positive / {s.neutral} neutral / {s.negative} negative.",
            pts,
        ))
    return CategoryScore("Sentiment", settings.weight_sentiment, _mean_component_score(comps), comps)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def rating_for_score(score: float) -> str:
    """Map a 0-100 score onto the 5-way rating."""
    if score <= 30:
        return "Strong Sell"
    if score <= 45:
        return "Sell"
    if score <= 55:
        return "Hold"
    if score <= 70:
        return "Buy"
    return "Strong Buy"


def score(tech: TechnicalSummary, sentiment: SentimentResult) -> ScoreResult:
    """
    Produce the final 0-100 score and rating from technicals + sentiment.

    Weights are renormalised over the categories that actually have data, so
    the result is well-defined even with a missing news feed or a short price
    history.
    """
    categories = [
        _score_trend(tech),
        _score_momentum(tech),
        _score_volume(tech),
        _score_volatility(tech),
        _score_sentiment(sentiment),
    ]

    usable = [c for c in categories if c.has_data]
    total_weight = sum(c.weight for c in usable)
    if total_weight == 0:
        final = 50.0
    else:
        final = sum(c.score * c.weight for c in usable) / total_weight

    final = max(0.0, min(100.0, final))
    rating = rating_for_score(final)

    # Confidence: distance from neutral (50) + agreement between categories.
    distance = abs(final - 50) / 50  # 0..1
    if len(usable) > 1:
        spread = (max(c.score for c in usable) - min(c.score for c in usable)) / 100
        agreement = 1 - spread
    else:
        agreement = 0.5
    confidence = int(round(min(95, max(35, 45 + distance * 40 + agreement * 15))))

    return ScoreResult(
        final_score=round(final, 1),
        rating=rating,
        confidence=confidence,
        categories=categories,
    )
