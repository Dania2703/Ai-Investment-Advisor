"""
src/ui/pages/dashboard.py
=========================
The authenticated analysis workspace — a premium, dark, "Bloomberg-meets-Linear"
fintech interface.

Layout
------
* A sticky top bar (ticker search · market-status dot · last-updated).
* An always-visible hero: ticker/name + solid rating badge + mono quote on the
  left, an animated circular score gauge on the right.
* A KPI strip of equal-height cards (no truncation; directional indicators).
* A segmented control (lucide icons) revealing the deep sections one click at a
  time: Overview · Technicals · Chart · News · AI Analysis · History.
* A floating RAG chatbot pinned bottom-right.

Data discipline: when a value can't be retrieved we show **"Data unavailable"**
rather than fabricating it. All colours come from the tokens in src/styles.css.
"""

from __future__ import annotations

import urllib.parse
from datetime import datetime, timezone
from typing import Callable, Optional

import pandas as pd
import streamlit as st

from config import settings
from src.ai.advisor import Recommendation, get_recommendation
from src.ai.chatbot import build_context
from src.analysis.sentiment import score_articles
from src.analysis.technical import analyze
from src.data.market_data import MarketDataError, get_history, get_quote
from src.data.news_data import get_news
from src.ui import nav, widgets as W
from src.ui.chatbot_widget import render_floating_chatbot
from src.ui.components import build_tv_chart
from src.ui.theme import SENTIMENT_COLORS, pill, render_section_header, theme_toggle_button

NA = "Data unavailable"

# Segmented-control definition: (key, label, lucide-icon-name)
_TABS = [
    ("overview", "Overview", "bar-chart-3"),
    ("tech", "Technicals", "activity"),
    ("chart", "Chart", "candlestick"),
    ("news", "News", "newspaper"),
    ("ai", "AI Analysis", "brain"),
    ("history", "History", "history"),
]


# --------------------------------------------------------------------------- #
# Cached data loaders
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=settings.cache_ttl_seconds, show_spinner=False)
def _load_quote(ticker: str):
    return get_quote(ticker)


@st.cache_data(ttl=settings.cache_ttl_seconds, show_spinner=False)
def _load_history(ticker: str):
    return get_history(ticker, period=settings.default_period, interval=settings.default_interval)


@st.cache_data(ttl=settings.cache_ttl_seconds, show_spinner=False)
def _load_news(ticker: str):
    return get_news(ticker)


@st.cache_data(ttl=settings.cache_ttl_seconds, show_spinner=False)
def _load_sentiment(_articles):
    return score_articles(_articles)


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _money(value: Optional[float], currency: str = "", digits: int = 2) -> str:
    if value is None:
        return NA
    suffix = f" {currency}" if currency else ""
    return f"{value:,.{digits}f}{suffix}"


def _big_number(value: Optional[float]) -> str:
    if value is None:
        return NA
    for unit, factor in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(value) >= factor:
            return f"{value / factor:,.2f}{unit}"
    return f"{value:,.0f}"


def _market_open_now() -> bool:
    """Rough US regular-session check (weekday 09:30–16:00 America/New_York)."""
    now = pd.Timestamp.now(tz="America/New_York")
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 + 30 <= minutes < 16 * 60


