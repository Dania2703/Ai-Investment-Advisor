"""
app.py
======
AI Investment Advisor — Streamlit front-end and pipeline orchestrator.

Flow
----
1. User enters a ticker symbol.
2. We pull a live quote + 1y history from Yahoo Finance.
3. We pull recent news from NewsAPI.
4. An AI model scores the news sentiment.
5. We compute the technical indicators (RSI, MACD, SMA50, SMA200).
6. An LLM combines everything into a Buy / Hold / Sell recommendation.
7. We render price, chart, news, sentiment, indicators and the AI verdict.

Run locally:
    streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config import settings
from src.ai.advisor import (
    get_recommendation,
    _build_user_prompt,
    _rule_based,
    _with_openai,
)
from src.ai.chatbot import build_context, chat as gemini_chat
from src.analysis.sentiment import score_articles
from src.analysis.technical import analyze
from src.data.market_data import MarketDataError, get_history, get_quote
from src.data.news_data import get_news
from src.ui.components import ACTION_COLORS, build_price_chart

# --------------------------------------------------------------------------- #
# Page configuration
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="AI Investment Advisor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------------------------------- #
# Cached data loaders (Streamlit caches results for `cache_ttl_seconds`)
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=settings.cache_ttl_seconds, show_spinner=False)
def load_quote(ticker: str):
    return get_quote(ticker)


@st.cache_data(ttl=settings.cache_ttl_seconds, show_spinner=False)
def load_history(ticker: str):
    return get_history(ticker, period=settings.default_period,
                       interval=settings.default_interval)


@st.cache_data(ttl=settings.cache_ttl_seconds, show_spinner=False)
def load_news(query: str):
    return get_news(query)


# Sentiment scoring is cached on the article texts so we don't re-run the
# transformer on every UI interaction.
@st.cache_data(ttl=settings.cache_ttl_seconds, show_spinner=False)
def load_sentiment(_articles):
    return score_articles(_articles)


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
def render_sidebar() -> str:
    """Render the input sidebar and return the chosen ticker."""
    with st.sidebar:
        st.title("📈 AI Investment Advisor")
        st.caption("AI & Innovation in Capital Markets — Track 3")

        ticker = st.text_input("Stock ticker", value="AAPL", help="e.g. AAPL, MSFT, TSLA, NVDA").upper().strip()
        analyze_clicked = st.button("Analyze", type="primary", use_container_width=True)

        st.divider()
        st.subheader("Status")
        st.write("🟢 OpenAI key" if settings.openai_enabled else "⚪ OpenAI key (using rule-based fallback)")
        st.write("🟢 NewsAPI key" if settings.news_enabled else "⚪ NewsAPI key (news disabled)")
        if settings.groq_enabled:
            st.write("🟢 Chatbot (Groq)")
        elif settings.gemini_enabled:
            st.write("🟢 Chatbot (Gemini)")
        else:
            st.write("⚪ Chatbot (no key configured)")

        st.divider()
        st.caption(
            "Educational tool — not financial advice. "
            "Data: Yahoo Finance & NewsAPI."
        )

    # Persist the "analyze" action across reruns.
    if analyze_clicked:
        st.session_state["run"] = True
        st.session_state["ticker"] = ticker
    return st.session_state.get("ticker", ticker)


# --------------------------------------------------------------------------- #
# Section renderers
# --------------------------------------------------------------------------- #
def render_header(quote) -> None:
    """Top metrics: price, daily change, market cap, sector."""
    st.subheader(f"{quote.name}  ({quote.ticker})")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current price", f"{quote.price:,.2f} {quote.currency}",
              f"{quote.change:+.2f} ({quote.change_pct:+.2f}%)")
    c2.metric("Previous close", f"{quote.previous_close:,.2f}")
    cap = f"{quote.market_cap/1e9:,.1f} B" if quote.market_cap else "N/A"
    c3.metric("Market cap", cap)
    c4.metric("Sector", quote.sector or "N/A")


def render_recommendation(rec, prompt_text: str | None = None) -> None:
    """The headline AI verdict with confidence and rationale."""
    color = ACTION_COLORS.get(rec.action, "#1A2A4F")
    token_info = f" · Tokens: {rec.tokens_used}" if rec.tokens_used else ""
    model_info = f" · Model: {rec.model_used}" if rec.model_used else ""
    st.markdown(
        f"""
        <div style="border-radius:14px;padding:20px;background:{color}15;
                    border:2px solid {color};">
          <div style="display:flex;align-items:center;gap:16px;">
            <span style="font-size:34px;font-weight:800;color:{color};">{rec.action.upper()}</span>
            <span style="font-size:16px;color:#444;">Confidence: <b>{rec.confidence}%</b></span>
            <span style="margin-left:auto;font-size:12px;color:#777;">Engine: {rec.engine}{model_info}{token_info}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown("**Rationale**")
    st.write(rec.rationale)
    if rec.key_points:
        st.markdown("**Key points**")
        for point in rec.key_points:
            st.markdown(f"- {point}")
    st.caption(rec.disclaimer)
    if prompt_text:
        with st.expander("View LLM prompt sent to OpenAI"):
            st.code(prompt_text, language="text")


