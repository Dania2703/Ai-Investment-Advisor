"""
src/ai/advisor.py
=================
The "brain" of the application.

Takes the structured outputs of every other module — the quote, the
technical summary and the news-sentiment result — and asks a Large Language
Model to produce a reasoned **Buy / Hold / Sell** recommendation.

Design notes
------------
* The LLM is instructed to return strict JSON, which we parse defensively.
* If no OpenAI key is configured, a transparent **rule-based engine**
  produces an equivalent recommendation from the composite technical score
  and sentiment score. This keeps the whole pipeline runnable for grading
  without any paid credentials.
* The prompt explicitly frames the output as educational, not financial
  advice.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from config import settings
from src.analysis.sentiment import SentimentResult
from src.analysis.technical import TechnicalSummary
from src.data.market_data import Quote

Action = Literal["Buy", "Hold", "Sell"]


@dataclass
class Recommendation:
    """The final recommendation surfaced to the user."""

    action: Action
    confidence: int            # 0-100
    rationale: str             # Detailed multi-sentence explanation.
    key_points: list[str]      # Bullet points behind the decision.
    engine: str                # "OpenAI (<model>)" or "Rule-based"
    tokens_used: int = 0       # Total tokens consumed by the LLM call.
    model_used: str = ""       # Exact model ID used for the LLM call.
    disclaimer: str = (
        "This is an automated, educational analysis and not financial advice. "
        "Always do your own research and consult a licensed professional before investing."
    )


SYSTEM_PROMPT = (
    "You are a disciplined equity analyst assistant. You combine quantitative "
    "technical indicators with qualitative news sentiment to produce a clear, "
    "balanced investment view for educational purposes. You never guarantee "
    "returns, you acknowledge uncertainty, and you explain your reasoning in "
    "plain language. You must respond with valid JSON only."
)


def _build_user_prompt(
    quote: Quote, tech: TechnicalSummary, sentiment: SentimentResult
) -> str:
    """Render all evidence into a compact, model-friendly prompt."""
    return f"""
Analyse the following stock and return a recommendation.

COMPANY
  Ticker:        {quote.ticker}
  Name:          {quote.name}
  Sector:        {quote.sector or 'N/A'}
  Current price: {quote.price:.2f} {quote.currency}
  Daily change:  {quote.change:+.2f} ({quote.change_pct:+.2f}%)

TECHNICAL INDICATORS
  RSI(14):           {tech.rsi}  -> {tech.rsi_signal}
  MACD:              {tech.macd} (signal {tech.macd_signal}, hist {tech.macd_hist}) -> {tech.macd_trend}
  SMA 50:            {tech.sma_50}
  SMA 200:           {tech.sma_200}
  MA relationship:   {tech.ma_trend}
  Composite score:   {tech.composite_score}  (range -1 bearish .. +1 bullish)

NEWS SENTIMENT  (engine: {sentiment.engine})
  Average score:     {sentiment.average_score}  (range -1 .. +1)
  Overall label:     {sentiment.label}
  Headline counts:   {sentiment.positive} positive / {sentiment.neutral} neutral / {sentiment.negative} negative

TASK
  Weigh the technical picture against the news sentiment. Decide on ONE action:
  "Buy", "Hold", or "Sell". Provide a confidence from 0 to 100 and a clear,
  educational rationale (4-6 sentences) plus 3-5 concise key points.

Respond with JSON exactly in this schema and nothing else:
{{
  "action": "Buy" | "Hold" | "Sell",
  "confidence": <integer 0-100>,
  "rationale": "<string>",
  "key_points": ["<string>", "..."]
}}
""".strip()


def _rule_based(
    quote: Quote, tech: TechnicalSummary, sentiment: SentimentResult
) -> Recommendation:
    """
    Deterministic fallback that mirrors the LLM's logic transparently.

    Blends the technical composite score (70%) with the sentiment score (30%)
    into a single decision value.
    """
    blended = 0.7 * tech.composite_score + 0.3 * sentiment.average_score

    if blended >= 0.25:
        action: Action = "Buy"
    elif blended <= -0.25:
        action = "Sell"
    else:
        action = "Hold"

    confidence = int(min(95, 50 + abs(blended) * 50))

    rsi_text = f"{tech.rsi:.1f}" if tech.rsi is not None else "N/A"
    key_points = [
        f"RSI(14) is {tech.rsi_signal.lower()} ({rsi_text}).",
        f"MACD momentum is {tech.macd_trend.lower()}.",
        f"Moving averages show a {tech.ma_trend.lower()}.",
        f"News sentiment is {sentiment.label.lower()} "
        f"({sentiment.positive}+/{sentiment.negative}-).",
    ]

    rationale = (
        f"The blended signal for {quote.ticker} is {blended:+.2f} on a -1..+1 scale, "
        f"combining a technical composite of {tech.composite_score:+.2f} with a news "
        f"sentiment of {sentiment.average_score:+.2f}. The {tech.ma_trend.lower()} between "
        f"the 50- and 200-day averages sets the longer-term trend, while MACD reflects "
        f"{tech.macd_trend.lower()} short-term momentum and RSI is {tech.rsi_signal.lower()}. "
        f"Taken together this supports a '{action}' stance at the current price of "
        f"{quote.price:.2f} {quote.currency}."
    )

    return Recommendation(
        action=action,
        confidence=confidence,
        rationale=rationale,
        key_points=key_points,
        engine="Rule-based",
    )


def _with_openai(
    quote: Quote, tech: TechnicalSummary, sentiment: SentimentResult
) -> Recommendation:
    """Call the OpenAI API and parse its JSON response."""
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(quote, tech, sentiment)},
        ],
    )

    usage = response.usage
    tokens = usage.total_tokens if usage else 0
    print(f"[AI AUDIT] OpenAI called. Model: {settings.llm_model}, Tokens: {tokens}")
    print(f"[AI AUDIT] Raw response: {response.choices[0].message.content[:300]}")

    content = response.choices[0].message.content or "{}"
    data = json.loads(content)

    action = data.get("action", "Hold")
    if action not in ("Buy", "Hold", "Sell"):
        action = "Hold"

    return Recommendation(
        action=action,
        confidence=int(data.get("confidence", 50)),
        rationale=data.get("rationale", "").strip(),
        key_points=list(data.get("key_points", []))[:5],
        engine=f"OpenAI ({settings.llm_model})",
        tokens_used=tokens,
        model_used=settings.llm_model,
    )


def get_recommendation(
    quote: Quote, tech: TechnicalSummary, sentiment: SentimentResult
) -> Recommendation:
    """
    Produce the final recommendation.

    Tries the OpenAI engine first (when a key is set); on any error it falls
    back to the transparent rule-based engine so the app never fails to
    return a result.
    """
    if settings.openai_enabled:
        try:
            return _with_openai(quote, tech, sentiment)
        except Exception:  # noqa: BLE001 - network / quota / parse errors.
            pass
    return _rule_based(quote, tech, sentiment)
