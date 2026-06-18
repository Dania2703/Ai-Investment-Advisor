"""
src/ui/components.py
====================
Reusable presentation helpers for the Streamlit front-end.

Keeping the Plotly chart construction and other view logic here keeps
`app.py` focused on layout and orchestration.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.analysis.technical import compute_macd, compute_rsi, compute_sma
from config import settings


# Colour palette (navy / teal / gold — consistent across the project).
COLORS = {
    "up": "#0E9F6E",
    "down": "#E02424",
    "price": "#1A2A4F",
    "sma50": "#0694A2",
    "sma200": "#C99700",
    "macd": "#1A2A4F",
    "signal": "#C99700",
}

ACTION_COLORS = {"Buy": "#0E9F6E", "Hold": "#C99700", "Sell": "#E02424"}


def build_price_chart(history: pd.DataFrame, ticker: str) -> go.Figure:
    """
    Build a 3-row figure: candlesticks + moving averages, MACD, and RSI.

    The shared x-axis lets the user line up price action with momentum and
    overbought/oversold conditions at a glance.
    """
    close = history["Close"].astype(float)
    sma50 = compute_sma(close, settings.sma_short)
    sma200 = compute_sma(close, settings.sma_long)
    macd_df = compute_macd(close)
    rsi = compute_rsi(close)

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=(f"{ticker} Price & Moving Averages", "MACD", "RSI (14)"),
    )

    # ---- Row 1: candlesticks + SMAs -------------------------------------
    fig.add_trace(
        go.Candlestick(
            x=history.index,
            open=history["Open"],
            high=history["High"],
            low=history["Low"],
            close=history["Close"],
            name="Price",
            increasing_line_color=COLORS["up"],
            decreasing_line_color=COLORS["down"],
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=history.index, y=sma50, name="SMA 50",
                   line=dict(color=COLORS["sma50"], width=1.5)),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=history.index, y=sma200, name="SMA 200",
                   line=dict(color=COLORS["sma200"], width=1.5)),
        row=1, col=1,
    )

    # ---- Row 2: MACD -----------------------------------------------------
    fig.add_trace(
        go.Bar(x=history.index, y=macd_df["hist"], name="Histogram",
               marker_color="rgba(26,42,79,0.35)"),
        row=2, col=1,
    )
    fig.add_trace(
        go.Scatter(x=history.index, y=macd_df["macd"], name="MACD",
                   line=dict(color=COLORS["macd"], width=1.2)),
        row=2, col=1,
    )
    fig.add_trace(
        go.Scatter(x=history.index, y=macd_df["signal"], name="Signal",
                   line=dict(color=COLORS["signal"], width=1.2)),
        row=2, col=1,
    )

    # ---- Row 3: RSI with 30/70 guide lines ------------------------------
    fig.add_trace(
        go.Scatter(x=history.index, y=rsi, name="RSI",
                   line=dict(color=COLORS["price"], width=1.2)),
        row=3, col=1,
    )
    fig.add_hline(y=70, line_dash="dot", line_color=COLORS["down"], row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color=COLORS["up"], row=3, col=1)

    fig.update_layout(
        height=720,
        showlegend=True,
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
    )
    fig.update_yaxes(range=[0, 100], row=3, col=1)
    return fig
