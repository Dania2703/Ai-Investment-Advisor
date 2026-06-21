"""
src/data/market_data.py
=======================
Market-data access layer.

Two distinct things live here — keep them distinct:

* :func:`get_quote` — the **live, intraday** last price from **Finnhub**
  (real-time tick). This is *not* an end-of-day close.
* :func:`get_history` — the **end-of-day** daily OHLCV candle series used by all
  indicators, from **yfinance** (with an optional Tiingo fallback).

Price-adjustment policy (explicit, documented choice)
-----------------------------------------------------
The canonical ``Close`` is **split-adjusted but dividend-UNADJUSTED** — the same
series TradingView / Investing.com / Barchart show by default. With yfinance
that is exactly what ``auto_adjust=False`` returns in the ``Close`` column; the
fully-adjusted series is preserved as ``Adj Close`` for reference only.
Indicators must use ``Close``, never ``Adj Close``, so our numbers line up with
those reference sites. See ``settings.price_adjustment``.

Look-ahead guard
----------------
During a live session the final daily bar is still *forming*. We drop it so the
latest indicator values reflect a **closed** bar. Crucially we only drop it
while the exchange is **open** — after the close, today's bar is complete and is
kept (fixing the "chart is a day stale all evening" bug).

Data-quality guard
------------------
yfinance is an unofficial scraper that can return empty / short / stale /
NaN-filled frames under rate-limiting. :func:`validate_history` checks the frame
and **raises loudly** rather than letting bad data flow into the analysis.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
import requests
import yfinance as yf

from config import settings

FINNHUB_BASE = "https://finnhub.io/api/v1"
TIINGO_BASE = "https://api.tiingo.com/tiingo/daily"

REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


@dataclass
class Quote:
    """A lightweight snapshot of a ticker's *live* state (Finnhub)."""

    ticker: str
    name: str
    currency: str
    price: float
    previous_close: float
    change: float
    change_pct: float
    market_cap: Optional[float]
    sector: Optional[str]
    as_of: datetime

    @property
    def is_up(self) -> bool:
        return self.change >= 0


class MarketDataError(Exception):
    """Raised when market data cannot be retrieved or fails validation."""


