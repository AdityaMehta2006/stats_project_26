# Quantitative Anomalies as Market Opportunities
### A Statistical and AI-Assisted Dashboard for Equity and Forex Markets

**Individual Report — submitted up to CIA 2**

---

## 1. Abstract

The Efficient Market Hypothesis assumes that prices absorb information instantly,
that risk is broadly constant, and that returns cannot be forecast. Fifty years of
empirical work says otherwise, and the documented departures — lagged macroeconomic
transmission, volatility clustering, fat tails, and cointegration between related
assets — are collectively called anomalies. This study treats each anomaly not as a
defect in the theory but as a measurable opportunity, and builds a working system
that finds them on live market data.

The project, **QuantAnomalies**, is a full-stack analytical dashboard with five
statistical pillars: macro factor-and-lag regression, GARCH volatility modelling,
Engle–Granger cointegration for forex pair trading, options pricing under four
closed-form models, and the stochastic processes that underlie all of them. Thirteen
deterministic detectors read these pillars and emit signals; a rule-based decision
layer fuses the signals into a single directional verdict weighted by each detector's
own statistical reliability; a locally hosted large language model then explains the
verdict in plain English without ever being permitted to compute or alter a number.

Validated on the S&P 500 and a 45-pair forex universe over 2015–2025, the system
finds that standardized macro factors explain 68.7% of monthly return variation
(adjusted R² = 0.585), that GARCH(1,1) persistence reaches 0.994 with excess kurtosis
of 15.8 and a Jarque–Bera p-value indistinguishable from zero, and that USDCHF and
USDJPY are cointegrated at p = 0.0075 with a mean-reversion half-life of 69 days.
The fused engine returns a cross-asset scan in 11 ms warm and a per-asset verdict in
4.5 ms. The principal contribution is architectural: statistics detect, deterministic
rules decide, and the language model only explains — a separation that makes the
output identical whether or not the model is running, and therefore auditable. The
acknowledged limitation, stated deliberately, is that the results are in-sample: no
walk-forward backtest, no multiple-testing correction on the cointegration sweep, and
no transaction costs. These bound what the project currently claims and define the
next block of work.

---

## 2. Introduction

Finance students meet the Efficient Market Hypothesis early and are told, quite
correctly, that it is the right null hypothesis. Its three practical consequences —
that prices reflect all available information, that volatility is a stable parameter,
and that returns are unforecastable — are also the three assumptions that empirical
finance has spent decades contradicting. Those contradictions are not scattered noise.
They are repeatable, named, and published: Chen, Roll and Ross showed macroeconomic
variables are priced factors; Mandelbrot, Engle and Bollerslev established that
variance moves and clusters; Engle and Granger showed that individually
unforecastable series can be tethered to each other.

The intellectual move this project makes is small but consequential. An anomaly is a
statement that the model is wrong somewhere. Read from the other direction, it is a
statement about where a careful observer might have an edge. A lagged macro effect is
a positioning window. A volatility regime is a risk-sizing instruction. A stretched
cointegrated spread is a market-neutral bet. The same statistic that a researcher
reports as a rejection of a null is what a practitioner reports as a signal.

Three problems stand between that observation and anything usable. First,
**fragmentation**: macro-factor work, volatility modelling and cointegration live in
different sub-literatures and different toolchains, so almost nothing lets a user
point at one arbitrary ticker and see all three at once. Second, **interpretation**:
a persistence of 0.994 or a half-life of 69 days communicates nothing to a
non-specialist, and the statistical literature is not written to fix that. Third,
**aggregation**: even when several signals are available, combining them is usually
done either by naive averaging, which manufactures false confidence out of
disagreement, or by a machine-learning model whose output is a number nobody can
interrogate.

This study addresses all three. It builds an integrated dashboard covering five
statistical pillars on any user-supplied ticker; it adds a natural-language
explanation layer that is constrained to explain rather than compute and is audited
against the figures it was given; and it fuses the signals through an explicit,
inspectable rule set in which conviction *falls* when detectors disagree and
dissenting signals are displayed rather than averaged away.

The scope covered by this report runs from project inception to the CIA 2
presentation: the data pipeline and its validation, all five analysis pillars, the
thirteen-detector decision layer, the fusion engine, the local AI layer, and the
dashboard. Backtesting and the inferential hardening described in §7 are outside this
scope and are stated as open work rather than claimed as done.

