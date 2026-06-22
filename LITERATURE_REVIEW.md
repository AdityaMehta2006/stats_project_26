# Literature Review — QuantAnomalies

A review of the academic foundations for the market anomalies our project detects,
the statistical methods we use, and the data sources we rely on. The unifying
theme: each "anomaly" is a documented departure from the Efficient Market
Hypothesis, and therefore a candidate **opportunity**.

---

## 1. Theoretical backdrop: efficient markets and their cracks

The Efficient Market Hypothesis (EMH) holds that prices fully reflect available
information, so returns are unforecastable and risk-adjusted excess returns are
unattainable (Fama, 1970; Fama, 1991). Decades of empirical work, however, document
systematic, repeatable departures — the *anomalies* literature. Lo & MacKinlay
(1988) statistically reject the random-walk model for U.S. weekly returns, and
Shiller (1981) shows prices move far more than dividend fundamentals justify
("excess volatility"). These findings motivate a search for structure that a
careful, data-driven observer can exploit — the premise of this project.

---

## 2. Pillar 1 — Macro factors and lagged transmission

**Arbitrage Pricing Theory (APT)** (Ross, 1976) frames returns as driven by
multiple systematic factors. Chen, Roll & Ross (1986), in the canonical study
*Economic Forces and the Stock Market*, show that macroeconomic variables —
industrial production, inflation surprises, the term spread, and default spreads —
are priced risk factors for equities. Fama & French (1989) document that the
dividend yield and term/default spreads forecast returns over business-cycle
horizons, i.e. macro effects act **with a lag**.

To test directionality we use **Granger causality** (Granger, 1969), which asks
whether a factor's past values improve forecasts of returns beyond returns' own
past. This is precisely our macro-regression design: OLS of returns on lagged
macro factors, with Granger tests and lag-depth model comparison (AIC/BIC).
*Opportunity reading:* a factor that leads returns by weeks is a positioning window.

---

## 3. Pillar 2 — Volatility clustering and fat tails

Mandelbrot (1963), studying cotton prices, observed that "large changes tend to be
followed by large changes... and small by small" — **volatility clustering** — and
that returns have **fat tails** incompatible with the normal distribution. These
"stylized facts" were later formalised: Engle (1982) introduced the **ARCH** model
(Nobel Prize, 2003), letting variance depend on recent squared shocks; Bollerslev
(1986) generalised it to **GARCH**, the workhorse we fit (GARCH(1,1)). Cont (2001)
catalogues the empirical stylized facts of asset returns (clustering, heavy tails,
leverage) that GARCH is designed to capture.

We test these properties directly with the **Ljung–Box** statistic (Ljung & Box,
1978) on squared returns (clustering / ARCH effects) and the **Jarque–Bera** test
(Jarque & Bera, 1980) plus Q–Q plots for non-normality. *Opportunity reading:*
identifying a high-volatility regime is a risk-management and option-pricing signal;
fat tails warn that Gaussian risk measures (e.g. variance-based VaR) understate
danger.

---

## 4. Pillar 3 — Cointegration and pairs trading

Engle & Granger (1987) introduced **cointegration**: two non-stationary price series
can share a stationary linear combination, so they are tethered over the long run
even while individually unpredictable. This is the statistical basis of
**pairs / statistical-arbitrage trading**. Gatev, Goetzmann & Rouwenhorst (2006), in
the most-cited empirical study, show a simple distance/mean-reversion pairs rule
earned significant excess returns on U.S. equities over 1962–2002, and discuss its
decay as the strategy became crowded. Vidyamurthy (2004) is the standard
practitioner treatment of cointegration-based pairs construction (hedge ratio,
spread, z-score, half-life) — exactly the pipeline we implement. *Opportunity
reading:* when a cointegrated spread stretches beyond its normal band, mean
reversion is the bet, and it is market-neutral.

---

## 5. Valuation anomalies (planned module)

Basu (1977) found that low price-to-earnings stocks earn higher risk-adjusted
returns than high-P/E stocks — the **value anomaly** and direct evidence that
"expensive" stocks can be over-priced. Fama & French (1992, 1993) formalised the
value (book-to-market) and size premia into their three-factor model, later
extended to five factors (Fama & French, 2015) with profitability and investment.
This literature underpins our planned valuation lens (P/E, P/B, P/S, PEG, EV/EBITDA
versus history and peers) for flagging "bloated" versus "on-sale" names.

---

## 6. Options pricing and implied volatility (current code module)

