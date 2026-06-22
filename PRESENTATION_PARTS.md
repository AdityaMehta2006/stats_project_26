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
   *(sample: persistence ≈ 0.9955, excess kurtosis ≈ 16)*.
5. **Valuation lens** — "is a stock bloated / overpriced?" via fundamental ratios
   (P/E, P/B, PEG) vs the stock's history and peers — flagging "priced for
   perfection" vs "on sale".

---

## Part 2 — Jitvan — Macro & the Engine

**Topics covered**
1. **Pillar — Macro Factor & Lag Regression** — OLS with lagged macro factors and
   Granger causality: which forces move an asset and with what delay
   *(sample: S&P 500 macro R² ≈ 0.64)*.
2. **The recommendation engine** — "statistics detect, the AI explains"; how
   detectors rank opportunities by severity with a confidence score.
3. **Pilot status & modules built** — validated data pipeline (corrupted cache
   found and fixed; ranges sanity-checked) and the working backend + dashboard.

---

## Part 3 — Rithesh — Pairs, Decision Modes & Future

**Topics covered**
1. **Pillar — Forex Pair Trading** — cointegration across pairs, the spread and
   z-score, mean-reversion signals and half-life
   *(sample: USDCHF/USDJPY cointegrated, p ≈ 0.008)*.
2. **Decision engine — rules-based vs LLM-based** — the trade-offs (determinism,
   explainability, speed, flexibility) and our hybrid approach with a toggle.
3. **Future directions** — **options analysis via Black–Scholes** *(keep
   high-level: the idea is to gauge whether options look expensive or cheap versus
   our volatility model — no formula needed)*; plus a few more opportunity lenses;
   brief closing.

---

### Timing
Roughly **5 minutes per part** for a ~15-minute talk. Each part owns one core
statistical method plus supporting material, so the depth is even across presenters.