---

## 3. Literature Review

### 3.1 Efficient markets and their documented cracks

Fama (1970, 1991) sets the null: prices fully reflect available information, so
risk-adjusted excess returns are unattainable. The anomalies literature is the record
of where that null fails. Lo and MacKinlay (1988) statistically reject the random-walk
model for U.S. weekly returns. Shiller (1981) shows that prices move far more than
dividend fundamentals can justify — the excess-volatility finding. These results do
not overturn the hypothesis so much as locate the places where structure survives, and
those places are where this project looks.

### 3.2 Macro factors and lagged transmission

Arbitrage Pricing Theory (Ross, 1976) frames returns as driven by several systematic
factors rather than one market beta. Chen, Roll and Ross (1986), in the canonical
*Economic Forces and the Stock Market*, show that industrial production, inflation
surprises, the term spread and default spreads are priced risk factors for equities.
Fama and French (1989) demonstrate that dividend yield and term/default spreads
forecast returns at business-cycle horizons — that is, macro effects operate **with a
lag**, which is precisely the effect this project measures. To test direction rather
than mere association, the study uses Granger causality (Granger, 1969), which asks
whether a factor's past improves the forecast of returns beyond what returns' own past
already provides. The macro pillar is therefore an OLS regression of returns on lagged
macro factors, with Granger tests and AIC/BIC lag-depth comparison.

### 3.3 Volatility clustering and fat tails

Mandelbrot (1963), studying cotton prices, observed that large changes are followed by
large changes and small by small, and that returns carry tails far heavier than the
normal distribution admits. Engle (1982) formalised the first half as the ARCH model,
letting conditional variance depend on recent squared shocks; Bollerslev (1986)
generalised it to GARCH, and GARCH(1,1) is the specification fitted here. Cont (2001)
catalogues the stylized facts — clustering, heavy tails, the leverage effect — that
these models exist to capture. The properties are tested directly rather than assumed:
Ljung–Box (1978) on squared returns for ARCH effects, and Jarque–Bera (1980) with Q–Q
plots for non-normality. The practical reading is twofold — a high-volatility regime is
a risk-management and option-pricing signal, and fat tails warn that variance-based
risk measures understate danger.

### 3.4 Cointegration and pairs trading

Engle and Granger (1987) introduced cointegration: two non-stationary price series can
share a stationary linear combination, so they remain tethered in the long run even
while each is individually unpredictable. This is the statistical foundation of
statistical arbitrage. Gatev, Goetzmann and Rouwenhorst (2006), the most-cited
empirical treatment, show that a simple distance-based pairs rule earned significant
excess returns on U.S. equities from 1962 to 2002, and document its decay as the
strategy crowded. Vidyamurthy (2004) provides the standard practitioner pipeline —
hedge ratio, spread, z-score, half-life — which is the pipeline implemented here.

### 3.5 Options pricing and the variance risk premium

Black and Scholes (1973) and Merton (1973) derived the closed-form European option
price under geometric Brownian motion. Its most useful practical output is implied
volatility: the volatility that equates model price to market price. The gap between
option-implied volatility and subsequently realised or model-forecast volatility — the
variance risk premium — is well documented and typically positive (Bakshi and Kapadia,
2003; Carr and Wu, 2009), meaning options are on average rich. Comparing market implied
volatility with this project's own GARCH forecast is what bridges the volatility pillar
to the options pillar and produces one of the thirteen detector signals.

### 3.6 Cross-sectional anomalies

Basu (1977) found that low price-to-earnings stocks earn higher risk-adjusted returns
than high-P/E stocks — the value anomaly — later formalised with the size premium into
the Fama–French three-factor model (1992, 1993) and extended to five factors (2015).
Jegadeesh and Titman (1993) document momentum: 3–12 month winners continue to
outperform over the following 3–12 months, confirmed across asset classes by Asness,
Moskowitz and Pedersen (2013). Thaler (1987) surveys calendar effects. These support
the momentum, relative-strength and seasonality detectors in the decision layer.

### 3.7 Statistical and AI tooling