Black & Scholes (1973) and Merton (1973) derived the closed-form price of a European
option under geometric Brownian motion — the foundation of modern derivatives. A
key practical output is **implied volatility**: the volatility that equates the
model price to the market price. The gap between option-implied volatility and
subsequently realised (or model-forecast) volatility — the **variance risk
premium** — is well documented (e.g. Bakshi & Kapadia, 2003; Carr & Wu, 2009) and is
typically positive, meaning options are, on average, "rich". *Opportunity reading:*
comparing market implied volatility to our GARCH forecast flags options that look
expensive or cheap relative to model expectations — the bridge between Pillar 2 and
this module.

---

## 7. Momentum and other cross-sectional anomalies (planned lenses)

Jegadeesh & Titman (1993) document **momentum**: past 3–12 month winners continue to
outperform losers over the following 3–12 months, one of the most robust and
pervasive anomalies (later confirmed across asset classes by Asness, Moskowitz &
Pedersen, 2013). This supports our planned momentum / relative-strength lens.
Calendar effects (turn-of-the-month, the January effect) are surveyed by Thaler
(1987) and remain part of the anomaly canon, motivating a seasonality lens.

---

## 8. Statistical and AI tooling

Our econometrics rely on standard, peer-reviewed implementations in `statsmodels`
(Seabold & Perktold, 2010) and the `arch` package (Sheppard et al.) for GARCH. The
project's novel layer is using a **local large language model** to translate
quantitative signals into natural-language reasoning. We deliberately constrain the
model to *explain* numbers it is given rather than compute them — mitigating the
well-known risk of factual "hallucination" in LLMs (Ji et al., 2023) — which keeps
the analyst note grounded in the deterministic statistics.

---

## 9. Data sources — review and assessment

A study is only as good as its data. Our "instrument" is a set of financial-data
APIs; this section assesses their provenance, strengths, and limitations.

### 9.1 FRED — Federal Reserve Economic Data
Maintained by the Federal Reserve Bank of St. Louis, FRED is an authoritative,
widely cited repository of U.S. macroeconomic series (CPI, Fed Funds Rate,
unemployment, Treasury yields). It is standard in academic and policy research and
provides documented vintages and revision histories. **Strength:** official,
free, reliable. **Limitation:** macro series are released monthly with publication
lags and are subject to later revision — a point we acknowledge by modelling at
monthly frequency and treating macro effects as lagged.

### 9.2 Yahoo Finance (via `yfinance`)
Yahoo Finance is among the most widely used free sources of daily OHLCV data for
equities, indices, currencies, futures, and crypto, and is common in empirical
finance teaching and prototyping. **Strengths:** broad cross-asset coverage, long
daily history (we use 2015–2025), split/dividend-adjusted prices, and ticker search.
**Limitations** documented by practitioners and researchers: occasional data errors
and gaps, silent changes to the (unofficial) API, possible survivorship bias for
delisted names, and adjusted-price conventions that can differ from other vendors.
Our project encountered exactly such an issue — a corrupted cache in which the
volatility and oil series had been cross-seeded — which we detected via
range-validation and corrected. This real example reinforces the literature's advice
to validate vendor data rather than trust it blindly.

### 9.3 DBnomics (fallback)
DBnomics aggregates and re-serves public economic datasets (including FRED) through a
single open API. We use it as a redundancy layer so that a single provider outage
does not halt the study — a basic but important reliability practice.

### 9.4 Data-quality practices we adopt
Informed by the above: (i) range / sanity validation of every cached series;
(ii) fault-tolerant assembly (a failed factor is skipped, not fatal);
(iii) provider redundancy (FRED + DBnomics; Yahoo `^TNX` substituting for a flaky
FRED daily series); and (iv) local caching for reproducibility.

---

## 10. Research gap and contribution

The anomalies above are individually well-studied, but the literature is fragmented
across sub-fields and is largely academic. Three gaps motivate this project:

1. **Integration.** Few accessible tools bring macro-factor, volatility, and
   cointegration analysis together for an arbitrary, user-chosen asset.
2. **Interpretation.** Statistical output (p-values, persistence, z-scores) is
   opaque to non-specialists; we add a grounded natural-language explanation layer.
3. **Actionability.** We reframe each detected anomaly as a ranked *opportunity* with
   a transparent severity and confidence, rather than a static report.

Our contribution is an integrated, explainable **opportunity-detection dashboard**
that operationalises the anomaly literature on live data.

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
