"""
src/ai/advisor.py
=================
Produces the final recommendation surfaced to the user.

Division of responsibility (this is the key design change)
----------------------------------------------------------
* :mod:`src.analysis.scoring` **decides** the rating from a transparent,
  weighted 0-100 score. This is deterministic and reproducible.
* The LLM (OpenAI GPT-4.1) **explains** that result in natural language:
  it summarises the technical signals, the news sentiment, and the risks —
  but it must keep the rating the engine produced. It never overrides the
  numbers.

If OpenAI is unavailable, a rule-based narrator builds the same explanation
fields directly from the score breakdown, so the app degrades gracefully.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal, Optional

from config import settings
from src.analysis.scoring import ScoreResult, score as run_scoring
from src.analysis.sentiment import SentimentResult
from src.analysis.technical import TechnicalSummary
from src.data.market_data import Quote

Action = Literal["Buy", "Hold", "Sell"]


@dataclass
class Recommendation:
    """The final recommendation surfaced to the user."""

    # ---- Decided by the scoring engine ----------------------------------
    rating: str                       # "Strong Buy" ... "Strong Sell"
    action: Action                    # collapsed Buy / Hold / Sell
    final_score: float                # 0-100
    confidence: int                   # 0-100
    score_result: Optional[ScoreResult] = None

    # ---- Narrated (by GPT or the rule-based fallback) --------------------
    rationale: str = ""
    technical_analysis: str = ""
    sentiment_analysis: str = ""
    risks: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    key_points: list[str] = field(default_factory=list)

    # ---- Structured, product-facing narrative (the spec's required shape) -
    executive_summary: str = ""        # concise overview, shown first
    bullish_factors: list[str] = field(default_factory=list)
    bearish_factors: list[str] = field(default_factory=list)
    risk_assessment: str = ""
    short_term_outlook: str = ""
    long_term_outlook: str = ""

    # ---- Provenance ------------------------------------------------------
    engine: str = ""
    tokens_used: int = 0
    model_used: str = ""
    disclaimer: str = (
        "This is an automated, educational analysis and not financial advice. "
        "Always do your own research and consult a licensed professional before investing."
    )


SYSTEM_PROMPT = (
    "You are a professional equity research analyst writing an educational brief. "
    "A deterministic quantitative engine has ALREADY decided the rating and score. "
    "Your job is to EXPLAIN that decision in clear, balanced language — never to "
    "change it. Summarise the technical signals, the news sentiment, and the key "
    "risks. Acknowledge uncertainty and never guarantee returns. "
    "Respond with valid JSON only."
)


def _format_headlines(articles) -> str:
    if not articles:
        return "  (no recent headlines available)"
    return "\n".join(f"  - {a.title}" for a in articles[:8])


def _format_breakdown(result: ScoreResult) -> str:
    lines = []
    for c in result.categories:
        if not c.has_data:
            lines.append(f"  {c.name} (weight {c.weight:.0%}): no data")
            continue
        lines.append(f"  {c.name} (weight {c.weight:.0%}): {c.score:.0f}/100")
        for comp in c.components:
            lines.append(f"      - {comp.name}: {comp.detail}")
    return "\n".join(lines)


def _build_user_prompt(
    quote: Quote,
    tech: TechnicalSummary,
    sentiment: SentimentResult,
    result: ScoreResult,
    articles=None,
) -> str:
    """Build the explanation prompt. The decision is given, not requested."""
    headlines = _format_headlines(articles)
    breakdown = _format_breakdown(result)
    return f"""A quantitative scoring engine has analysed {quote.ticker} and produced
this decision. Explain it for an educated retail investor.

DECISION (do not change these):
  Rating:       {result.rating}
  Final score:  {result.final_score:.1f} / 100
  Confidence:   {result.confidence}%

Company:
  Ticker: {quote.ticker}   Name: {quote.name}   Sector: {quote.sector or 'N/A'}
  Price: {quote.price:.2f} {quote.currency} ({quote.change:+.2f}, {quote.change_pct:+.2f}%)

Key technical readings:
  RSI(14): {_n(tech.rsi, 1)} ({tech.rsi_signal})   MACD: {_n(tech.macd, 3)} ({tech.macd_trend})
  StochRSI %K/%D: {_n(tech.stoch_rsi_k, 0)}/{_n(tech.stoch_rsi_d, 0)}
  SMA50: {_n(tech.sma_50, 2)}   SMA200: {_n(tech.sma_200, 2)}   MA trend: {tech.ma_trend}
  EMA20/50/200: {_n(tech.ema_20, 2)}/{_n(tech.ema_50, 2)}/{_n(tech.ema_200, 2)}
  ADX: {_n(tech.adx, 1)} (+DI {_n(tech.plus_di, 1)} / -DI {_n(tech.minus_di, 1)})
  Bollinger %B: {_n(tech.bb_percent_b, 2)}   ATR%: {_n(tech.atr_pct, 2)}
  OBV trend vs EMA: {'rising' if (tech.obv or 0) > (tech.obv_ema or 0) else 'falling'}
  Volume vs 20d avg: {_n(tech.volume_ratio, 2)}x
  Support/Resistance: {_n(tech.support, 2)} / {_n(tech.resistance, 2)}