Econometric work relies on peer-reviewed implementations in `statsmodels` (Seabold and
Perktold, 2010) and the `arch` package for GARCH. The novel layer is the use of a
**local** large language model to translate quantitative output into natural-language
reasoning. The model is deliberately constrained to explain numbers it is given rather
than compute them, mitigating the well-documented hallucination risk in language
generation (Ji et al., 2023) and keeping the analyst note anchored to the deterministic
statistics.

### 3.8 Data sources — assessment

A study is only as good as its instrument, and here the instrument is a set of
financial-data APIs.

**FRED**, maintained by the Federal Reserve Bank of St. Louis, is an authoritative and
widely cited repository of U.S. macroeconomic series with documented vintages and
revision histories. Its limitation is intrinsic rather than technical: official
statistics are released monthly with genuine publication lags and are subject to later
revision, which is why this study models at monthly frequency and treats macro effects
as lagged by construction.

**Yahoo Finance**, accessed through `yfinance`, provides daily OHLCV data across
equities, indices, currencies, futures and crypto, with split- and dividend-adjusted
prices and long history. The documented limitations are occasional data errors, silent
changes to an unofficial API, possible survivorship bias for delisted names, and
adjusted-price conventions that differ between vendors. This project encountered a more
insidious variant, described in §5.2, which produced a caveat not found stated in the
sources reviewed: with an unofficial client, the *access pattern* must be validated,
not only the values.

**DBnomics** re-serves public economic datasets, including FRED, through a single open
API, and is used here purely as a redundancy layer so that one provider outage cannot
halt the study.

### 3.9 Research gap

The anomalies above are individually well studied, but three gaps motivate this work.
**Integration** — few accessible tools bring macro-factor, volatility and
cointegration analysis together for an arbitrary user-chosen asset. **Interpretation**
— statistical output is opaque to non-specialists, and the remedy attempted here is a
grounded explanation layer that is constrained to explain rather than compute and is
audited against the figures supplied to it. **Actionability** — signals are fused into
a single verdict weighted by each detector's own statistical reliability, with
conviction falling on disagreement and dissenting signals displayed rather than
averaged away, so the aggregation stays legible instead of becoming another opaque
score.

---

## 4. Objectives of the Study

1. **Measure macro-driver opportunity.** Identify which macroeconomic forces — the
   volatility index, oil, gold, the dollar index, the 10-year yield, the Fed Funds
   rate, inflation and unemployment — move an asset's returns, and with what time
   delay, so that a lag can be read as a positioning window rather than a curiosity.

2. **Model the risk regime.** Estimate time-varying volatility via GARCH(1,1), test
   volatility clustering formally, and quantify the departure from normality, so that
   regime changes become an explicit risk-sizing input and tail risk is stated rather
   than assumed away.

3. **Detect mean-reversion opportunity.** Test a 45-pair forex universe for
   cointegration, construct the hedge ratio, spread and z-score for the strongest
   pair, generate entry and exit signals, and estimate the mean-reversion half-life.

4. **Price options and extract the variance risk premium.** Implement four closed-form
   pricing models on a shared engine with full Greeks, wire them to live market
   inputs, and compare market implied volatility against the project's own GARCH
   forecast.

5. **Synthesise the signals into one decision.** Fuse the detector outputs into a
   single directional verdict with explicit conviction, an independent risk axis, and
   a full audit trail — such that conviction falls on genuine conflict instead of
   averaging opposing evidence into a confident-looking middle.

6. **Explain the verdict in natural language, verifiably.** Use a locally hosted
   language model to narrate the decision under a strict constraint: it may not
   compute, rank, or invent a number, and every figure in its output is checked
   against the evidence it was supplied.

7. **Deliver accessibility and robustness.** Support any user-typed ticker and any
   forex combination on a fault-tolerant, cache-validated data pipeline, presented
   through an interactive dashboard.

---

## 5. Methodology

### 5.1 Research design

The design is quantitative, secondary-data, and computational. There is no
questionnaire and no human sample; the instrument is a set of financial-data APIs and
the sample is the live market history they return — daily price history from 2015 to
2025 across equities, indices, currencies, futures and crypto, together with monthly
U.S. macroeconomic series. Analysis is conducted at daily frequency for volatility and
pairs work and at monthly frequency for macro regression, matching the publication
frequency of official statistics.

### 5.2 Data pipeline and validation

