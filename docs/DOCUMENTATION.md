# QuantAnomalies — Project Documentation & Story

> A statistical and AI-assisted dashboard that hunts for **market anomalies** in
> equities and forex and reframes them as **opportunities** — explained in plain
> English by a local AI analyst.

---

## 1. The Big Idea (in plain terms)

Classic finance theory (the "Efficient Market Hypothesis") makes three tidy
assumptions: prices instantly reflect all information, risk is roughly constant,
and you cannot predict returns. Decades of evidence show reality is messier — and
those mismatches are recurring, studied patterns called **anomalies**.

Our insight: an anomaly is just an **opportunity** seen from the other side. The
same crack in the theory that academics flag as "the model is wrong here" is
exactly where a careful observer might find an edge. QuantAnomalies makes three of
these anomalies visible, measurable, and actionable, then layers an AI analyst on
top to explain what it finds.

The three anomalies, as opportunities:

| Anomaly (textbook says…) | Reality (opportunity) | Layman analogy |
|---|---|---|
| Prices react instantly | Macro news ripples over **weeks** (lagged effects) | A stone in a pond — the ripple takes time to reach the edge |
| Risk is constant | Volatility **clusters**; tails are **fat** | Storms come in clusters, and big ones hit more often than forecast |
| Returns are unpredictable | Some pairs are **cointegrated** (tethered) | Two dogs on one leash — they wander but snap back together |

---

## 2. What the Project Does

A full-stack web application with seven areas:

1. **Overview** — what the project is and how to navigate it.
2. **Opportunities** — the recommendation engine: 13 detectors feeding a
   rule-based decision layer that produces a stance, conviction and position
   size, with an optional AI analyst note.
3. **Macro Regression** — which macro forces drive an asset, and with what lag.
4. **GARCH Volatility** — how risk changes over time, and how fat the tails are.
5. **Pair Trading** — cointegrated forex pairs and mean-reversion signals.
6. **Options Pricing** — Black-Scholes, jump-diffusion and stochastic volatility
   priced on live market inputs, plus the implied-volatility smile.
7. **Stochastic Processes** — the SDEs underneath the other pillars, with
   convergence and variance-reduction studies.

Everything is **dynamic**: the user can type any ticker (stock, index, crypto,
future) or pick any combination of 45 forex pairs, and the analysis regenerates.

---

## 3. Architecture

```
            ┌─────────────────────────────┐
            │   React + Vite frontend     │   7 tabs, Recharts, framer-motion
            │   (quant-terminal UI)       │   time filters, info tooltips
            └──────────────┬──────────────┘
                           │  HTTP (JSON) — 38 endpoints
            ┌──────────────▼──────────────┐
            │   FastAPI backend (Python)  │
            │   5 analysis pillars +      │
            │   13 detectors +            │
            │   rule-based decision layer │
            └───┬───────────────┬─────────┘
                │               │
   ┌────────────▼───┐   ┌───────▼────────────┐   ┌──────────────────────┐
   │ Data layer     │   │ Local LLM (GPU)    │   │ External data APIs    │
   │ yfinance +FRED │   │ llama.cpp server   │   │ Yahoo Finance, FRED,  │
   │ CSV cache with │   │ Qwen3-4B, Vulkan   │   │ DBnomics (backup)     │
   │ staleness guard│   │ (optional)         │   │                       │
   └────────────────┘   └────────────────────┘   └──────────────────────┘
```

**Stack:** Python · FastAPI · pandas/numpy · statsmodels · arch · scipy ·
React 19 · Vite · Recharts · framer-motion · llama-cpp / llama.cpp (GPU).

### How the pillars connect

The pillars are not independent exercises — four explicit couplings tie them
into one system:

| Coupling | Mechanism |
|---|---|
| GARCH → Options | The GARCH volatility forecast, aggregated over the option's life, *is* the sigma fed to Black-Scholes. An option is a claim on future variance, so a forecast is the correct input rather than a historical average. |
| GARCH → Heston | `kappa = -252 * ln(alpha+beta)`, `theta` = GARCH long-run variance, `v0` = current conditional variance. The two describe the same volatility dynamics in discrete and continuous time. |
| Pairs → Stochastic | The pair spread is fitted as an Ornstein-Uhlenbeck process; its half-life `ln(2)/kappa` independently reproduces the value the pairs module computes from an AR(1) regression. |
| Options → Recommender | Market implied volatility minus the GARCH forecast is the variance risk premium, which becomes one of the 13 detector signals. |