def render_indicators(tech) -> None:
    """Technical indicators as metrics + a tidy table."""
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("RSI (14)", f"{tech.rsi:.1f}" if tech.rsi is not None else "N/A", tech.rsi_signal)
    c2.metric("MACD", f"{tech.macd:.3f}" if tech.macd is not None else "N/A", tech.macd_trend)
    c3.metric("SMA 50", f"{tech.sma_50:,.2f}" if tech.sma_50 is not None else "N/A")
    c4.metric("SMA 200", f"{tech.sma_200:,.2f}" if tech.sma_200 is not None else "N/A")
    st.caption(f"Long-term trend: **{tech.ma_trend}**  ·  Composite score: **{tech.composite_score:+.2f}** (-1..+1)")


def render_sentiment(sent) -> None:
    """Sentiment gauge-style summary."""
    c1, c2, c3 = st.columns(3)
    c1.metric("Sentiment", sent.label, f"{sent.average_score:+.2f}")
    c2.metric("Score (0-100)", f"{sent.percent}")
    c3.metric("Engine", sent.engine)
    st.progress(sent.percent / 100)
    st.caption(f"Headlines — 🟢 {sent.positive} positive · ⚪ {sent.neutral} neutral · 🔴 {sent.negative} negative")


def render_news(articles, sentiment=None) -> None:
    """Recent headlines list with optional per-article FinBERT scores."""
    if not articles:
        st.info("No recent news available (NewsAPI key not configured or no results).")
        return
    score_map = {}
    if sentiment and sentiment.details:
        for d in sentiment.details:
            score_map[d.title] = d
    for a in articles[:8]:
        detail = score_map.get(a.text[:120])
        badge = ""
        if detail:
            color = "#0E9F6E" if detail.label == "positive" else "#E02424" if detail.label == "negative" else "#888"
            badge = f' <span style="color:{color};font-weight:bold;">[{detail.label} {detail.score:+.2f}]</span>'
        st.markdown(f"**[{a.title}]({a.url})**{badge}", unsafe_allow_html=True)
        st.caption(f"{a.source} · {a.published_at[:10]}")
        if a.description:
            st.write(a.description)
        st.divider()


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    ticker = render_sidebar()

    if not st.session_state.get("run"):
        st.title("Welcome 👋")
        st.write(
            "Enter a stock ticker in the sidebar and press **Analyze**. "
            "The app pulls live market data and news, runs an AI sentiment model "
            "and technical indicators, then asks an LLM for a reasoned "
            "Buy / Hold / Sell recommendation."
        )
        st.stop()

    # ---- Run the full pipeline with clear progress feedback -------------
    try:
        with st.spinner(f"Fetching market data for {ticker}…"):
            quote = load_quote(ticker)
            history = load_history(ticker)
        with st.spinner("Fetching recent news…"):
            articles = load_news(quote.name or ticker)
        with st.spinner("Scoring news sentiment with AI…"):
            sentiment = load_sentiment(articles)
        with st.spinner("Computing technical indicators…"):
            tech = analyze(history)
        with st.spinner("Generating recommendations…"):
            rule_rec = _rule_based(quote, tech, sentiment)
            ai_rec = None
            prompt_text = _build_user_prompt(quote, tech, sentiment)
            if settings.openai_enabled:
                try:
                    ai_rec = _with_openai(quote, tech, sentiment)
                except Exception:
                    pass
            rec = ai_rec or rule_rec
    except MarketDataError as exc:
        st.error(str(exc))
        st.stop()

    # ---- Layout ----------------------------------------------------------
    render_header(quote)
    st.divider()

    render_recommendation(rec, prompt_text=prompt_text if ai_rec else None)

    # ---- AI vs Rule-Based comparison ------------------------------------
    if ai_rec:
        st.divider()
        st.subheader("AI vs Rule-Based Comparison")
        col_ai, col_rule = st.columns(2)
        with col_ai:
            ai_color = ACTION_COLORS.get(ai_rec.action, "#1A2A4F")
            st.markdown(
                f'<div style="border-radius:10px;padding:14px;background:{ai_color}10;'
                f'border:1px solid {ai_color};">'
                f'<b style="color:{ai_color};">{ai_rec.engine}</b></div>',
                unsafe_allow_html=True,
            )
            st.metric("Action", ai_rec.action)
            st.metric("Confidence", f"{ai_rec.confidence}%")
            st.write(ai_rec.rationale)
        with col_rule:
            rule_color = ACTION_COLORS.get(rule_rec.action, "#1A2A4F")
            st.markdown(
                f'<div style="border-radius:10px;padding:14px;background:{rule_color}10;'
                f'border:1px solid {rule_color};">'
                f'<b style="color:{rule_color};">Rule-Based Engine</b></div>',
                unsafe_allow_html=True,
            )
            st.metric("Action", rule_rec.action)
            st.metric("Confidence", f"{rule_rec.confidence}%")
            st.write(rule_rec.rationale)
        if ai_rec.action != rule_rec.action:
            st.warning(
                f"The engines **disagree**: AI recommends **{ai_rec.action}** "
                f"while the rule-based engine recommends **{rule_rec.action}**. "
                f"This highlights how an LLM can weigh qualitative context "
                f"(news tone, sector dynamics) differently than a purely quantitative formula."
            )
        else:
            st.success(
                f"Both engines **agree** on **{ai_rec.action}**. "
                f"The AI's reasoning aligns with the quantitative signals."
            )

    st.divider()

    left, right = st.columns([2, 1])
    with left:
        st.subheader("Price & technical chart")
        st.plotly_chart(build_price_chart(history, ticker), use_container_width=True)
    with right:
        st.subheader("Technical indicators")
        render_indicators(tech)
        st.subheader("News sentiment")
        render_sentiment(sentiment)

    st.divider()
    st.subheader("Recent news")
    render_news(articles, sentiment=sentiment)

    # ---- AI Chatbot ----------------------------------------------------------
    st.divider()
    st.subheader("Ask the AI Advisor")

    if not settings.chatbot_enabled:
        st.info(
            "The chatbot requires a free API key. Add one of these to your .env file:\n\n"
            "- **GROQ_API_KEY** — free at https://console.groq.com (recommended)\n"
            "- **GEMINI_API_KEY** — free at https://aistudio.google.com/apikey"
        )
    else:
        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = []
        if st.session_state.get("chat_ticker") != ticker:
            st.session_state["chat_history"] = []
            st.session_state["chat_ticker"] = ticker

        context = build_context(quote, tech, sentiment, rec, articles)

        for role, text in st.session_state["chat_history"]:
            with st.chat_message(role):
                st.markdown(text)

        if user_input := st.chat_input(f"Ask anything about {ticker}…"):
            st.session_state["chat_history"].append(("user", user_input))
            with st.chat_message("user"):
                st.markdown(user_input)

            with st.chat_message("assistant"):
                with st.spinner("Thinking…"):
                    try:
                        reply, engine = gemini_chat(
                            user_message=user_input,
                            context=context,
                            history=st.session_state["chat_history"][:-1],
                        )
                    except Exception as exc:
                        reply = f"Sorry, I couldn't process that request. Error: {exc}"
                        engine = None
                st.markdown(reply)
                if engine:
                    st.caption(f"Powered by {engine}")
            st.session_state["chat_history"].append(("assistant", reply))


if __name__ == "__main__":
    main()