Prices are drawn from Yahoo Finance and macro series from FRED, with DBnomics as a
fallback mirror, and everything is cached as CSV so the system runs offline once
populated. Four validation practices are built in, each prompted by a fault actually
encountered:

- **Range and sanity validation of every cached series.** This is what first exposed a
  corruption in which the volatility and oil caches held each other's data.
- **Serialized downloads.** Tracing that corruption revealed the mechanism: the
  `yfinance` client is not thread-safe, and concurrent `yf.download()` calls silently
  return one ticker's data labelled as another's. A deliberately threaded scan
  reproduced the fault on demand — three separate ticker pairs returned byte-identical
  frames. The failure is silent and plausible-looking, and no test that merely checks
  for missing data would catch it. Downloads now run behind a lock.
- **A cache staleness guard.** The download window's end date had been hardcoded, so
  once written, a cache was served indefinitely and every "latest price" in the
  application aged silently — at discovery, by 208 days. The end date now tracks the
  current date, a cached series older than seven days triggers a refetch, and if the
  refetch fails the stale cache is still served rather than raising, with the staleness
  exposed through a `data_freshness()` endpoint so it is visible rather than hidden.
  Monthly macro series are exempt, since their lag is genuine.
- **Fault-tolerant assembly.** If one factor source fails, that factor is skipped
  rather than breaking the entire study, and the omission is recorded.

### 5.3 Pillar 1 — Macro factor and lag regression

A monthly dataset is assembled containing the asset's return alongside eight
standardized macro factors. OLS is estimated with time lags of zero to three months,
so that both contemporaneous and delayed transmission are visible. Because the
regressors are standardized, coefficients are comparable betas and the question "which
driver matters most" has a fair answer. Granger-causality tests are run across the
factor–lag grid, and a lagged-correlation heatmap supports visual inspection. Lag depth
is compared by AIC and BIC.

### 5.4 Pillar 2 — GARCH and volatility clustering

A GARCH(1,1) model is fitted to daily log returns, producing a day-by-day conditional
volatility series and a persistence estimate (α + β). Clustering is tested with the
Ljung–Box statistic on squared returns; normality is tested with Jarque–Bera and
inspected with a Q–Q plot alongside skewness and excess kurtosis. The fitted model
also produces the forward volatility forecast consumed by the options pillar.

### 5.5 Pillar 3 — Forex pair trading

Engle–Granger cointegration is tested across all pair combinations in the forex
universe. For the strongest pair, a hedge ratio is estimated by regression on log
prices, the spread is constructed and standardized to a z-score, and entry and exit
signals are generated at thresholds of ±2 and near zero respectively. The
mean-reversion half-life is estimated from an AR(1) regression on spread changes.

### 5.6 Pillar 4 — Options pricing

Four closed-form models share a single engine and differ only in the carry term:
Black–Scholes–Merton for equities, Garman–Kohlhagen for FX, Black-76 for futures, and
Bachelier for normal dynamics. First- and second-order Greeks are computed
analytically. A Cox–Ross–Rubinstein lattice handles American early exercise, and two
smile-admitting models are implemented — the Merton jump-diffusion Poisson series and
the Heston characteristic-function integral. Market wiring uses live spot, a
continuously compounded rate derived from `^TNX`, the actual dividend yield, a GARCH
volatility forecast aggregated over the option's life, and jump parameters fitted from
the return distribution's own tails.

### 5.7 Pillar 5 — Stochastic processes

Simulation engines are implemented for the Wiener process, geometric Brownian motion,
Ornstein–Uhlenbeck, Cox–Ingersoll–Ross, Merton jump-diffusion and Heston, each
reporting theoretical moments beside empirical ones as a self-check. An
Euler-versus-Milstein convergence study and a variance-reduction comparison
(antithetic, control variate, and both) are included.

### 5.8 Coupling between pillars

The pillars are not independent exercises; four explicit couplings tie them into one
system. The GARCH volatility forecast, aggregated over an option's life, *is* the sigma
fed to Black–Scholes, on the reasoning that an option is a claim on future variance and
a forecast is therefore the correct input rather than a historical average. Heston is
seeded from GARCH by κ = −252·ln(α+β), with θ the GARCH long-run variance and v₀ the
current conditional variance, since both describe the same dynamics in discrete and
continuous time. The pair spread is fitted as an Ornstein–Uhlenbeck process whose
half-life ln(2)/κ independently reproduces the value the pairs module derives from
AR(1). Finally, market implied volatility minus the GARCH forecast becomes the
variance-risk-premium detector signal.

