# QuantAnomalies — Roadmap / TODO

Forward-looking plan. Items are grouped and tagged **P0** (next), **P1** (soon),
**P2** (nice-to-have). Done items are listed at the bottom for context.

---

## 1. Decision Engine (headline feature) — P0

A layer that turns the three pillars' raw statistics into a plain-English
**verdict with reasoning**, so a non-statistician can act on the dashboard.

**Inputs** (already produced by the API): macro OLS/Granger results, GARCH
parameters + clustering tests, cointegration + current z-score.

**Output shape** (proposed):
```json
{
  "ticker": "^GSPC",
  "verdict": "Moderately macro-driven, high-persistence risk, no pair trade yet",
  "confidence": 0.7,
  "reasoning": [
    {"pillar": "macro", "finding": "...", "evidence": "R²=0.64, VIX(lag0) significant"},
    {"pillar": "volatility", "finding": "...", "evidence": "persistence 0.9955, kurtosis 15.9"},
    {"pillar": "pairs", "finding": "...", "evidence": "USDCHF/USDJPY p=0.008, z=+1.2"}
  ],
  "mode": "rules"
}
```

### 1a. Rules-based engine (build first — deterministic, free, explainable)
- [ ] New module `backend/analysis/decision_engine.py` with
      `generate_decision(ticker, pairs, mode="rules")`.
- [ ] Pull metrics from existing analysis functions (don't recompute raw data twice).
- [ ] Threshold rules → statements, e.g.:
  - macro: `R² > 0.6` → "strongly macro-explained"; flag the factor with the
    largest **standardized** beta (see §2) as the dominant driver.
  - volatility: `persistence > 0.95` + Ljung-Box p<0.05 → "shocks persist, size for tail risk";
    `excess kurtosis > 3` → "fat tails — VaR understates risk".
  - pairs: `coint p<0.05` & `|z|>2` → BUY/SELL call; `|z|<2` → "watch, no entry".
- [ ] Produce a 0–1 confidence from how many tests agree.
- [ ] Endpoint `GET /api/decision?ticker=&pairs=` in `backend/main.py`.

### 1b. LLM engine (optional toggle — richer narrative)
- [ ] Mode `mode="llm"`: send the **structured metrics JSON** (not raw data) to the
      model and ask for an analyst-style note + recommendation.
- [ ] Use **Claude Opus 4.8** (`claude-opus-4-8`) via the Anthropic Messages API;
      API key from env var `ANTHROPIC_API_KEY` (never hard-code).
- [ ] Guardrails: instruct the model to cite only the numbers provided and not
      invent values; validate the response references real metrics before showing it.
- [ ] Keep rules-based as the default/fallback so the app works with no API key or no network.

### 1c. Frontend
- [ ] New "Insights" tab rendering the verdict as a report card: headline verdict,
      confidence meter, one reasoning card per pillar (with the cited evidence),
      and a rules-vs-AI toggle.

---

## 2. Proper scaling & normalization (make results meaningful) — P0

Right now several outputs are technically correct but hard to interpret because
inputs live on wildly different scales.

- [ ] **Standardize macro factors (z-score) before OLS.** Raw coefficients aren't
      comparable (VIX≈18 vs CPI_Change≈0.0025), so the coefficient bar chart is
      misleading. Report **standardized betas** so "which factor matters most" is
      meaningful; optionally show raw + standardized side by side.
- [ ] **Surface the dominant driver** (largest |standardized beta|) — feeds the
      decision engine.
- [ ] **Normalize forex prices before the spread/hedge ratio.** USDJPY≈150 vs
      EURUSD≈1.1 gives a near-zero hedge ratio (e.g. −0.002) that looks broken.
      Use log-prices (or index each series to 100) so the hedge ratio and spread
      are interpretable, and label units on the spread chart.
- [ ] **Consider VIX as a change/log-level** rather than raw level for the
      regression (stationarity); document the choice.
- [ ] **Consistent display units** across the UI: returns in %, yields in %,
      p-values in scientific notation when tiny, fixed decimal places via a shared
      `formatNumber` helper.

---

## 3. UI polish — P1

- [ ] **Shared ticker state.** Each tab currently keeps its own `ticker` (defaults
      to ^GSPC), so analyzing AAPL on Macro doesn't carry to GARCH. Lift ticker to
      `App.jsx` (or context) so the selection is consistent across tabs.
- [ ] Loading **skeletons** per card instead of one full-panel spinner.
- [ ] Axis **unit labels** and better tick formatting on every chart.
- [ ] Empty / partial states (e.g. a factor was skipped, or a pair returned no signals).
- [ ] "Data as of <date>" freshness indicator; manual **refresh data** button that
      busts the CSV cache for the current ticker.
- [ ] Light-mode variant of the theme (toggle), reusing the `theme.js` tokens.
- [ ] Mobile pass on tables (horizontal scroll affordance) and the heatmaps.

---

## 4. Data & robustness — P1

- [ ] **Cache integrity guard.** The original caches were cross-seeded (VIX held
      S&P, oil held VIX). Add a light sanity check on load (e.g. assert a cached
      series sits in a plausible range / matches its ticker) and auto-refetch if not.
- [ ] Store a small **metadata sidecar** per cache (ticker, fetch date, row count)
      to detect staleness and mismatches.
- [ ] Wrap the `pandas_datareader` FRED fallback with a timeout (it can hang).
- [ ] Unit tests for `data_loader` (ranges, NaN handling, empty-column drop) and a
      tiny pytest smoke suite over every endpoint.
- [ ] Pin exact dependency versions; document the Anaconda interpreter requirement
      in a README (`python` on this machine is the broken Store stub).

---

## 5. Analysis depth — P2

- [ ] Rolling / out-of-sample regression (does macro sensitivity change over time?).
- [ ] GARCH variants (EGARCH/GJR for leverage effect) in the comparison table.
- [ ] Backtest the pair-trading signals (PnL, Sharpe, drawdown) instead of only
      listing signals.
- [ ] Multiple-testing correction for the cointegration matrix (many pairs → false
      positives).
- [ ] Let users pick the macro factor set and lag depth from the UI.

---

## Done (for context)
- Fixed broken FRED downloads (User-Agent) + added DBnomics fallback.
- 10Y yield sourced from Yahoo `^TNX` (skips flaky FRED DGS10).
- Added Gold + US Dollar Index factors; made `build_macro_dataset` fault-tolerant.
- Cleaned corrupted equity caches (VIX/oil were cross-seeded) and restored EURGBP.
- Frontend redesign: "quant terminal" theme, SVG icon set, hover info-tooltips,
  explanatory copy, stealth SVG background.


## Make sure to have news-articles for that day when clicked on chart
## make charts with time filter and make it scale properly 
## Add feature to toggle between different assets