---

## 4. The Five Pillars

### Pillar 1 — Macro Factor & Lag Regression  ·  `backend/analysis/macro_regression.py`
**Question:** Which macro forces move an asset, and how quickly?
**Method:** Build a monthly dataset of the asset's return plus eight factors
(VIX, oil, gold, US dollar, 10-yr yield, Fed Funds, inflation, unemployment). Run
OLS regression with **time lags** (0–3 months), Granger-causality tests, and a
lagged-correlation heatmap.
**Opportunity:** If a factor predicts returns weeks ahead, that lag is a window to
position before the move. (Sample: S&P 500 R²≈0.64 monthly.)

### Pillar 2 — GARCH & Volatility Clustering  ·  `backend/analysis/garch.py`
**Question:** How does risk change over time, and are crashes under-estimated?
**Method:** Fit a **GARCH(1,1)** model to daily returns to estimate day-by-day
volatility; test clustering via autocorrelation of squared returns (Ljung-Box);
test normality (Jarque-Bera, QQ plot, skew/kurtosis).
**Opportunity:** A high-volatility regime is a cue to reduce risk; calm regimes can
precede expansions. Fat tails warn that standard risk measures understate danger.
(Sample: persistence ≈ 0.9955, excess kurtosis ≈ 16 — strongly non-normal.)

### Pillar 3 — Forex Pair Trading  ·  `backend/analysis/pairs.py`
**Question:** Which currency pairs are tethered, and when is the gap tradeable?
**Method:** Engle-Granger **cointegration** across all pair combinations; for the
best pair, build a hedge-ratio **spread**, standardise it to a **z-score**, and
generate buy/sell/exit signals (enter beyond ±2, exit near 0); estimate the
mean-reversion **half-life**.
**Opportunity:** Market-neutral "statistical arbitrage" — profit from the gap
closing regardless of overall market direction. (Sample: USDCHF/USDJPY
cointegrated, p ≈ 0.0075, hedge ratio −0.339, half-life ≈ 69 days.)

### Pillar 4 — Options Pricing  ·  `backend/analysis/advanced_options.py` · `market_options.py`
**Question:** What is an option worth, and what does its price reveal that the
return series alone does not?
**Method:** Four closed-form models sharing one engine (Black-Scholes-Merton for
equities, Garman-Kohlhagen for FX, Black-76 for futures, Bachelier for normal
dynamics — they differ only in the carry term), first- and second-order Greeks,
a Cox-Ross-Rubinstein lattice with American early exercise, and two models that
admit a volatility smile: the Merton jump-diffusion Poisson series and the
Heston characteristic-function integral. Every Monte Carlo estimator is paired
with the exact price for the same model.
**Market wiring:** live spot, a continuously-compounded rate derived from `^TNX`,
the actual dividend yield, a GARCH volatility forecast matched to the option's
maturity, jump parameters fitted from the return distribution's own tails, and
Heston seeded from GARCH.
**Opportunity:** The gap between market implied volatility and the GARCH
forecast is the **variance risk premium**. (Sample: AAPL 33.1% implied vs 28.8%
forecast, a +4.3 point premium.)

### Pillar 5 — Stochastic Processes  ·  `backend/analysis/stochastic.py`
**Question:** What mathematics underlies the other pillars?
**Method:** Simulation engines for the Wiener process, geometric Brownian
motion, Ornstein-Uhlenbeck, Cox-Ingersoll-Ross, Merton jump-diffusion and
Heston, each reporting theoretical moments alongside empirical ones as a
self-check. Includes an Euler-vs-Milstein convergence study and a
variance-reduction comparison (antithetic, control variate, both).
**Connection:** The pair-trading spread is fitted as an Ornstein-Uhlenbeck
process, and its half-life reproduces Pillar 3's independently derived value.

---

## 5. The Decision Layer — "stats detect, rules decide, LLM explains"
`backend/analysis/recommender.py` · `decision.py` · `backend/llm_client.py`

