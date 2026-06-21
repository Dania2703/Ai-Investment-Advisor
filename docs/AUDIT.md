# Phase 1 — Full Engine Audit

This report documents the defects that caused the recommendation engine to
print **Strong Buy** when TradingView / Investing.com / Barchart showed
**Sell** or **Neutral**, and how each is addressed in the refactor.

The findings are grouped into (A) defects already fixed in the indicator/data
layer, and (B) defects in the *scoring logic* that this phase fixes.

---

## A. Indicator & data-layer defects (fixed in `indicators.py` / `market_data.py`)

| # | Finding | Impact | Fix |
|---|---------|--------|-----|
| 1 | **Wrong smoothing convention.** The old engine used `pandas-ta` defaults, which do not consistently use Wilder's RMA for RSI/ATR/ADX. | RSI/ADX drifted from TradingView by several points → wrong momentum/trend reads. | Native implementations using **Wilder's RMA** (`alpha=1/period`) for RSI/ATR/ADX, **EMA** for MACD, **population stdev** for Bollinger. See `indicators.py`. |
| 2 | **Look-ahead bias from the forming bar.** The latest (still-forming) daily candle was included. | The most recent RSI/MACD reflected an intraday partial bar, not a closed bar — unstable, non-reproducible signals. | `get_history` drops the in-progress final daily bar (`drop_incomplete_bar`). |
| 3 | **Insufficient history.** `period="1y"` (~252 bars) gives only ~50 valid SMA200 points and poor Wilder warm-up. | SMA200 / ADX unreliable early; trend misread. | Default `period="2y"`; `min_history_bars` gate surfaces low-data warnings. |
| 4 | **Timezone / alignment.** tz-aware index, possible duplicate/unsorted rows. | Rolling/EWMA windows can misalign; chart timestamps locale-dependent. | Index normalised to naive, sorted, de-duplicated; NaN closes dropped. |
| 5 | **NaN handling.** `_latest()` only guarded some series. | Under-warmed indicators could read as `0`/`None` silently and be scored as bearish. | Every indicator keeps explicit warm-up NaNs; scoring treats missing categories by **renormalising weights**, never scoring them as 0. |
| 6 | **Mixed price sources.** Quote price (Finnhub) vs indicators (yfinance) could disagree. | Indicator/price inconsistency. | All indicators computed on one OHLCV series; quote shown separately. |

---

## B. Scoring-logic defects (fixed in this phase)

### 7. Score inflation via **double counting** of correlated trend signals
The trend category scored these as **independent** sub-signals:

```
Price > SMA50
Price > SMA200
SMA50 > SMA200
EMA20 > EMA50
EMA50 > EMA200
Price > EMA20
```

These are **highly collinear** — in any sustained uptrend they all fire
together. Counting them as six independent bullish votes meant a single
phenomenon (an uptrend) was counted ~6×, pushing the trend score to 100/100 and
dragging the whole recommendation to Strong Buy even when momentum, volume and
ADX disagreed. **This is the primary cause of the over-bullish bias.**

**Fix (Phase 3):** `correlation.py` automatically clusters signals whose
historical boolean series are correlated above a threshold and gives each
*cluster* a single combined weight (split within the cluster). Six collinear MA
relationships now contribute roughly the weight of **one** concept. Trend is
also hard-capped at **35%** of the total score.

### 8. Trend over-weighted (40%) and no risk term
Trend at 40% + double counting compounded the bias. There was no explicit
**risk** term to discount overextended/volatile setups.

**Fix (Phase 4):** factor weights rebalanced to
Trend **35%** · Momentum **25%** · Volume **15%** · Volatility **10%** ·
Sentiment **10%** · **Risk Adjustment 5%**, with each category exposing
`raw_score`, `normalized_score` and an explanation.

### 9. Confidence was a function of the score (not real uncertainty)
Confidence was derived almost entirely from "distance from neutral", so a
Strong Buy was *always* high-confidence — even when signals conflicted.

**Fix (Phase 5):** confidence is computed from **indicator agreement, data
quality, sentiment consistency, trend strength (ADX) and volatility** — fully
decoupled from the rating. You can now get *Strong Buy + Low Confidence*.

### 10. No disagreement detection
Conflicts (bullish trend + bearish momentum + weak ADX) were invisible and did
not affect the output.

**Fix (Phase 6):** `diagnostics.py` counts Bullish/Neutral/Bearish indicators
and flags specific conflicts, each of which **downgrades confidence** and is
surfaced to the user and to GPT.

### 11. Opaque contributions
The UI showed indicator values but not **how much each one moved the score**.

**Fix (Phase 7):** every signal carries an `effective_weight` and a signed
`contribution`; the contributions **sum to the final score**, shown in a table
(Indicator · Value · Signal · Weight · Contribution).

### 12. Rating bands too generous in the middle
Old bands made "Buy" start at 56 and never required strong agreement for
"Strong Buy".

**Fix (Phase 4):** bands tightened to
`0–20` Strong Sell · `21–40` Sell · `41–60` Hold · `61–80` Buy ·
`81–100` Strong Buy. "Strong Buy" now genuinely requires broad agreement.

### 13. No out-of-sample validation
There was no evidence the signals had any forward edge.

**Fix (Phase 9):** `backtest.py` replays the engine bar-by-bar (using the
look-ahead-free indicators) and reports 5/10/20-day forward returns, win rate
and signal accuracy per ticker.

---

## Net effect

The combination of (7) de-correlation, (8) the risk term + 35% trend cap, and
(12) tighter bands removes the systematic Strong-Buy inflation. A stock in a
long uptrend but with deteriorating momentum, weak ADX and elevated volatility
now lands in **Hold/Buy with reduced confidence and explicit conflict flags**,
instead of an unqualified Strong Buy — which is exactly the kind of nuance the
third-party screeners were showing.