### 5.9 The decision layer

Three strictly separated layers constitute the design's principal claim.

**Detection.** Thirteen deterministic detectors emit signals with a severity in [0, 1]:
trend, breakout, 12-1 momentum and relative performance on the price/trend axis;
mean reversion (RSI plus displacement) and pairs opportunity on the mean-reversion
axis; volatility regime, tail event and options mispricing on the volatility axis;
macro dislocation; and volume anomaly, correlation regime and seasonality on the
flow/context axis.

**Decision.** The signals are netted into one stance, conviction and position size.
Each signal is weighted by reliability × severity, where reliability is derived from
the detector's own statistics — cointegration p-value, macro R², GARCH sample size —
and never invented. Redundant signals within a family are discounted by 0.45^rank, so
three views of the same price move do not count as three confirmations. Direction
(agreement × strength, with strength saturating through tanh) is separated from size,
which is a risk overlay driven by risk-off signals and the volatility percentile.
Conviction is demoted on genuine conflict rather than averaged, and a full audit trail
names every step.

**Fusion.** A parallel engine answers where the evidence points and how firmly. Eight
of the thirteen detectors feed it. Because detectors speak different direction
vocabularies — "uptrend", "above_model", "long spread", "compressed", "rich" — a
polarity map collapses them onto one bull/bear/neutral axis. Volatility and tail
readings are routed to a separate risk axis so that a volatility spike can never
masquerade as a directional call, and volatility mispricing is kept off both axes since
expensive premium is a relative-value read. With weight w = severity × reliability:

```
tilt       = (bull − bear) / (bull + bear)          direction, −1..+1
agreement  = 1 − min(bull, bear) / max(bull, bear)  how one-sided
mass       = 1 − exp(−total / 2)                    saturating evidence weight
conviction = mass × (0.4 + 0.6 × agreement)
```

Strength therefore beats count, nothing pins to 1.0 on noise, and a signal pointing
the other way actively lowers conviction. This replaced an earlier linear form
dominated by signal count that clamped to 1.0 as soon as six of anything appeared.

**Explanation.** The language model receives the detections and the computed decision
as compact JSON and writes prose. It cannot compute, rank, invent a number, or change
the stance, conviction or size; the system's output is identical whether or not a model
is available. Three mechanisms make that verifiable rather than merely asserted: the
prompt demands a `STANCE:` line before the prose, so the model's own labelled opinion
lands within roughly ten tokens; that stance renders beside the computed stance, so
divergence is visible rather than hidden; and an `unverified_numbers()` check tests
every figure in the narrative against the supplied evidence, surfacing anything
unmatched as a grounding badge in the interface.

### 5.10 Implementation and performance

The backend is FastAPI with pandas, numpy, statsmodels, arch and scipy, exposing 38
endpoints; the frontend is React 19 with Vite, Recharts and framer-motion. The language
runtime is a local `llama.cpp` server running Qwen3-4B on an RTX 4050 via Vulkan, with
a CPU fallback and a rules-only path if no model is running — nothing leaves the
machine. Price detectors run broad and cheap, one cointegration sweep serves the whole
FX basket, and GARCH is cached on (ticker, last data date) so it refits once per
trading day regardless of request volume. A detector that fails is recorded in
diagnostics rather than raised, so one dead factor costs one signal rather than the
verdict.

### 5.11 Verification strategy

The numerical work is checked rather than trusted, with each check computed at request
time and returned in the API response so it is visible in the interface. Put–call
parity is a model-free arbitrage identity; Greeks are cross-checked against central
finite differences; every Monte Carlo estimator is paired against the exact price for
the same model; the binomial lattice is checked for 1/N error decay; and the Heston
characteristic function is checked by driving vol-of-vol to zero, which must collapse
the model to Black–Scholes.

---

## 6. Data Analysis and Results (to CIA 2)

All figures below were recomputed on 26 July 2026 on live data.

### 6.1 Pillar 1 — Macro factor regression (S&P 500, monthly)