Three strictly separated layers, which is the design's main claim.

**1. Detection** — 13 deterministic detectors emit signals with a 0–1 severity:

| Family | Detectors |
|---|---|
| Price / trend | `trend`, `breakout`, `momentum` (12-1), `relative_performance` |
| Mean reversion | `mean_reversion` (RSI + displacement), `pairs_opportunity` |
| Volatility | `volatility_regime`, `tail_event`, `options_mispricing` |
| Macro | `macro_dislocation` |
| Flow / context | `volume_anomaly`, `correlation_regime`, `seasonality` |

**2. Decision** (`decision.py`) — nets the signals into one stance, conviction
and position size:
- weights each signal by **reliability × severity**;
- **discounts redundant signals** within a family (0.45^rank), so three views of
  the same price move do not count as three confirmations;
- separates **direction** (`agreement × strength`, where strength saturates via
  `tanh`) from **size** (a risk overlay driven by risk-off signals and the
  volatility percentile);
- **demotes conviction on genuine conflict** rather than averaging opposing
  evidence into a confident-looking middle;
- emits a full audit trail naming every step.

**3. Explanation** — the LLM receives the detections *and* the computed decision
and writes prose. It never computes, ranks, or invents a number, and cannot
change the stance, conviction or size. The system's output is therefore
unchanged whether or not a model is available.

---

## 5b. The Fusion Engine — `backend/engine.py`

`decision.py` above answers "what stance, and what size". This layer answers
"where does the evidence point, how firmly, and how fast can we say so" — it is
what drives the verdict gauge and the streamed narration. Both read the same
detections, so they cannot disagree about the inputs. The pillars are untouched
and still individually callable.

**Eight of the thirteen detectors** feed it (`analysis/recommender.py`):
volatility regime, tail event, macro dislocation, pairs opportunity, trend,
breakout, relative performance, options mispricing. The remainder run in the
`/api/recommendations` path.

**Normalisation.** The detectors speak eight different direction vocabularies
("uptrend", "above_model", "long spread", "compressed", "rich"…). A `POLARITY`
map collapses them onto one bull/bear/neutral axis so they can be compared at
all. Volatility and tail readings are routed to a **separate risk axis** so a
vol spike can never fake a directional call. Vol mispricing is mapped to
polarity 0 and kept off the risk axis too: expensive option premium is a
relative-value read, so it reports itself without moving the verdict either way. Each signal also carries a
`reliability` derived from its own statistics — cointegration p-value, macro
R², GARCH sample size — never invented.

**Fusion.** Weight `w = severity × reliability`, then:

```
tilt        = (bull − bear) / (bull + bear)      direction, −1..+1
agreement   = 1 − min(bull,bear)/max(bull,bear)  how one-sided
mass        = 1 − exp(−total / 2)                saturating evidence weight
conviction  = mass × (0.4 + 0.6 × agreement)
```

Strength beats count, nothing pins to 1.0 on noise, and a signal pointing the
other way actively *lowers* conviction. This replaced an earlier
`0.2 + 0.15·n + 0.3·top` line that was dominated by signal count and clamped
to 1.0 the moment six of anything showed up.

**Tiered scan.** Price detectors run broad and cheap; one cointegration sweep
serves the whole FX basket; GARCH is cached on `(ticker, last_data_date)` so
it refits once per trading day regardless of request volume. A detector that
fails is recorded in `diagnostics`, never raised — one dead factor costs one
signal, not the verdict. Measured warm: feed **11 ms**, per-asset **4.5 ms**,
off-universe cold **0.9 s**.

**Endpoints:** `/api/engine/{feed,asset,narrate,status}`, alongside the
unchanged per-pillar routes used for drill-down.

---

### The AI layer — "stats detect, the LLM explains"

The model receives the computed detections as compact JSON and is instructed
to use only those numbers. It never feeds back into the fusion. Three things
make that verifiable rather than merely asserted:

- **Stance-first streaming.** The prompt demands a `STANCE:` line before the
  prose, so the model's labelled opinion lands after ~10 tokens and the
  reasoning streams beneath it instead of blocking for ~20 s.
