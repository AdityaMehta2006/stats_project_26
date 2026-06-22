# Presentation — Split into 3 Parts

The Tuesday presentation (`docs/PRESENTATION.pdf`) divided into three balanced
segments, each with the topics it covers. Use this to share speaking time or to
structure the talk into a beginning, middle, and end.

---

## Part 1 — The Idea & the Setup
*"What are we studying, why, and with what data?"*

**Topics covered**
- **Title of the study** — Quantitative Anomalies as Market Opportunities.
- **The core idea** — the Efficient Market Hypothesis vs reality; an anomaly is an
  opportunity seen from the other side.
- **Objectives** — the five objectives (macro-driver, risk-regime, mean-reversion,
  opportunity synthesis, accessibility), each framed as an opportunity.
- **Motivation** — why the topic: anomalies made tangible, risk reframed as
  opportunity, statistics + local AI, learning value.
- **Data & APIs used** (in place of questionnaire + sample):
  - Yahoo Finance (`yfinance`), FRED, DBnomics backup
  - our FastAPI backend endpoints, and the local AI API.

**Maps to PDF sections:** 1 (Title), 2 (Objectives), 3 (Motivation), 4 (Data & APIs).

---

## Part 2 — The Methods & What Works Today
*"How do we detect each anomaly, and what does the pilot show?"*

**Topics covered**
- **The three analysis pillars:**
  - Pillar 1 — Macro Factor & Lag Regression (OLS with lags, Granger causality).
  - Pillar 2 — GARCH & Volatility Clustering (time-varying risk, fat tails).
  - Pillar 3 — Forex Pair Trading (cointegration, z-score, mean reversion).
- **The recommendation engine** — "stats detect, AI explains"; four detectors,
  severity ranking, confidence.
- **Pilot study results** — validated data pipeline; sample findings on the S&P 500
  (macro R² ≈ 0.64; GARCH persistence ≈ 0.9955, kurtosis ≈ 16; USDCHF/USDJPY
  cointegrated p ≈ 0.008); local AI note in ≈4 s on the GPU.
- **Modules built so far** — backend (data loader, three pillars, recommender, LLM
  client, API) and frontend (five tabs + shared components).

**Maps to PDF sections:** 5 (Pilot Study), 6 (Modules Built So Far), plus the
methods behind each pillar.

---

## Part 3 — Decision Engine & the Road Ahead
*"How does the engine decide, and where is this going?"*

**Topics covered**
- **Decision engine: rules-based vs LLM-based** — the comparison (determinism,
  explainability, numbers, flexibility, speed, offline), and our hybrid with a
  toggle; the planned LLM decision-maker mode with guardrails.
- **Future plans — expanding the opportunity engine:**
  - Options & Black–Scholes (implied vs model volatility = vol mispricing).
  - Valuation — "is the stock bloated / overpriced?" (P/E, P/B, PEG vs history/peers).
  - More lenses — momentum, oversold bounce, volatility squeeze, correlation-regime
    shift, seasonality, alpha vs beta, unusual volume, risk budgeting.
- **Closing** — the layman one-liners for each anomaly (the Appendix), and the
  research gap we address (integration, interpretation, actionability).

**Maps to PDF sections:** 7 (Future Plans), 8 (Decision Engine: Rules vs LLM),
Appendix.

---

### Suggested timing (for a ~15-minute talk)
- Part 1 — ~5 min (sets up the problem and data)
- Part 2 — ~6 min (the substance: methods + working results)
- Part 3 — ~4 min (design choice + vision)