| Quantity | Value |
|---|---|
| R² | 0.687 |
| Adjusted R² | 0.585 |
| Granger tests run | 32 |
| Significant Granger relationships | 6 |

Standardized macro factors explain roughly 69% of monthly return variation. Because
the regressors are standardized, the coefficients are directly comparable, so the
ranking of drivers is meaningful rather than an artefact of differing units. Six of
thirty-two Granger tests reach significance, indicating that a subset of factors leads
returns rather than merely co-moving with them — which is the lag that objective 1
sought to measure. The gap between R² and adjusted R² reflects the cost of the lag
structure in degrees of freedom and is reported rather than suppressed.

### 6.2 Pillar 2 — GARCH and the return distribution (S&P 500, daily)

| Quantity | Value |
|---|---|
| Sample | 2,905 trading days |
| GARCH(1,1) persistence (α + β) | 0.994 |
| Excess kurtosis | 15.8 |
| Skewness | −0.65 |
| Jarque–Bera p-value | ≈ 0 |

Persistence of 0.994 means volatility shocks decay very slowly: a turbulent period
predicts further turbulence for weeks, which is exactly the clustering that Mandelbrot
described and that ARCH/GARCH was built to formalise. Excess kurtosis of 15.8 against
a normal benchmark of 0, with negative skew, says that extreme moves — and
particularly extreme *downward* moves — occur far more often than a Gaussian
assumption admits. Jarque–Bera rejects normality decisively. The practical consequence
is that variance-based risk measures on this series understate danger, and that a
volatility regime is a legitimate risk-sizing input rather than a descriptive
statistic.

One caveat is stated by the code itself and displayed in the interface: as persistence
approaches 1, the GARCH long-run variance becomes ill-conditioned. Short-horizon
forecasts from this fit are reliable; the long-run level is indicative only.

### 6.3 Pillar 3 — Cointegration and pairs (45-pair forex universe)

| Quantity | Value |
|---|---|
| Strongest pair | USDCHF / USDJPY |
| Engle–Granger p-value | 0.0075 |
| Hedge ratio | −0.339 |
| Mean-reversion half-life | 69 days |

The pair tests cointegrated on log prices, and the half-life of 69 days sets the
horizon over which a stretched spread would be expected to close. The independent
Ornstein–Uhlenbeck fit in Pillar 5 reproduces this half-life from ln(2)/κ, which is a
genuine cross-check: two different estimation routes, one AR(1)-based and one
SDE-based, agree on the same reversion speed.

The result is reported with its qualification. The sweep searches many pair
combinations and reports the best, so the p-value is not corrected for multiple
comparisons; against a Bonferroni threshold over the 15 combinations in the reported
subset, 0.0075 does not survive 0.05/15 = 0.00333. What supports the finding is the
economic rationale — both legs are USD-based safe-haven crosses and therefore share a
common driver — rather than the p-value in isolation. Benjamini–Hochberg correction is
the natural remedy and is scheduled work.

### 6.4 Pillar 4 — Options and the variance risk premium (AAPL)

| Quantity | Value |
|---|---|
| Market implied volatility | 33.1% |
| GARCH forecast volatility | 28.8% |
| Variance risk premium | +4.3 points |

The positive sign matches the documented literature (Bakshi and Kapadia; Carr and Wu):
options are on average rich relative to subsequently realised volatility. Because the
Heston model here is seeded from GARCH rather than calibrated to observed option
prices, the comparison is not circular — calibrating to prices would have made the
premium an artefact of the fit. The consequence is that the model smile is a
prediction rather than a fit, which is the intended trade-off.

### 6.5 Numerical verification

| Check | Method | Result |
|---|---|---|
| Put–call parity | model-free arbitrage identity | violation 0.0 |
| Greeks | central finite differences, O(h²) | max difference 4.6 × 10⁻⁷ |
| GBM Monte Carlo | vs analytic Black–Scholes | within 3 standard errors |
| Merton Monte Carlo | vs exact Poisson-weighted series | Δ 0.053, SE 0.039 |
| Heston Monte Carlo | vs Fourier inversion of the CF | Δ 0.067, SE 0.050 |
| Heston CF | vol-of-vol → 0 must collapse to Black–Scholes | Δ 3 × 10⁻⁶ |
| Binomial lattice | error against 1/N | halves per step doubling |
| American call, no dividend | premium must be exactly zero | 0.0 |
| Longstaff–Schwartz | vs 800-step lattice | Δ 0.023, SE 0.029 |
| Black–Scholes smile | implied-vol spread across strikes | 0.000 |