- **The model may disagree.** Its stance renders *beside* the computed stance,
  so a divergence is visible rather than hidden.
- **A number guardrail.** `unverified_numbers()` checks every figure in the
  narrative against the evidence supplied; anything unmatched surfaces in the
  UI as a grounding badge.

Runtime is a local `llama.cpp` server (Qwen3-4B) on an RTX 4050 via Vulkan,
with an in-process CPU fallback and a rules-only path if no model is up. Nothing
leaves the machine.

---

---

## 6. Data Pipeline & Robustness  ·  `backend/data_loader.py`

- **Sources:** Yahoo Finance (prices) and FRED (macro), cached as CSV so the app
  runs offline once data is fetched.
- **Resilience we built in:**
  - FRED downloads were failing (HTTP 403) — fixed with a proper request header,
    plus a **DBnomics** fallback mirror.
  - The flaky FRED 10-year series was replaced by Yahoo's `^TNX`.
  - `build_macro_dataset` is **fault-tolerant**: if one factor source fails, that
    factor is skipped instead of breaking the whole study.
  - A data-integrity bug (the VIX and oil caches had been seeded with the wrong
    series) was detected and corrected; all series now validate to real ranges.
  - **Cache staleness guard.** The end date of the download window was previously
    hardcoded, so once the cache was written it was served indefinitely — every
    "latest price" in the app silently aged. `END` now tracks the current date,
    and a cached series older than `STALE_AFTER_DAYS` (7) triggers a refetch. If
    the refetch fails the stale cache is still served rather than raising, but
    the staleness is exposed through `data_freshness()` so it is visible instead
    of hidden. Monthly macro series are exempt, since official statistics are
    published with a genuine multi-week lag.

---

## 6b. Verification

The numerical work is checked rather than trusted. Each check is computed at
request time and returned in the API response, so it is visible in the UI:

| Check | Method | Result |
|---|---|---|
| Put-call parity | model-free arbitrage identity | violation `0.0` |
| Greeks | central finite differences (error `O(h²)`) | max difference `4.6e-7` |
| GBM Monte Carlo | vs analytic Black-Scholes | within 3 standard errors |
| Merton Monte Carlo | vs the exact Poisson-weighted series | Δ 0.053, SE 0.039 |
| Heston Monte Carlo | vs Fourier inversion of the characteristic function | Δ 0.067, SE 0.050 |
| Heston characteristic function | vol-of-vol → 0 must collapse to Black-Scholes | Δ `3e-6` |
| Binomial lattice | error against `1/N` | halves per step doubling |
| American call, no dividend | premium must be exactly zero | `0.0` |
| Longstaff-Schwartz | vs an 800-step lattice | Δ 0.023, SE 0.029 |
| Black-Scholes smile | implied-vol spread across strikes must be zero | `0.000` |

The Heston check is the strongest: setting vol-of-vol to zero must reduce the
model to Black-Scholes, and agreement to six decimals validates the complex
arithmetic, branch-cut handling and quadrature against a formula derived by an
entirely different route.

Variance-reduction efficiency is measured rather than asserted: plain Monte
Carlo 1.00×, antithetic 1.97×, control variate 5.01×, both combined **19.27×**.

---

## 7. The Dashboard (UI)

- A dark **"quant terminal"** theme (deep navy, teal/cyan data, gold highlights),
  custom **SVG icon set** (no emojis), and a subtle SVG grid backdrop.
- **Hover info-tooltips** explain every metric in plain English.
- **Time-range filters** (1M–All) on every time-series chart, with the y-axis
  auto-scaling to the visible window.
- **framer-motion** polish: animated tab transitions, sliding active indicators,
  and animated confidence/severity bars.

---

## 8. The Story So Far (how we got here)

1. **Revived a broken project.** The app wouldn't run — the `python` command was
   pointing at a dead path; we located the working Anaconda interpreter and got it
   running again.
2. **Fixed the data.** Repaired FRED access, added fallbacks, swapped the flaky
   10-yr source to Yahoo, and cleaned corrupted caches so every value is sane.
3. **Enriched the analysis.** Added gold and the dollar index as macro factors and
   made the dataset builder fault-tolerant.
