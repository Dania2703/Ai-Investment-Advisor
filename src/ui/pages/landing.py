"""
src/ui/pages/landing.py
=======================
The marketing landing page: hero, project overview, feature grid, "how it
works", and a call-to-action. Pure presentation — no data calls.
"""

from __future__ import annotations

import streamlit as st

from config import settings
from src.ui import nav
from src.ui.theme import PALETTE, theme_toggle_button

_FEATURES = [
    ("📡", "Real Market Data",
     "Live quotes from Finnhub and clean, validated daily OHLCV from Yahoo Finance. "
     "Every number is sourced — never invented."),
    ("📊", "Validated Indicators",
     "RSI, MACD, SMA/EMA, Bollinger, ADX, ATR, OBV and more — implemented natively "
     "with TradingView-aligned conventions and unit-tested for no look-ahead bias."),
    ("📰", "News Sentiment",
     "Financial headlines scored with FinBERT (VADER fallback) into positive, "
     "negative and risk factors that feed the analysis."),
    ("🧠", "Explainable AI",
     "A deterministic scoring engine decides the rating; the LLM explains it. "
     "Same inputs always yield the same call — fully transparent."),
    ("💬", "RAG Chatbot",
     "Ask anything about the stock you're viewing. The assistant answers only from "
     "retrieved data, indicators and news — it never makes up financials."),
    ("🔒", "Your History",
     "Create an account to save every analysis you run and revisit it anytime, "
     "backed by a real Postgres/SQL database."),
]


def render() -> None:
    p = PALETTE

    # ---- Top nav bar ----------------------------------------------------
    left, right = st.columns([3, 2])
    with left:
        st.markdown(
            f"<div style='font-size:20px;font-weight:800;'>📈 "
            f"<span style='color:{p['accent']}'>AI</span> Investment Advisor</div>",
            unsafe_allow_html=True,
        )
    with right:
        c0, c1, c2 = st.columns([1, 1, 1.2])
        with c0:
            theme_toggle_button(key="landing_theme_toggle")
        if c1.button("Log in", use_container_width=True, key="land_login"):
            nav.go_to(nav.LOGIN)
        if c2.button("Get started", type="primary", use_container_width=True, key="land_register"):
            nav.go_to(nav.REGISTER)

    # ---- Hero -----------------------------------------------------------
    st.markdown(
        f"""
        <div class="ai-fade-in" style="text-align:center;padding:56px 12px 28px;">
          <div class="ai-chip" style="border-color:{p['accent']}55;color:{p['accent']};">
            Explainable AI · Real data · No hallucinations
          </div>
          <div style="font-size:54px;font-weight:800;line-height:1.05;margin-top:14px;">
            Institutional-grade stock analysis,<br>
            <span style="background:linear-gradient(135deg,{p['accent']},{p['accent_2']});
                  -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
              
            </span>
          </div>
          <div class="ai-muted" style="font-size:18px;max-width:680px;margin:18px auto 0;">
            Enter any ticker and get a transparent, data-driven verdict — technical
            indicators, news sentiment, and an AI brief that shows its work. Built for
            people who want the <i>why</i>, not just a buy/sell arrow.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cta1, cta2, cta3 = st.columns([2, 2, 2])
    with cta2:
        if st.button("🚀  Start analyzing free", type="primary",
                     use_container_width=True, key="hero_cta"):
            nav.go_to(nav.REGISTER)

    st.write("")
    # ---- Trust strip ----------------------------------------------------
    st.markdown(
        f"""
        <div style="display:flex;justify-content:center;gap:10px;flex-wrap:wrap;margin:8px 0 32px;">
          <span class="ai-chip">Finnhub</span>
          <span class="ai-chip">Yahoo Finance</span>
          <span class="ai-chip">FinBERT</span>
          <span class="ai-chip">SEC filings</span>
          <span class="ai-chip">TradingView charts</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Overview -------------------------------------------------------
    st.markdown(
        f"""
        <div class="ai-card glow">
          <div class="ai-section-eyebrow">The principle</div>
          <div class="ai-section-title">The engine decides. The AI explains.</div>
          <p class="ai-muted" style="font-size:16px;margin-top:8px;">
            A deterministic, weighted scoring engine produces the 0–100 score and rating
            from validated indicators and sentiment — so the same inputs always give the
            same answer. The language model only narrates that result. You get reproducible,
            auditable analysis instead of a black box, with clickable sources to verify
            every figure yourself.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Feature grid ---------------------------------------------------
    st.write("")
    st.markdown('<div class="ai-section-eyebrow">Features</div>', unsafe_allow_html=True)
    st.markdown('<div class="ai-section-title">Everything you need to form a view</div>',
                unsafe_allow_html=True)
    st.write("")

    cols = st.columns(3)
    for i, (icon, title, desc) in enumerate(_FEATURES):
        with cols[i % 3]:
            st.markdown(
                f"""
                <div class="ai-card" style="min-height:190px;">
                  <div style="font-size:28px;">{icon}</div>
                  <div style="font-size:17px;font-weight:700;margin:8px 0 4px;">{title}</div>
                  <div class="ai-muted" style="font-size:14px;">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ---- How it works ---------------------------------------------------
    st.write("")
    st.markdown('<div class="ai-section-eyebrow">How it works</div>', unsafe_allow_html=True)
    st.markdown('<div class="ai-section-title">From ticker to thesis in seconds</div>',
                unsafe_allow_html=True)
    steps = [
        ("01", "Enter a ticker", "AAPL, MSFT, NVDA — anything Finnhub & Yahoo cover."),
        ("02", "We pull & validate", "Live quote, 2y of clean candles, and recent news."),
        ("03", "Indicators + sentiment", "Native TradingView-aligned maths and FinBERT scoring."),
        ("04", "Score → explain", "The engine rates it; the AI writes the brief; you verify the sources."),
    ]
    scols = st.columns(4)
    for col, (num, title, desc) in zip(scols, steps):
        with col:
            st.markdown(
                f"""
                <div class="ai-card" style="min-height:160px;">
                  <div class="ai-mono" style="font-size:28px;color:{p['accent']};">{num}</div>
                  <div style="font-weight:700;margin:6px 0 4px;">{title}</div>
                  <div class="ai-muted" style="font-size:13px;">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ---- Final CTA ------------------------------------------------------
    st.write("")
    st.markdown(
        f"""
        <div class="ai-card glow" style="text-align:center;padding:36px;">
          <div style="font-size:26px;font-weight:800;">Ready to see the <i>why</i>?</div>
          <div class="ai-muted" style="margin:6px 0 4px;">
            Free to use. Educational tool — not financial advice.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    f1, f2, f3 = st.columns([2, 2, 2])
    with f2:
        if st.button("Create your free account", type="primary",
                     use_container_width=True, key="footer_cta"):
            nav.go_to(nav.REGISTER)

    chatbot = "configured" if settings.chatbot_enabled else "available with a free API key"
    st.markdown(
        f"<div class='ai-muted' style='text-align:center;font-size:12px;margin-top:24px;'>"
        f"© AI Investment Advisor · Conversational assistant {chatbot} · "
        f"For educational use only.</div>",
        unsafe_allow_html=True,
    )