# --------------------------------------------------------------------------- #
# Live quote (Finnhub)
# --------------------------------------------------------------------------- #
def _finnhub_get(endpoint: str, params: dict) -> dict:
    """Make an authenticated GET request to Finnhub."""
    params["token"] = settings.finnhub_api_key
    resp = requests.get(f"{FINNHUB_BASE}{endpoint}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_quote(ticker: str) -> Quote:
    """Return a current (live, intraday) Quote snapshot for *ticker* via Finnhub."""
    ticker = ticker.strip().upper()
    if not ticker:
        raise MarketDataError("Ticker symbol is empty.")
    if not settings.finnhub_enabled:
        raise MarketDataError(
            "Finnhub API key is not configured. Add FINNHUB_API_KEY to your .env file."
        )

    try:
        quote_data = _finnhub_get("/quote", {"symbol": ticker})
    except requests.RequestException as exc:
        raise MarketDataError(f"Could not fetch quote for '{ticker}': {exc}")

    price = quote_data.get("c", 0)
    prev_close = quote_data.get("pc", 0)

    if not price:
        raise MarketDataError(
            f"No live quote found for '{ticker}'. Check the symbol and try again."
        )

    try:
        profile = _finnhub_get("/stock/profile2", {"symbol": ticker})
    except Exception:  # noqa: BLE001 - profile is non-essential
        profile = {}

    name = profile.get("name") or ticker
    sector = profile.get("finnhubIndustry")
    market_cap = profile.get("marketCapitalization")
    if market_cap:
        market_cap = market_cap * 1e6
    currency = profile.get("currency") or "USD"

    change = quote_data.get("d", 0) or (price - prev_close)
    change_pct = quote_data.get("dp", 0) or (change / prev_close * 100 if prev_close else 0)

    return Quote(
        ticker=ticker,
        name=name,
        currency=currency,
        price=float(price),
        previous_close=float(prev_close),
        change=float(change),
        change_pct=float(change_pct),
        market_cap=market_cap,
        sector=sector,
        as_of=datetime.now(timezone.utc),
    )


# --------------------------------------------------------------------------- #
# Session / freshness helpers
# --------------------------------------------------------------------------- #
def _is_session_open(now_ts: pd.Timestamp) -> bool:
    """
    Roughly true if a regular US equity session is in progress at *now_ts*
    (a tz-aware timestamp in the exchange's timezone).

    Weekday + 09:30–16:00 local. Holidays are not modelled — but that is safe
    here: on a holiday the provider simply won't return a bar dated 'today', so
    the look-ahead guard has nothing to drop.
    """
    if now_ts.weekday() >= 5:  # Sat/Sun
        return False
    minutes = now_ts.hour * 60 + now_ts.minute
    return 9 * 60 + 30 <= minutes < 16 * 60


def _business_days_stale(last_bar_date, today) -> int:
    """Number of business days between the last bar and today (>= 0)."""
    return int(np.busday_count(last_bar_date, today))


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def validate_history(
    data: pd.DataFrame,
    ticker: str,
    *,
    raise_on_stale: bool = True,
) -> list[str]:
    """
    Validate a cleaned OHLCV frame. Raises :class:`MarketDataError` on fatal
    problems; returns a list of non-fatal **warnings** otherwise.

    Fatal: missing columns, empty/too-short frame, NaN/zero in the latest bar,
    impossible OHLC ordering, or a stale latest bar. These are the silent
    failure modes that let bad data into the analysis.
    """
    warnings: list[str] = []

    missing = [c for c in REQUIRED_COLUMNS if c not in data.columns]
    if missing:
        raise MarketDataError(f"{ticker}: history is missing columns {missing}.")

    if data.empty or len(data) < 2:
        raise MarketDataError(f"{ticker}: history is empty or too short ({len(data)} rows).")

    # Latest bar must be fully populated and sane.
    last = data.iloc[-1]
    if last[REQUIRED_COLUMNS].isna().any():
        raise MarketDataError(
            f"{ticker}: latest bar has NaN values {dict(last[REQUIRED_COLUMNS])} "
            "(likely a failed/rate-limited data pull)."
        )
    if last["Close"] <= 0 or last["High"] < last["Low"]:
        raise MarketDataError(
            f"{ticker}: latest bar is invalid (Close={last['Close']}, "
            f"High={last['High']}, Low={last['Low']})."
        )

    # OHLC ordering sanity across the whole frame (allow tiny float noise).
    bad_rows = data[(data["High"] + 1e-6 < data["Low"])]
    if len(bad_rows) > 0:
        raise MarketDataError(
            f"{ticker}: {len(bad_rows)} bar(s) have High < Low — corrupt series."
        )

    # NaN density in Close.
    nan_ratio = data["Close"].isna().mean()
    if nan_ratio > 0.05:
        warnings.append(f"{nan_ratio:.0%} of closes are NaN — data source may be degraded.")

    # Row-count plausibility.
    if len(data) < settings.min_history_bars:
        warnings.append(
            f"only {len(data)} bars (< {settings.min_history_bars}); "
            "long-term indicators (SMA200) may be incomplete."
        )

    # Freshness.
    last_date = data.index[-1].date()
    today = datetime.now(timezone.utc).date()
    stale_days = _business_days_stale(last_date, today)
    if stale_days > settings.max_stale_business_days:
        msg = (
            f"{ticker}: latest bar is {last_date} — {stale_days} business days old "
            f"(> {settings.max_stale_business_days}). Data is stale."
        )
        if raise_on_stale:
            raise MarketDataError(msg)
        warnings.append(msg)

    # Recent corporate actions that can desync a comparison with reference sites.
    if "Stock Splits" in data.columns:
        recent_splits = data["Stock Splits"].tail(10)
        if (recent_splits != 0).any():
            warnings.append(
                "a stock split occurred in the last 10 bars — historical prices are "
                "back-adjusted; compare against a split-adjusted reference."
            )

    return warnings


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #
def _fetch_yfinance(ticker: str, period: str, interval: str) -> pd.DataFrame:
    """Fetch raw (split-adjusted, dividend-unadjusted) candles from yfinance."""
    last_exc: Optional[Exception] = None
    for attempt in range(1, settings.history_retries + 1):
        try:
            df = yf.Ticker(ticker).history(
                period=period,
                interval=interval,
                auto_adjust=False,   # Close = split-adj, div-UNADJUSTED (matches ref sites)
                actions=True,        # include Dividends / Stock Splits columns
            )
            if df is not None and not df.empty:
                df.attrs["source"] = "yfinance"
                return df
            last_exc = MarketDataError("empty frame")
        except Exception as exc:  # noqa: BLE001 - transient scraper/network errors
            last_exc = exc
        if attempt < settings.history_retries:
            time.sleep(settings.history_retry_wait_seconds * attempt)
    raise MarketDataError(f"yfinance failed for '{ticker}' after "
                          f"{settings.history_retries} attempts: {last_exc}")


def _fetch_tiingo(ticker: str, period: str) -> pd.DataFrame:
    """
    Optional fallback. Reconstructs the SAME canonical series as yfinance:
    split-adjusted, dividend-unadjusted Close.

    Tiingo gives ``close`` (fully unadjusted) and ``splitFactor`` per row. The
    split-adjusted/dividend-unadjusted price is ``close`` scaled by the
    cumulative *future* split factor, so the latest bar is unchanged and older
    bars are back-adjusted for splits only — exactly matching reference sites.
    """
    years = 2 if period.endswith("y") and period[:-1].isdigit() else 2
    start = (datetime.now(timezone.utc) - pd.Timedelta(days=int(years) * 372)).date()
    resp = requests.get(
        f"{TIINGO_BASE}/{ticker}/prices",
        params={"startDate": start.isoformat(), "format": "json", "resampleFreq": "daily"},
        headers={"Authorization": f"Token {settings.tiingo_api_key}"},
        timeout=20,
    )
    resp.raise_for_status()
    rows = resp.json()
    if not rows:
        raise MarketDataError(f"Tiingo returned no data for '{ticker}'.")

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df.set_index("date").sort_index()

    split = df.get("splitFactor", pd.Series(1.0, index=df.index)).fillna(1.0)
    # Cumulative split factor applied to *past* bars (reverse cumprod, excl. self).
    cum_future_split = split[::-1].cumprod()[::-1].shift(-1).fillna(1.0)

    out = pd.DataFrame(index=df.index)
    out["Open"] = df["open"] / cum_future_split
    out["High"] = df["high"] / cum_future_split
    out["Low"] = df["low"] / cum_future_split
    out["Close"] = df["close"] / cum_future_split          # split-adj, div-unadj
    out["Adj Close"] = df["adjClose"]                       # fully adjusted (reference)
    out["Volume"] = df["volume"] * cum_future_split
    out["Dividends"] = df.get("divCash", 0.0)
    out["Stock Splits"] = (split - 1.0).where(split != 1.0, 0.0)
    out.attrs["source"] = "tiingo"
    return out


def _fetch_candles(ticker: str, period: str, interval: str) -> pd.DataFrame:
    """yfinance first; Tiingo only as a fallback when a key is configured."""
    try:
        return _fetch_yfinance(ticker, period, interval)
    except MarketDataError as yf_exc:
        if settings.tiingo_enabled and interval.endswith("d"):
            print(f"[DATA] yfinance failed, trying Tiingo fallback: {yf_exc}")
            try:
                return _fetch_tiingo(ticker, period)
            except Exception as ti_exc:  # noqa: BLE001
                raise MarketDataError(
                    f"Both providers failed for '{ticker}'. "
                    f"yfinance: {yf_exc}; tiingo: {ti_exc}"
                )
        raise


# --------------------------------------------------------------------------- #
# Public: cleaned, validated history
# --------------------------------------------------------------------------- #
def get_history(
    ticker: str,
    period: str = "2y",
    interval: str = "1d",
    drop_incomplete: Optional[bool] = None,
    *,
    raise_on_stale: bool = True,
) -> pd.DataFrame:
    """
    Return clean, validated daily OHLCV for *ticker*.

    Deterministic: the same inputs yield the same frame (retries and the
    optional fallback only add resilience, they do not change the output).

    The returned frame carries metadata in ``df.attrs``:
    ``source``, ``adjustment``, ``last_bar``, ``rows``, ``dropped_forming_bar``,
    ``warnings``.
    """
    ticker = ticker.strip().upper()
    if not ticker:
        raise MarketDataError("Ticker symbol is empty.")
    if drop_incomplete is None:
        drop_incomplete = settings.drop_incomplete_bar

    data = _fetch_candles(ticker, period, interval)
    source = data.attrs.get("source", "yfinance")

    # ---- Look-ahead guard, using the EXCHANGE timezone yfinance tagged -----
    dropped_forming = False
    tz = getattr(data.index, "tz", None)
    if drop_incomplete and interval.endswith("d") and len(data) > 1:
        now_ex = pd.Timestamp.now(tz=tz) if tz is not None else pd.Timestamp.now(tz="America/New_York")
        last_local_date = data.index[-1].date()
        # Drop only a *forming* bar: dated today while the session is open, or
        # any bar dated in the future (clock/source glitch).
        if last_local_date > now_ex.date() or (
            last_local_date == now_ex.date() and _is_session_open(now_ex)
        ):
            data = data.iloc[:-1]
            dropped_forming = True

    # ---- Normalise the index (tz-naive, sorted, de-duplicated) ------------
    data.index = pd.to_datetime(data.index)
    if getattr(data.index, "tz", None) is not None:
        data.index = data.index.tz_localize(None)
    data = data[~data.index.duplicated(keep="last")].sort_index()
    data = data.dropna(subset=["Close"])

    if "Adj Close" not in data.columns:
        data["Adj Close"] = data["Close"]

    # ---- Validate (fails loudly on bad/stale data) ------------------------
    warnings = validate_history(data, ticker, raise_on_stale=raise_on_stale)

    data.attrs.update(
        source=source,
        adjustment=settings.price_adjustment,  # "raw" = split-adj, div-unadj
        last_bar=str(data.index[-1].date()),
        rows=len(data),
        dropped_forming_bar=dropped_forming,
        warnings=warnings,
    )
    for w in warnings:
        print(f"[DATA WARN] {ticker}: {w}")

    return data


# --------------------------------------------------------------------------- #
# Diagnostic helper — verify against TradingView yourself
# --------------------------------------------------------------------------- #
def market_data_diagnostics(ticker: str) -> dict:
    """
    Print and return a side-by-side diagnostic for *ticker* so you can check the
    app's numbers against TradingView / Investing.com / Barchart.

    Reports: source, adjustment mode, latest *closed* bar date + OHLC, row
    count / date range, recent corporate actions, and the live-quote vs
    last-close delta (which are different by design — live tick vs EOD close).
    """
    out: dict = {"ticker": ticker.upper()}

    try:
        hist = get_history(ticker, raise_on_stale=False)
        last = hist.iloc[-1]
        out.update(
            source=hist.attrs.get("source"),
            adjustment=f"{hist.attrs.get('adjustment')} (Close = split-adjusted, dividend-UNADJUSTED)",
            rows=len(hist),
            date_range=f"{hist.index[0].date()} -> {hist.index[-1].date()}",
            last_bar_date=str(hist.index[-1].date()),
            last_close=round(float(last["Close"]), 4),
            last_adj_close=round(float(last["Adj Close"]), 4),
            dropped_forming_bar=hist.attrs.get("dropped_forming_bar"),
            warnings=hist.attrs.get("warnings", []),
        )
        if "Stock Splits" in hist.columns:
            recent = hist["Stock Splits"].tail(10)
            splits = {str(i.date()): float(v) for i, v in recent.items() if v}
            out["recent_splits"] = splits or "none"
    except MarketDataError as exc:
        out["history_error"] = str(exc)

    try:
        q = get_quote(ticker)
        out["live_quote"] = round(q.price, 4)
        out["live_quote_source"] = "finnhub (real-time tick)"
        if "last_close" in out:
            delta = q.price - out["last_close"]
            out["live_vs_lastclose_delta"] = round(delta, 4)
            out["live_vs_lastclose_pct"] = round(
                delta / out["last_close"] * 100, 3
            ) if out["last_close"] else None
    except MarketDataError as exc:
        out["quote_error"] = str(exc)

    print("\n=== MARKET DATA DIAGNOSTICS ===")
    for k, v in out.items():
        print(f"  {k:24s}: {v}")
    print("  note                    : live_quote (Finnhub tick) and last_close "
          "(yfinance EOD) are DIFFERENT things; they match only just after the close.")
    print("================================\n")
    return out


if __name__ == "__main__":  # pragma: no cover - manual diagnostic entry point
    import sys
    market_data_diagnostics(sys.argv[1] if len(sys.argv) > 1 else "AAPL")