4. **Redesigned the interface.** New professional theme, SVG icons, explanatory
   copy, hover tooltips, and a stealth SVG background.
5. **Built the recommendation engine.** Four anomaly/opportunity detectors plus a
   provider-agnostic AI client.
6. **Put the AI on the GPU.** Switched the local model from CPU to the RTX 4050 via
   the bundled Vulkan `llama.cpp` server — a ~6× speed-up (25s → ~4s).
7. **Added time filters and motion.** Interactive ranges and a proper animation
   pass across the app.
8. **Added the options pillar.** Four closed-form models on one engine, full
   Greeks with a finite-difference audit, a binomial lattice with early
   exercise, Merton and Heston in closed form *and* Monte Carlo so each
   validates the other, Longstaff-Schwartz for American options, and the
   implied-volatility smile — the result that shows why Black-Scholes alone is
   insufficient.
9. **Wired the options models to the market.** Live spot, a properly converted
   continuously-compounded rate, the real dividend yield, a GARCH volatility
   forecast matched to maturity, jump parameters fitted from realised tails, and
   Heston seeded from GARCH — making the volatility pillar and the options
   pillar one model rather than two.
10. **Added the stochastic-processes pillar.** The SDEs made explicit, with
    Euler-vs-Milstein convergence, variance reduction, and an Ornstein-Uhlenbeck
    fit to the live pair spread that independently reproduces Pillar 3's
    half-life.
11. **Completed the decision layer.** Six further detectors (13 total) and a
    genuine aggregation step: reliability weighting, redundancy discounting,
    conflict demotion, and position sizing with a full audit trail.
12. **Fixed six real defects found by testing**, the most serious being a
    hardcoded end date that had left every cached price series 208 days stale,
    and a dividend-yield unit mismatch that applied a 32% yield to a stock
    paying 0.32%.

---

## 9. Known Limitations

Stated deliberately, since they bound what the project currently claims:

1. **No backtest.** Signals are detected but never evaluated for profit-and-loss,
   Sharpe ratio or drawdown. Everything is in-sample. This is the largest gap —
   "opportunities" are not yet evidence.
2. **Multiple testing is uncorrected.** 15 pair combinations are searched and the
   best reported; `p = 0.0075` does not survive a Bonferroni threshold of
   `0.05/15 = 0.00333`. The economic rationale (both legs are USD-based
   safe-haven currencies) is what supports the result, not the p-value alone.
3. **Decision weights are stated judgement, not fitted.** Deliberately so — with
   a few hundred monthly observations, fitting them would overfit more
   convincingly than it would inform.
4. **No transaction costs** are modelled anywhere.
5. **GARCH long-run variance is ill-conditioned** when persistence approaches 1
   (ours is 0.994). Short-horizon forecasts are reliable; the long-run level is
   indicative only. The code emits this caveat itself and the UI displays it.
6. **A single 10-year rate is used for all option maturities**; a bootstrapped
   yield curve would be correct. FX policy rates are hardcoded approximations.
7. **Heston is seeded from GARCH rather than calibrated to option prices.** This
   is intentional — calibrating to prices would make the variance-risk-premium
   comparison circular — but it means the model smile is a prediction, not a fit.
8. **No unit-test suite.** Validation is via the in-response checks in §6b, which
   are real and visible but are not a test suite.

---

## 10. What's Next

Tracked in `docs/TODO.md`: a walk-forward **backtest** of the decision engine
(the highest-value next step), multiple-testing correction for pair selection,
transaction-cost modelling, a bootstrapped yield curve, KPSS and structural-break
tests to complement ADF, and a pytest suite around the analytic checks.

---

## 11. How to Run

```bash
# Backend — main.py uses flat imports, so it is served with --app-dir
pip install -r backend/requirements.txt
python -m uvicorn main:app --app-dir backend --port 8000     # → localhost:8000/docs

# Local AI, optional but recommended
llama-server.exe -m <Qwen3-4B gguf> -ngl 99 -c 4096 --port 8080

# Frontend
cd frontend && npm install && npm run dev                    # → localhost:5173
```

The optional local LLM is provider-agnostic; if none is configured the
rules-based decision layer runs unchanged and only the prose note is absent.