News sentiment ({sentiment.engine}): {sentiment.label} ({sentiment.average_score:+.3f}),
  {sentiment.positive} positive / {sentiment.neutral} neutral / {sentiment.negative} negative.

Score breakdown:
{breakdown}

Recent headlines:
{headlines}

Write JSON only, in this exact shape (keep "rating" identical to the decision).
Every statement MUST be grounded in the numbers above — never invent values,
price targets, or facts not derivable from the data. If something is unknown,
say so plainly.

{{
  "rating": "{result.rating}",
  "executive_summary": "<3-4 sentence investment overview a busy investor reads first; states the rating, the dominant driver, and the single biggest caveat>",
  "technical_analysis": "<2-4 sentences explaining the trend, momentum and volume signals>",
  "sentiment_analysis": "<1-3 sentences on the news sentiment>",
  "bullish_factors": ["<concrete, data-grounded bullish factor>", "..."],
  "bearish_factors": ["<concrete, data-grounded bearish factor>", "..."],
  "risk_assessment": "<2-3 sentences on the key risks: volatility, trend fragility, sentiment, concentration>",
  "short_term_outlook": "<1-2 sentences: days-to-weeks view grounded in momentum/volatility readings>",
  "long_term_outlook": "<1-2 sentences: months view grounded in the primary trend (SMA200) and structure>",
  "summary": "<2-3 sentence plain-language summary that justifies the {result.rating} rating>"
}}"""


def _n(value, digits: int) -> str:
    return f"{value:,.{digits}f}" if value is not None else "N/A"


# --------------------------------------------------------------------------- #
# Rule-based narrator (fallback when OpenAI is unavailable)
# --------------------------------------------------------------------------- #
def _rule_based_narrative(
    quote: Quote,
    tech: TechnicalSummary,
    sentiment: SentimentResult,
    result: ScoreResult,
) -> Recommendation:
    cats = {c.name: c for c in result.categories}

    def cat_line(name: str) -> str:
        c = cats.get(name)
        if not c or not c.has_data:
            return f"{name}: no data."
        return f"{name} {c.score:.0f}/100 — " + "; ".join(x.detail for x in c.components)

    technical_analysis = " ".join(
        cat_line(n) for n in ("Trend", "Momentum", "Volume", "Volatility")
    )
    sentiment_analysis = (
        f"News sentiment is {sentiment.label.lower()} ({sentiment.average_score:+.3f}) "
        f"across {sentiment.positive + sentiment.neutral + sentiment.negative} headlines "
        f"via {sentiment.engine}."
    )

    risks, opportunities = [], []
    for c in result.categories:
        for comp in c.components:
            if comp.points <= 0.35:
                risks.append(f"{comp.name}: {comp.detail}")
            elif comp.points >= 0.75:
                opportunities.append(f"{comp.name}: {comp.detail}")

    summary = (
        f"{quote.ticker} scores {result.final_score:.0f}/100 → "
        f"'{result.rating}' ({result.confidence}% confidence). "
        f"The rating is driven by the weighted blend of trend, momentum, volume, "
        f"volatility and news sentiment."
    )

    # ---- Structured, product-facing fields (deterministic) --------------
    trend_word = {
        "Golden Cross": "a bullish long-term structure (SMA50 above SMA200)",
        "Death Cross": "a bearish long-term structure (SMA50 below SMA200)",
    }.get(tech.ma_trend, "a mixed moving-average structure")
    executive_summary = (
        f"{quote.name} ({quote.ticker}) rates **{result.rating}** with a quantitative "
        f"score of {result.final_score:.0f}/100 and {result.confidence}% confidence. "
        f"Price is {quote.price:,.2f} {quote.currency} ({quote.change_pct:+.2f}% today), "
        f"trading with {trend_word}. "
        f"Momentum reads {tech.rsi_signal.lower()} (RSI {_n(tech.rsi, 0)}) and MACD is "
        f"{tech.macd_trend.lower()}; news sentiment is {sentiment.label.lower()}."
    )

    risk_assessment = (
        f"Volatility (ATR) is {_n(tech.atr_pct, 1)}% of price and ADX is {_n(tech.adx, 0)} "
        f"({'a confirmed' if (tech.adx or 0) >= 25 else 'a weak/unconfirmed'} trend). "
        f"Key risks: a trend reversal if price loses the SMA200 at {_n(tech.sma_200, 2)}, "
        f"momentum exhaustion, and headline/sentiment shocks. Position sizing should "
        f"reflect the {_n(tech.atr_pct, 1)}% daily range."
    )

    short_term_outlook = (
        f"Near term (days–weeks): momentum is {tech.rsi_signal.lower()} and MACD "
        f"{tech.macd_trend.lower()}; watch resistance near {_n(tech.resistance, 2)} and "
        f"support near {_n(tech.support, 2)}."
    )
    long_term_outlook = (
        f"Longer term (months): the primary trend is defined by the 200-day average "
        f"({_n(tech.sma_200, 2)}) — price is currently "
        f"{'above' if (tech.sma_200 and quote.price >= tech.sma_200) else 'below'} it, "
        f"implying a {'constructive' if (tech.sma_200 and quote.price >= tech.sma_200) else 'cautious'} "
        f"long-term posture."
    )

    return Recommendation(
        rating=result.rating,
        action=result.action,
        final_score=result.final_score,
        confidence=result.confidence,
        score_result=result,
        rationale=summary,
        technical_analysis=technical_analysis,
        sentiment_analysis=sentiment_analysis,
        risks=risks[:6],
        opportunities=opportunities[:6],
        executive_summary=executive_summary,
        bullish_factors=opportunities[:6],
        bearish_factors=risks[:6],
        risk_assessment=risk_assessment,
        short_term_outlook=short_term_outlook,
        long_term_outlook=long_term_outlook,
        key_points=[technical_analysis, sentiment_analysis],
        engine="Rule-based narrator (deterministic scoring engine)",
    )


# --------------------------------------------------------------------------- #
# OpenAI narrator
# --------------------------------------------------------------------------- #
def _with_openai(
    quote: Quote,
    tech: TechnicalSummary,
    sentiment: SentimentResult,
    result: ScoreResult,
    articles=None,
) -> Recommendation:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(quote, tech, sentiment, result, articles)},
        ],
    )

    usage = response.usage
    tokens = usage.total_tokens if usage else 0
    print(f"[AI AUDIT] OpenAI narration. Model: {settings.llm_model}, Tokens: {tokens}")

    data = json.loads(response.choices[0].message.content or "{}")

    return Recommendation(
        # Rating/score/action ALWAYS come from the engine, never the LLM.
        rating=result.rating,
        action=result.action,
        final_score=result.final_score,
        confidence=result.confidence,
        score_result=result,
        rationale=str(data.get("summary", "")).strip(),
        technical_analysis=str(data.get("technical_analysis", "")).strip(),
        sentiment_analysis=str(data.get("sentiment_analysis", "")).strip(),
        # Accept either the new "bullish/bearish_factors" or the legacy keys.
        risks=list(data.get("bearish_factors") or data.get("risks") or []),
        opportunities=list(data.get("bullish_factors") or data.get("opportunities") or []),
        executive_summary=str(data.get("executive_summary", "")).strip(),
        bullish_factors=list(data.get("bullish_factors") or data.get("opportunities") or []),
        bearish_factors=list(data.get("bearish_factors") or data.get("risks") or []),
        risk_assessment=str(data.get("risk_assessment", "")).strip(),
        short_term_outlook=str(data.get("short_term_outlook", "")).strip(),
        long_term_outlook=str(data.get("long_term_outlook", "")).strip(),
        key_points=[
            str(data.get("technical_analysis", "")),
            str(data.get("sentiment_analysis", "")),
        ],
        engine=f"OpenAI narration ({settings.llm_model}) · scoring engine decision",
        tokens_used=tokens,
        model_used=settings.llm_model,
    )


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def get_recommendation(
    quote: Quote,
    tech: TechnicalSummary,
    sentiment: SentimentResult,
    articles=None,
) -> Recommendation:
    """
    Score the stock deterministically, then narrate the result.

    Tries OpenAI for the narrative; falls back to the deterministic narrator.
    The rating itself is identical either way.
    """
    result = run_scoring(tech, sentiment)

    if settings.openai_enabled:
        try:
            return _with_openai(quote, tech, sentiment, result, articles)
        except Exception as exc:  # noqa: BLE001
            print(f"[AI AUDIT] OpenAI failed, using rule-based narrator: {exc}")

    return _rule_based_narrative(quote, tech, sentiment, result)