The Heston check is the most informative. Driving vol-of-vol to zero must reduce the
model to Black–Scholes, and agreement to six decimal places validates the complex
arithmetic, the branch-cut handling and the quadrature simultaneously — against a
formula derived by an entirely different route.

Variance-reduction efficiency was measured rather than asserted: plain Monte Carlo
1.00×, antithetic 1.97×, control variate 5.01×, and both combined **19.27×**.

### 6.6 Decision engine performance

| Quantity | Value |
|---|---|
| Detectors implemented | 13 (8 feeding the fusion engine) |
| Cross-asset feed, warm | 11 ms |
| Per-asset verdict, warm | 4.5 ms |
| Off-universe asset, cold | 0.9 s |
| AI narration | ≈ 4 s, ≈ 28 tokens/sec, streaming, fully local |

The warm figures are the result of the tiering described in §5.10 — a single
cointegration sweep amortised across the FX basket and a GARCH cache keyed on the last
data date, so the model refits once per trading day rather than once per request.

### 6.7 Data-pipeline findings

Two findings are worth reporting as results in their own right, because both are
methodological rather than incidental. The first is the `yfinance` thread-safety fault
described in §5.2: concurrent downloads silently mislabel one ticker's data as
another's, reproduced on demand with three byte-identical frame pairs. The second is
the frozen end date that had left every cached price series 208 days stale while the
dashboard reported them as current. Both failures were silent and both produced
plausible-looking output, which is precisely why they are worth stating: they were
caught by range validation and a freshness check, not by any test for missing data. A
third defect of the same character — a dividend-yield unit mismatch applying a 32%
yield to a stock paying 0.32% — was found by the same route.

### 6.8 Interpretation against the objectives

Objectives 1 through 4 are met with quantified results: macro drivers are measured
with their lags and a directional test, the risk regime is modelled and its
non-normality quantified, a cointegrated pair is identified with its reversion horizon,
and the variance risk premium is extracted. Objective 5 is met by the fusion engine,
whose behaviour on conflicting evidence is the specific property that distinguishes it
from averaging. Objective 6 is met and, more importantly, made checkable through the
stance-beside-stance display and the number guardrail. Objective 7 is met: any ticker,
any forex combination, on a pipeline that now validates rather than trusts its sources.

---

## 7. Limitations

These are stated deliberately, because they bound what the project currently claims.

1. **No backtest.** Signals are detected but never evaluated for profit and loss,
   Sharpe ratio or drawdown. Everything reported is in-sample. This is the largest gap:
   "opportunities" are not yet evidence.
2. **Multiple testing is uncorrected.** The cointegration sweep reports the best of many
   tests without a Benjamini–Hochberg or Bonferroni correction, as discussed in §6.3.
3. **OLS standard errors** are used on a monthly regression with autocorrelated
   residuals, where Newey–West HAC errors would be appropriate.
4. **Decision weights are stated judgement, not fitted** — deliberately, since fitting
   them on a few hundred monthly observations would overfit more convincingly than it
   would inform.
5. **No transaction costs** are modelled anywhere.
6. **GARCH long-run variance is ill-conditioned** at persistence near 1; short-horizon
   forecasts hold, the long-run level is indicative.
7. **A single 10-year rate serves all option maturities**, where a bootstrapped yield
   curve would be correct; FX policy rates are approximations.
8. **Heston is seeded from GARCH, not calibrated to option prices** — intentional, to
   keep the variance-risk-premium comparison non-circular, at the cost of the smile
   being a prediction rather than a fit.

---

## 8. Work Planned Beyond CIA 2

In priority order: a walk-forward backtest of the decision engine, which is the highest
value next step and the one that converts detected signals into evidence;
multiple-comparisons correction on pair selection; Newey–West HAC standard errors on
the macro regression; transaction-cost modelling; a bootstrapped yield curve for option
maturities; and KPSS and structural-break tests to complement ADF.

---

## References