# --------------------------------------------------------------------------- #
# Sticky top bar
# --------------------------------------------------------------------------- #
def _render_topbar(user, on_logout: Callable[[], None]) -> str:
    is_open = _market_open_now()
    status = "Market open" if is_open else "Market closed"
    stamp = datetime.now(timezone.utc).strftime("%H:%M UTC · %d %b")

    # Sticky meta header (single HTML block → robust position:sticky)
    st.markdown('<div id="topbar-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <style>
        div:has(> #topbar-anchor) + div {{
            position: sticky; top: 0; z-index: 60;
            background: var(--topbar-bg); backdrop-filter: blur(10px);
            border-bottom: 1px solid var(--border); padding: 6px 2px; margin-bottom: 6px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    c_logo, c_input, c_btn, c_meta, c_theme, c_user = st.columns([1.9, 2.8, 0.95, 1.5, 0.95, 1.2])
    with c_logo:
        st.markdown(
            f"<div style='font-size:18px;font-weight:800;padding-top:8px;'>"
            f"{W.icon('activity', 18, 'var(--brand)')} "
            f"<span style='color:var(--brand)'>AI</span> Advisor</div>",
            unsafe_allow_html=True,
        )
    with c_input:
        ticker = st.text_input(
            "Ticker", value=st.session_state.get("ticker", "AAPL"),
            label_visibility="collapsed", placeholder="Search a ticker — AAPL, MSFT, NVDA…",
        ).upper().strip()
    with c_btn:
        if st.button("Analyze", type="primary", use_container_width=True):
            st.session_state["ticker"] = ticker
            st.session_state["run"] = True
            st.rerun()
    with c_meta:
        st.markdown(
            f"<div class='topbar-meta' style='padding-top:9px;'>"
            f"{W.status_dot(is_open, status)}</div>"
            f"<div class='topbar-meta' style='font-size:11px;'>{stamp}</div>",
            unsafe_allow_html=True,
        )
    with c_theme:
        st.write("")
        theme_toggle_button(key="topbar_theme_toggle")
    with c_user:
        with st.popover(f"@{user['username']}", use_container_width=True):
            st.caption(f"Signed in as **{user['username']}**")
            if st.button("Log out", use_container_width=True, key="logout_btn"):
                on_logout()
    return ticker


# --------------------------------------------------------------------------- #
# Hero — always-visible summary (ticker · badge · gauge · quote · exec summary)
# --------------------------------------------------------------------------- #
def _render_hero(rec: Recommendation, quote) -> None:
    summary = rec.executive_summary or rec.rationale or NA
    tone = "up" if quote.change >= 0 else "down"
    arrow = W.icon("trending-up" if quote.change >= 0 else "trending-down", 16,
                   "var(--bull)" if quote.change >= 0 else "var(--bear)")
    gauge = W.score_gauge(rec.final_score, rec.rating)
    st.markdown(
        f"""
        <div class="hero fade-up">
          <div style="display:flex;justify-content:space-between;align-items:center;
                      gap:24px;flex-wrap:wrap;">
            <div style="min-width:0;flex:1;">
              <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
                <span class="hero-ticker">{quote.ticker}</span>
                {W.badge(rec.rating)}
                <span class="muted" style="font-size:13px;">Confidence
                  <b style="color:var(--text)">{rec.confidence}%</b></span>
              </div>
              <div class="hero-name" style="margin-top:2px;">{quote.name} · {quote.sector or 'N/A'}</div>
              <div style="margin-top:12px;display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;">
                <span class="hero-price">{_money(quote.price, quote.currency)}</span>
                <span class="hero-quote {tone}" style="font-size:15px;">
                  {arrow} {quote.change:+.2f} ({quote.change_pct:+.2f}%)</span>
              </div>
            </div>
            <div>{gauge}</div>
          </div>
          <div class="eyebrow" style="margin-top:18px;">
            {W.icon('brain', 13, 'var(--brand)')} AI Executive Summary</div>
          <div style="font-size:15.5px;line-height:1.65;margin-top:6px;color:var(--text-2);">
            {summary}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _arrow_for(signal: str) -> tuple[str, str]:
    """Return (icon_name, tone) for a textual signal."""
    s = (signal or "").lower()
    if any(w in s for w in ("bull", "up", "golden", "positive", "accumulat", "over")):
        if "overbought" in s or "oversold" in s:
            return "minus", "flat"
        return "trending-up", "up"
    if any(w in s for w in ("bear", "down", "death", "negative", "distribut")):
        return "trending-down", "down"
    return "minus", "flat"


def _render_kpi_strip(tech, sentiment) -> None:
    rsi_tone = _arrow_for(tech.rsi_signal)[1]
    macd_tone = _arrow_for(tech.macd_trend)[1]
    trend_tone = _arrow_for(tech.ma_trend)[1]
    news_tone = ("up" if sentiment.average_score > 0.1 else
                 "down" if sentiment.average_score < -0.1 else "flat")
    vol = tech.atr_pct
    vol_tone = "flat" if vol is None else ("down" if vol >= 4 else "flat" if vol >= 2 else "up")

    cards = [
        W.kpi_card("RSI 14", f"{tech.rsi:.0f}" if tech.rsi is not None else NA,
                   sub=tech.rsi_signal, sub_tone=rsi_tone, icon_name="activity"),
        W.kpi_card("MACD", tech.macd_trend if tech.macd is not None else NA,
                   sub=f"{tech.macd:+.3f}" if tech.macd is not None else "",
                   sub_tone=macd_tone, icon_name="trending-up"),
        W.kpi_card("Trend", tech.ma_trend,
                   sub="50/200 MA", sub_tone=trend_tone, icon_name="bar-chart-3"),
        W.kpi_card("Volatility", f"{vol:.1f}%" if vol is not None else NA,
                   sub="ATR of price", sub_tone=vol_tone, icon_name="gauge"),
        W.kpi_card("News", sentiment.label if sentiment.engine != "None" else NA,
                   sub=f"{sentiment.average_score:+.2f}" if sentiment.engine != "None" else "",
                   sub_tone=news_tone, icon_name="newspaper-mini"),
    ]
    st.markdown(W.grid(cards), unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Score breakdown
# --------------------------------------------------------------------------- #
def _render_score_breakdown(rec: Recommendation) -> None:
    result = rec.score_result
    if result is None:
        return
    for c in result.categories:
        if not c.has_data:
            st.markdown(f"**{c.name}** · weight {c.weight:.0%} — _no data_")
            continue
        st.markdown(f"**{c.name}** · weight {c.weight:.0%} — **{c.score:.0f}/100**")
        st.progress(min(1.0, max(0.0, c.score / 100)))
        for comp in c.components:
            tone = "up" if comp.points >= 0.66 else "flat" if comp.points >= 0.4 else "down"
            ic = W.icon(("trending-up" if tone == "up" else "minus" if tone == "flat"
                         else "trending-down"), 12, f"var(--{'bull' if tone=='up' else 'neutral' if tone=='flat' else 'bear'})")
            st.markdown(f"<span class='muted' style='font-size:13px;'>{ic} "
                        f"{comp.name} ({comp.points:.2f}) — {comp.detail}</span>",
                        unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Market snapshot
# --------------------------------------------------------------------------- #
def _render_market_snapshot(quote, tech) -> None:
    render_section_header("Market Snapshot", "Live market data", "Real-time quote from Finnhub.")
    tone = "up" if quote.change >= 0 else "down"
    cards = [
        W.kpi_card("Price", _money(quote.price, quote.currency),
                   sub=f"{quote.change:+.2f} ({quote.change_pct:+.2f}%)", sub_tone=tone),
        W.kpi_card("Prev Close", _money(quote.previous_close)),
        W.kpi_card("Volume", _big_number(tech.volume) if tech.volume else NA, sub="last bar"),
        W.kpi_card("Market Cap", _big_number(quote.market_cap)),
        W.kpi_card("Sector", quote.sector or NA),
    ]
    st.markdown(W.grid(cards, cls="kpi-grid snap-grid"), unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Technical indicators
# --------------------------------------------------------------------------- #
def _render_technical(tech) -> None:
    render_section_header("Technical Indicators", "The full indicator readout",
                          "Native, TradingView-aligned maths — value, signal and interpretation.")
    if not tech.enough_data:
        st.warning(f"Only {tech.bars} bars available (need ≥ {settings.min_history_bars}); "
                   "long-term indicators may be incomplete.")

    cards = [
        W.kpi_card("RSI 14", f"{tech.rsi:.1f}" if tech.rsi is not None else NA,
                   sub=tech.rsi_signal, sub_tone=_arrow_for(tech.rsi_signal)[1]),
        W.kpi_card("MACD", f"{tech.macd:.3f}" if tech.macd is not None else NA,
                   sub=tech.macd_trend, sub_tone=_arrow_for(tech.macd_trend)[1]),
        W.kpi_card("ADX 14", f"{tech.adx:.1f}" if tech.adx is not None else NA, sub="trend strength"),
        W.kpi_card("ATR %", f"{tech.atr_pct:.2f}%" if tech.atr_pct is not None else NA, sub="volatility"),
    ]
    st.markdown(W.grid([c for c in cards], cls="kpi-grid")
                .replace("repeat(5", "repeat(4"), unsafe_allow_html=True)
    st.write("")

    rows = [{"Indicator": ind.label, "Value": ind.display,
             "Signal": ind.signal, "Interpretation": ind.note} for ind in tech.indicators]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    if tech.as_of is not None:
        st.caption(f"Latest closed bar: {tech.as_of.date()} · {tech.bars} bars · "
                   f"Long-term trend: {tech.ma_trend}.")


# --------------------------------------------------------------------------- #
# Chart
# --------------------------------------------------------------------------- #
def _render_chart(history, ticker) -> None:
    render_section_header("Interactive Chart", "Price action & moving averages",
                          "Candlesticks with SMA50, SMA200 and EMA20 overlays.")
    build_tv_chart(history, ticker)


# --------------------------------------------------------------------------- #
# News
# --------------------------------------------------------------------------- #
def _render_news(articles, sentiment) -> None:
    render_section_header("News Analysis", "Latest headlines & sentiment",
                          "Scored with FinBERT (VADER fallback).")
    has = sentiment.engine != "None"
    cards = [
        W.kpi_card("Sentiment", sentiment.label if has else NA,
                   sub=f"{sentiment.average_score:+.2f}" if has else "",
                   sub_tone=("up" if sentiment.average_score > 0.1 else
                             "down" if sentiment.average_score < -0.1 else "flat")),
        W.kpi_card("Score", f"{sentiment.percent}/100" if has else NA, sub="0–100 scale"),
        W.kpi_card("Mix", f"{sentiment.positive}/{sentiment.neutral}/{sentiment.negative}" if has else NA,
                   sub="pos / neu / neg"),
        W.kpi_card("Engine", sentiment.engine if has else NA),
    ]
    st.markdown(W.grid(cards, cls="kpi-grid").replace("repeat(5", "repeat(4"),
                unsafe_allow_html=True)
    st.write("")

    if not articles:
        st.info("No recent news available for this ticker.")
        return

    score_map = {d.title: d for d in (sentiment.details or [])}
    for a in articles[:8]:
        detail = score_map.get(a.text[:120])
        tag = ""
        if detail:
            color = SENTIMENT_COLORS.get(detail.label, "var(--text-muted)")
            tag = pill(f"{detail.label} {detail.score:+.2f}", color)
        date = a.published_at[:10] if a.published_at else ""
        st.markdown(
            f"""
            <div class="news">
              <div style="display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;">
                <a href="{a.url}" target="_blank" style="font-weight:600;font-size:15px;">{a.title}</a>
                {tag}
              </div>
              <div class="muted mono" style="font-size:11px;margin:5px 0;">{a.source} · {date}</div>
              <div class="muted" style="font-size:13px;">{(a.description or '')[:220]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# --------------------------------------------------------------------------- #
# Detailed AI analysis
# --------------------------------------------------------------------------- #
def _bullets(items, color, fallback=NA) -> str:
    if not items:
        return f"<div class='muted'>{fallback}</div>"
    lis = "".join(
        f"<li style='margin-bottom:6px;'><span style='color:{color};'>▸</span> {x}</li>"
        for x in items[:6]
    )
    return f"<ul style='list-style:none;padding-left:0;margin:0;'>{lis}</ul>"


def _render_detailed_ai(rec: Recommendation) -> None:
    render_section_header("Detailed AI Analysis", "The full explanation",
                          "Grounded in the indicators, sentiment and the engine's score.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"<div class='card'><div style='font-weight:700;color:var(--bull);"
            f"margin-bottom:8px;display:flex;align-items:center;gap:7px;'>"
            f"{W.icon('trending-up', 16, 'var(--bull)')} Bullish Factors</div>"
            f"{_bullets(rec.bullish_factors or rec.opportunities, 'var(--bull)')}</div>",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"<div class='card'><div style='font-weight:700;color:var(--bear);"
            f"margin-bottom:8px;display:flex;align-items:center;gap:7px;'>"
            f"{W.icon('trending-down', 16, 'var(--bear)')} Bearish Factors</div>"
            f"{_bullets(rec.bearish_factors or rec.risks, 'var(--bear)')}</div>",
            unsafe_allow_html=True,
        )

    if rec.technical_analysis:
        st.markdown(f"<div class='card'><b>Technical read.</b> "
                    f"<span class='muted'>{rec.technical_analysis}</span></div>",
                    unsafe_allow_html=True)
    if rec.sentiment_analysis:
        st.markdown(f"<div class='card'><b>Sentiment read.</b> "
                    f"<span class='muted'>{rec.sentiment_analysis}</span></div>",
                    unsafe_allow_html=True)

    st.markdown(
        f"<div class='card' style='border-color:rgba(245,158,11,0.35);'>"
        f"<div style='font-weight:700;color:var(--neutral);margin-bottom:4px;'>"
        f"Risk Assessment</div>"
        f"<span class='muted'>{rec.risk_assessment or NA}</span></div>",
        unsafe_allow_html=True,
    )

    o1, o2 = st.columns(2)
    with o1:
        st.markdown(
            f"<div class='card'><div style='font-weight:700;'>Short-Term Outlook</div>"
            f"<span class='muted'>{rec.short_term_outlook or NA}</span></div>",
            unsafe_allow_html=True,
        )
    with o2:
        st.markdown(
            f"<div class='card'><div style='font-weight:700;'>Long-Term Outlook</div>"
            f"<span class='muted'>{rec.long_term_outlook or NA}</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown(f"<div style='margin-top:8px;font-weight:700;'>Confidence Level: "
                f"<span class='mono' style='color:var(--brand);'>{rec.confidence}%</span></div>",
                unsafe_allow_html=True)
    st.progress(min(1.0, max(0.0, rec.confidence / 100)))
    st.caption(rec.disclaimer)


# --------------------------------------------------------------------------- #
# Sources — favicon chips grouped by trust tier
# --------------------------------------------------------------------------- #
def _render_sources(ticker: str, company: str, articles) -> None:
    render_section_header("Sources", "Verify the data",
                          "Cross-check every figure against the originals.")
    q = urllib.parse.quote

    official = [
        ("SEC EDGAR",
         f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&ticker={ticker}"
         f"&type=10-K&dateb=&owner=include&count=40", "sec.gov"),
        ("Investor Relations",
         f"https://www.google.com/search?q={q(company + ' investor relations')}", "google.com"),
    ]
    market = [
        ("Yahoo Finance", f"https://finance.yahoo.com/quote/{ticker}", "finance.yahoo.com"),
        ("Finnhub", "https://finnhub.io/", "finnhub.io"),
    ]
    news_seen, news_chips = set(), []
    for a in (articles or []):
        if not a.url:
            continue
        domain = urllib.parse.urlparse(a.url).netloc.replace("www.", "")
        if domain in news_seen:
            continue
        news_seen.add(domain)
        news_chips.append(W.source_chip(a.source or domain, a.url, domain))
        if len(news_chips) >= 6:
            break

    def tier(title, chips):
        if not chips:
            return ""
        return (f"<div class='muted' style='font-size:11px;letter-spacing:.08em;"
                f"text-transform:uppercase;margin:10px 0 6px;'>{title}</div>"
                f"<div>{''.join(chips)}</div>")

    st.markdown(
        "<div class='card'>"
        + tier("Official / Regulatory", [W.source_chip(l, u, d) for l, u, d in official])
        + tier("Market Data", [W.source_chip(l, u, d) for l, u, d in market])
        + tier("News Outlets", news_chips)
        + "</div>",
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# Saved history
# --------------------------------------------------------------------------- #
def _render_history(user) -> None:
    from src.auth import delete_saved_analysis, list_saved_analyses
    render_section_header("Saved History", "Your previous searches",
                          "Saved automatically each time you run an analysis.")
    try:
        rows = list_saved_analyses(user["id"], limit=25)
    except Exception as exc:  # noqa: BLE001
        st.info(f"History is temporarily unavailable: {exc}")
        return
    if not rows:
        st.markdown("<div class='card muted'>No saved analyses yet — run one above "
                    "and it'll appear here.</div>", unsafe_allow_html=True)
        return
    for r in rows:
        c1, c2, c3, c4, c5 = st.columns([1.3, 2, 1.4, 3.5, 0.7])
        c1.markdown(f"<b class='mono'>{r.ticker}</b>", unsafe_allow_html=True)
        c2.markdown(W.badge(r.rating), unsafe_allow_html=True)
        c3.markdown(f"<span class='mono'>{r.final_score:.0f}/100</span>"
                    if r.final_score is not None else NA, unsafe_allow_html=True)
        c4.markdown(f"<span class='muted mono' style='font-size:12px;'>{r.created_at} · "
                    f"{_money(r.price)}</span>", unsafe_allow_html=True)
        if c5.button("✕", key=f"del_{r.id}", help="Delete"):
            delete_saved_analysis(user["id"], r.id)
            st.rerun()


# --------------------------------------------------------------------------- #
# Segmented control
# --------------------------------------------------------------------------- #
def _render_segmented_nav() -> str:
    active = st.session_state.get("dash_tab", "overview")
    cols = st.columns(len(_TABS))
    for col, (key, label, icon_name) in zip(cols, _TABS):
        with col:
            is_active = key == active
            color = "var(--brand)" if is_active else "var(--text-muted)"
            st.markdown(f"<div class='seg-icon'>{W.icon(icon_name, 18, color)}</div>",
                        unsafe_allow_html=True)
            if st.button(label, key=f"tab_{key}", use_container_width=True,
                         type="primary" if is_active else "secondary"):
                st.session_state["dash_tab"] = key
                st.rerun()
    return active


# --------------------------------------------------------------------------- #
# Welcome (empty state)
# --------------------------------------------------------------------------- #
def _render_welcome(user) -> None:
    st.markdown(
        f"""
        <div class="hero fade-up" style="text-align:center;padding:48px;">
          <div style="font-size:30px;font-weight:800;">Welcome, {user['username']}</div>
          <div class="muted" style="font-size:16px;margin-top:10px;max-width:560px;
               margin-left:auto;margin-right:auto;">
            Search a ticker above and hit <b style="color:var(--brand)">Analyze</b> for a
            transparent, data-driven breakdown — executive summary, an animated score gauge,
            indicators, news sentiment and a full AI explanation.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    _render_history(user)


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def render(user: dict, on_logout: Callable[[], None]) -> None:
    """Render the full dashboard for the logged-in *user*."""
    _render_topbar(user, on_logout)

    if not st.session_state.get("run"):
        _render_welcome(user)
        return

    ticker = st.session_state.get("ticker", "AAPL")

    # ---- Pipeline -------------------------------------------------------
    try:
        with st.spinner(f"Fetching market data for {ticker}…"):
            quote = _load_quote(ticker)
            history = _load_history(ticker)
        with st.spinner("Fetching news…"):
            articles = _load_news(ticker)
        with st.spinner("Scoring sentiment…"):
            sentiment = _load_sentiment(articles)
        with st.spinner("Computing indicators…"):
            tech = analyze(history)
        with st.spinner("Scoring & writing the AI brief…"):
            rec = get_recommendation(quote, tech, sentiment, articles)
    except MarketDataError as exc:
        st.error(f"❌ {exc}")
        st.caption("Check the symbol and try again. We never show fabricated data.")
        return
    except Exception as exc:  # noqa: BLE001
        st.error(f"Unexpected error while analyzing {ticker}: {exc}")
        return

    # ---- Persist to the user's history (best-effort) --------------------
    if not st.session_state.get(f"saved::{ticker}::{quote.as_of}"):
        try:
            from src.auth import save_analysis
            save_analysis(
                user_id=user["id"], ticker=ticker, company_name=quote.name,
                price=quote.price, rating=rec.rating, final_score=rec.final_score,
                confidence=rec.confidence, executive_summary=rec.executive_summary or rec.rationale,
            )
            st.session_state[f"saved::{ticker}::{quote.as_of}"] = True
        except Exception:  # noqa: BLE001
            pass

    # ---- Always-visible summary ----------------------------------------
    _render_hero(rec, quote)
    st.write("")
    _render_kpi_strip(tech, sentiment)
    st.write("")

    # ---- Segmented control + the active section ------------------------
    active = _render_segmented_nav()
    st.write("")

    if active == "overview":
        _render_market_snapshot(quote, tech)
        st.write("")
        with st.expander("How this score was built (weighted breakdown)"):
            _render_score_breakdown(rec)
        st.write("")
        _render_sources(ticker, quote.name, articles)
    elif active == "tech":
        _render_technical(tech)
    elif active == "chart":
        _render_chart(history, ticker)
    elif active == "news":
        _render_news(articles, sentiment)
    elif active == "ai":
        _render_detailed_ai(rec)
    elif active == "history":
        _render_history(user)

    # ---- Floating RAG chatbot ------------------------------------------
    context = build_context(quote, tech, sentiment, rec, articles)
    render_floating_chatbot(ticker, context)
