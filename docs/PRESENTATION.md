# Progress Presentation — Tuesday

**Project:** QuantAnomalies

---

## 1. Title of the Study

**Quantitative Anomalies as Market Opportunities — A Statistical & AI Dashboard
for Equity and Forex Markets**

In plain terms: textbook finance says markets are "efficient" — prices already
reflect everything, risk never changes, and nothing is predictable. Reality is
messier, and those cracks in the theory are recurring patterns called
**anomalies**. Our project hunts for those anomalies and reframes them as
**opportunities**: places where the odds may tilt in a careful observer's favour.

---

## 2. Objectives of the Study

Each objective targets one well-known market anomaly and turns it into a usable
opportunity signal.

1. **Macro-driver opportunity.** Measure *which* macroeconomic forces (interest
   rates, inflation, the fear index, oil, gold, the dollar) move an asset's
   returns — and crucially with *what time delay*. If a driver acts weeks later,
   that lag is a window to anticipate moves.

2. **Risk-regime opportunity.** Model how risk itself rises and falls over time
   (volatility clustering) and detect that crashes happen far more often than a
   bell curve predicts (fat tails). Knowing you are entering a "stormy" regime is
   a chance to cut risk early — or to recognise unusually cheap calm.

3. **Mean-reversion opportunity.** Find pairs of currencies whose prices are
   tethered over the long run (cointegration), then flag when they drift
   unusually far apart — history says the gap tends to snap back. This is the
   basis of market-neutral "statistical arbitrage".

4. **Opportunity synthesis (the recommendation engine).** Combine all the above
   into one automated scanner that ranks what is unusual or actionable *right
   now*, and uses a **local AI analyst** to explain each finding in plain English.

5. **Accessibility & robustness.** Make it work for *any* ticker the user types,
   on a reliable data pipeline, presented through a clear, interactive dashboard.

---

## 3. Motivation for Selecting the Topic

- **The anomalies are real and well-studied, but rarely made tangible.** Lagged
  macro effects, volatility clustering, fat tails, and cointegration all appear in
  finance literature; we wanted to make them *visible and actionable* rather than
  abstract equations.
- **Reframing risk as opportunity.** The same statistics used to warn about risk
  can also point to opportunity — we wanted a tool that does both.
- **Bridging statistics and modern AI.** We combine classic econometrics
  (regression, GARCH, cointegration) with a **local large language model** that
  turns numbers into a readable analyst note — private, free to run, and on our
  own GPU.
- **Learning value.** The project spans real statistical modelling, live financial
  data engineering, full-stack web development, and on-device AI.

---

## 4. Data & APIs Used
*(In place of a questionnaire and a survey sample — our "instrument" is a set of
financial-data APIs, and our "sample" is the live market history they return.)*

**A. External data-source APIs (how we collect raw market data)**
- **Yahoo Finance** (via the `yfinance` library) — daily price history (2015–2025)
  for any equity, index, currency pair, future, or crypto. Examples we use:
  `^GSPC` (S&P 500), `^VIX` (volatility index), `CL=F` (oil), `GC=F` (gold),
  `^TNX` (10-year Treasury yield), `DX-Y.NYB` (US dollar index), and 45 forex pairs.
- **FRED — U.S. Federal Reserve Economic Data** — macroeconomic series: CPI
  (inflation), Fed Funds Rate, and Unemployment. A free mirror, **DBnomics**, is a
  built-in backup so a single outage never stops the study.

**B. Our own analysis API (FastAPI backend)** — turns raw data into results:
- `/api/macro-regression/*` — regression, Granger-causality, correlation, time series
- `/api/garch/*` — volatility model, clustering tests, return distribution
- `/api/pairs/*` — cointegration tests, best-pair spread & signals, correlation
- `/api/recommendations` — the ranked opportunity scan
- `/api/llm/info` — status of the local AI analyst

**C. Local AI API** — an on-device `llama.cpp` server (OpenAI-compatible) running
the **Qwen3-4B** model on our **NVIDIA RTX 4050 GPU**, used to explain the
detected opportunities in plain language. No data leaves the machine.

---

## 5. Pilot Study Conducted to Date

We have a **working end-to-end prototype** and have validated it on real data.

**Data pipeline (validated):**
- Live downloads working for all sources; a corrupted early cache (the volatility
  and oil series had been mixed up) was found and fixed. Every series now sits in
  its correct real-world range (e.g. VIX 9–83, oil −37 to 124, 10-yr yield 0.5–4.9%).

**Three analysis pillars (working, with sample findings on the S&P 500):**
- *Macro:* macro factors explain about **64%** of monthly return variation (R²≈0.64);
  the model surfaces which factors are statistically significant and at what lag.
- *Volatility:* GARCH "persistence" ≈ **0.9955** (shocks fade very slowly) and
  excess kurtosis ≈ **16** (strong fat tails) — both confirm risk is *not* constant
  and crashes are under-estimated by the normal curve.
- *Pairs:* among major forex pairs, **USDCHF/USDJPY** tested cointegrated
  (p ≈ 0.008) with a mean-reversion half-life around 64 days.

**Recommendation engine (v1 working):**
- Four detectors (volatility regime, tail move, trend, forex mean-reversion) rank
  opportunities by severity and assign a confidence score.
- The local AI produces a grounded plain-English note in **~4 seconds on the GPU**
  (≈28 tokens/sec), citing only the real detected numbers.

**Dashboard (working):**
- Interactive web app: search any ticker, pick forex pairs, switch time ranges,
  and read explained results across five tabs (Overview, Opportunities, Macro,
  GARCH, Pair Trading).

**In short:** the "pilot" confirms the data, the statistics, the AI explanation
layer, and the user interface all work together on live markets. Next steps
(standardised comparisons, an options/Black–Scholes module, a back-test of the
signals) are tracked in `TODO.md`.

---

## Appendix — Anomalies explained in one line each (layman)

- **Lagged macro effect:** *"News ripples through markets over weeks, not
  instantly — know the lever and the delay, and you can position ahead."*
- **Volatility clustering:** *"Calm days cluster, and so do wild days — storms
  arrive in groups, giving you warning to manage risk."*
- **Fat tails:** *"Extreme crashes happen much more often than the textbook bell
  curve says — plan for them."*
- **Cointegration / pairs:** *"Two currencies on one leash: when they drift far
  apart, they usually snap back — bet on the gap closing, up market or down."*
