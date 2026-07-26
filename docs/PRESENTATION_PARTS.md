# Presentation — Split into 3 Parts

The Tuesday presentation (`docs/PRESENTATION.pdf`) divided into three parts of
**equal depth**. The three statistical pillars are deliberately split — one core
method per presenter — so no single part carries all the heavy content. Fixed
assignments: **Aditya opens**, and **Rithesh covers Black–Scholes** (kept
high-level). Everything else is balanced around those.

| Part | Presenter | Owns this pillar | Theme |
|------|-----------|------------------|-------|
| 1 | **Aditya** | GARCH volatility | Opening + GARCH + Valuation |
| 2 | **Jitvan** | Macro regression | Macro + the Engine |
| 3 | **Rithesh** | Pair trading | Pairs + Decision modes + Future |

---

## Part 1 — Aditya — Opening, GARCH & Valuation

**Topics covered**
1. **Title & core idea** — Quantitative Anomalies as Market Opportunities; the
   Efficient Market Hypothesis vs reality, and why an anomaly is an opportunity.
2. **Objectives & motivation** — the five opportunity-framed objectives, and why we
   chose the topic (anomalies made tangible; statistics + local AI).
3. **Data & APIs** (in place of questionnaire + sample) — Yahoo Finance, FRED,
   DBnomics backup; our FastAPI backend; the local AI API.
4. **Pillar — GARCH & Volatility Clustering** — modelling time-varying risk;
   evidence of clustering and fat tails via Ljung-Box and Jarque-Bera
   *(sample: persistence ≈ 0.994 over 2,905 days, excess kurtosis ≈ 15.8,
   Jarque-Bera p ≈ 0)*.
5. **Valuation lens** — "is a stock bloated / overpriced?" via fundamental ratios
   (P/E, P/B, PEG) vs the stock's history and peers — flagging "priced for
   perfection" vs "on sale".

---

## Part 2 — Jitvan — Macro & the Engine

**Topics covered**
1. **Pillar — Macro Factor & Lag Regression** — OLS with *standardized* lagged
   macro factors and Granger causality: which forces move an asset and with what
   delay *(sample: S&P 500 R² ≈ 0.69; 6 of 32 Granger tests significant)*.
2. **The decision engine** — "statistics detect, the AI explains". Seven
   detectors normalized onto one bull/bear axis, then **fused**: weight =
   severity × statistical reliability, giving a direction (`tilt`) and a
   `conviction` that *falls* when signals disagree — with risk kept on a
   separate axis and dissent shown rather than averaged away.
3. **Pilot status & modules built** — the working backend + dashboard, and the
   data-validation finding worth telling: `yfinance` is **not thread-safe**,
   which is what had been silently swapping one ticker's data for another.

---

## Part 3 — Rithesh — Pairs, Decision Modes & Future

**Topics covered**
1. **Pillar — Forex Pair Trading** — cointegration across pairs, the spread and
   z-score on **log prices**, mean-reversion signals and half-life
   *(sample: USDCHF/USDJPY cointegrated, p = 0.0075, half-life ≈ 69 days)*.
2. **Rules vs LLM** — the trade-offs (determinism, explainability, speed,
   flexibility) and why we landed on "rules decide, the model explains": the
   model's stance is shown *beside* the computed one so it may disagree
   visibly, and every number it writes is checked against the evidence we gave it.
3. **Future directions** — **options analysis via Black–Scholes** *(keep
   high-level: the idea is to gauge whether options look expensive or cheap
   versus our volatility model — the module and endpoint are built; wiring it
   in as a detector is next)*; the statistical-rigor work (multiple-testing
   correction, HAC errors, out-of-sample validation); brief closing.

---

### Timing
Roughly **5 minutes per part** for a ~15-minute talk. Each part owns one core
statistical method plus supporting material, so the depth is even across presenters.