- Asness, C. S., Moskowitz, T. J., & Pedersen, L. H. (2013). Value and momentum everywhere. *Journal of Finance*, 68(3), 929–985.
- Bakshi, G., & Kapadia, N. (2003). Delta-hedged gains and the negative market volatility risk premium. *Review of Financial Studies*, 16(2), 527–566.
- Basu, S. (1977). Investment performance of common stocks in relation to their price-earnings ratios. *Journal of Finance*, 32(3), 663–682.
- Black, F., & Scholes, M. (1973). The pricing of options and corporate liabilities. *Journal of Political Economy*, 81(3), 637–654.
- Bollerslev, T. (1986). Generalized autoregressive conditional heteroskedasticity. *Journal of Econometrics*, 31(3), 307–327.
- Carr, P., & Wu, L. (2009). Variance risk premiums. *Review of Financial Studies*, 22(3), 1311–1341.
- Chen, N.-F., Roll, R., & Ross, S. A. (1986). Economic forces and the stock market. *Journal of Business*, 59(3), 383–403.
- Cont, R. (2001). Empirical properties of asset returns: stylized facts and statistical issues. *Quantitative Finance*, 1(2), 223–236.
- Engle, R. F. (1982). Autoregressive conditional heteroscedasticity with estimates of the variance of United Kingdom inflation. *Econometrica*, 50(4), 987–1007.
- Engle, R. F., & Granger, C. W. J. (1987). Co-integration and error correction: representation, estimation, and testing. *Econometrica*, 55(2), 251–276.
- Fama, E. F. (1970). Efficient capital markets: a review of theory and empirical work. *Journal of Finance*, 25(2), 383–417.
- Fama, E. F. (1991). Efficient capital markets: II. *Journal of Finance*, 46(5), 1575–1617.
- Fama, E. F., & French, K. R. (1989). Business conditions and expected returns on stocks and bonds. *Journal of Financial Economics*, 25(1), 23–49.
- Fama, E. F., & French, K. R. (1992). The cross-section of expected stock returns. *Journal of Finance*, 47(2), 427–465.
- Fama, E. F., & French, K. R. (1993). Common risk factors in the returns on stocks and bonds. *Journal of Financial Economics*, 33(1), 3–56.
- Fama, E. F., & French, K. R. (2015). A five-factor asset pricing model. *Journal of Financial Economics*, 116(1), 1–22.
- Gatev, E., Goetzmann, W. N., & Rouwenhorst, K. G. (2006). Pairs trading: performance of a relative-value arbitrage rule. *Review of Financial Studies*, 19(3), 797–827.
- Granger, C. W. J. (1969). Investigating causal relations by econometric models and cross-spectral methods. *Econometrica*, 37(3), 424–438.
- Jarque, C. M., & Bera, A. K. (1980). Efficient tests for normality, homoscedasticity and serial independence of regression residuals. *Economics Letters*, 6(3), 255–259.
- Jegadeesh, N., & Titman, S. (1993). Returns to buying winners and selling losers. *Journal of Finance*, 48(1), 65–91.
- Ji, Z., et al. (2023). Survey of hallucination in natural language generation. *ACM Computing Surveys*, 55(12), 1–38.
- Ljung, G. M., & Box, G. E. P. (1978). On a measure of lack of fit in time series models. *Biometrika*, 65(2), 297–303.
- Lo, A. W., & MacKinlay, A. C. (1988). Stock market prices do not follow random walks. *Review of Financial Studies*, 1(1), 41–66.
- Mandelbrot, B. (1963). The variation of certain speculative prices. *Journal of Business*, 36(4), 394–419.
- Merton, R. C. (1973). Theory of rational option pricing. *Bell Journal of Economics and Management Science*, 4(1), 141–183.
- Ross, S. A. (1976). The arbitrage theory of capital asset pricing. *Journal of Economic Theory*, 13(3), 341–360.
- Seabold, S., & Perktold, J. (2010). statsmodels: econometric and statistical modeling with Python. *Proc. 9th Python in Science Conf.*
- Shiller, R. J. (1981). Do stock prices move too much to be justified by subsequent changes in dividends? *American Economic Review*, 71(3), 421–436.
- Thaler, R. H. (1987). Anomalies: the January effect. *Journal of Economic Perspectives*, 1(1), 197–201.
- Vidyamurthy, G. (2004). *Pairs Trading: Quantitative Methods and Analysis*. Wiley.
