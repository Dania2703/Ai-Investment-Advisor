"""
src/ui/components.py
====================
UI components for the Streamlit front-end.

Uses TradingView Lightweight Charts for price visualization.
"""

from __future__ import annotations

import pandas as pd
from streamlit_lightweight_charts import renderLightweightCharts

ACTION_COLORS = {"Buy": "#0E9F6E", "Hold": "#C99700", "Sell": "#E02424"}

# Colour scale for the 5-way rating produced by the scoring engine.
RATING_COLORS = {
    "Strong Buy": "#0B7A4B",
    "Buy": "#0E9F6E",
    "Hold": "#C99700",
    "Sell": "#E0533C",
    "Strong Sell": "#E02424",
}


def build_tv_chart(history: pd.DataFrame, ticker: str) -> None:
    """
    Render a TradingView Lightweight candlestick chart with MA overlays.
    """
    candle_data = []
    for idx, row in history.iterrows():
        ts = int(idx.timestamp())
        candle_data.append({
            "time": ts,
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
        })

    close = history["Close"].astype(float)
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    ema20 = close.ewm(span=20, adjust=False).mean()

    sma50_data = []
    for idx, val in sma50.dropna().items():
        sma50_data.append({"time": int(idx.timestamp()), "value": float(val)})

    sma200_data = []
    for idx, val in sma200.dropna().items():
        sma200_data.append({"time": int(idx.timestamp()), "value": float(val)})

    ema20_data = []
    for idx, val in ema20.dropna().items():
        ema20_data.append({"time": int(idx.timestamp()), "value": float(val)})

    # Colours follow the active light/dark theme.
    from src.ui.theme import active_theme, chart_colors
    c = chart_colors()

    chart_options = {
        "height": 500,
        "layout": {
            "textColor": c["text"],
            "background": {"type": "solid", "color": c["bg"]},
            "fontFamily": "JetBrains Mono, monospace",
        },
        "grid": {
            "vertLines": {"color": c["grid"]},
            "horzLines": {"color": c["grid"]},
        },
        "crosshair": {"mode": 0},
        "rightPriceScale": {"borderColor": c["border"]},
        "timeScale": {
            "borderColor": c["border"],
            "timeVisible": False,
        },
        "watermark": {
            "visible": True,
            "fontSize": 56,
            "horzAlign": "center",
            "vertAlign": "center",
            "color": c["watermark"],
            "text": ticker,
        },
    }

    series = [
        {
            "type": "Candlestick",
            "data": candle_data,
            "options": {
                "upColor": c["up"],
                "downColor": c["down"],
                "borderVisible": False,
                "wickUpColor": c["up"],
                "wickDownColor": c["down"],
            },
        },
        {
            "type": "Line",
            "data": sma50_data,
            "options": {"color": c["sma50"], "lineWidth": 2, "title": "SMA 50"},
        },
        {
            "type": "Line",
            "data": sma200_data,
            "options": {"color": c["sma200"], "lineWidth": 2, "title": "SMA 200"},
        },
        {
            "type": "Line",
            "data": ema20_data,
            "options": {"color": c["ema20"], "lineWidth": 1, "title": "EMA 20"},
        },
    ]

    # Re-key the chart per theme so Lightweight Charts re-renders on toggle.
    renderLightweightCharts(
        [{"chart": chart_options, "series": series}],
        key=f"tv_chart_{ticker}_{active_theme()}",
    )
