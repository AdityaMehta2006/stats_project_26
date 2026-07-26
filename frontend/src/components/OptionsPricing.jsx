/**
 * OptionsPricing.jsx
 * ------------------
 * Pillar 4: Options pricing.
 *
 * Two modes, because they answer different questions:
 *   "Market"  — price an option on a real ticker with market-derived inputs
 *               (live spot, 10Y rate, actual dividend yield, GARCH-forecast
 *               volatility), and compare against live quotes.
 *   "Theory"  — drive the models directly to see how they behave, including the
 *               implied-volatility smile that Black-Scholes cannot produce.
 *
 * The narrative the tab is built to deliver: Black-Scholes assumes one constant
 * volatility, so its implied-vol curve is flat. Real option markets are skewed.
 * Merton (jumps) and Heston (stochastic vol) both bend the curve, and that bend
 * is the same non-normality the GARCH pillar measures as excess kurtosis.
 */

import { useState, useMemo, useCallback } from "react";
import { motion } from "framer-motion";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Legend, ReferenceLine, Scatter, ComposedChart,
} from "recharts";
import useApiData from "../hooks/useApiData";
import {
  getMarketOption, getVolTermStructure, getMarketSmile,
  getOptionsMultiMarket, getOptionsSmile, getBinomialConvergence,
} from "../api";
import { LoadingState, ErrorState } from "./common/StatusStates";
import TickerSearch from "./common/TickerSearch";
import ParamControls from "./common/ParamControls";
import Icon from "./common/Icon";
import { InfoTip, LabelWithTip } from "./common/Tooltip";
import { CHART, tooltipStyle, tooltipLabelStyle, tooltipItemStyle } from "../theme";
import { fmtNum } from "../utils/format";

const container = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const item = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

const THEORY_DEFAULTS = {
  spot: 100, strike: 100, t_years: 1.0, rate: 0.05, sigma: 0.2,
  dividend: 0, option: "call",
};

const THEORY_FIELDS = [
  { key: "spot", label: "Spot S", min: 0.0001, step: 1,
    tip: "Current price of the underlying asset." },
  { key: "strike", label: "Strike K", min: 0.0001, step: 1,
    tip: "The price at which the option can be exercised. At-the-money means K = S." },
  { key: "t_years", label: "Expiry T", min: 0.0027, max: 30, step: 0.05, hint: "years",
    tip: "Time to expiry in years. 0.25 = three months. Option value grows with T because there is more time for the price to move." },
  { key: "rate", label: "Rate r", min: -0.05, max: 1, step: 0.005, hint: "decimal",
    tip: "Continuously-compounded risk-free rate. 0.05 = 5%. Raises call values and lowers put values, because the strike is paid later." },
  { key: "sigma", label: "Vol σ", min: 0.001, max: 5, step: 0.01, hint: "decimal",
    tip: "Annualised volatility. 0.20 = 20%. The only Black-Scholes input that is not directly observable, which is why implied volatility matters." },
  { key: "dividend", label: "Div q", min: 0, max: 1, step: 0.005, hint: "decimal",
    tip: "Continuous dividend yield. Lowers calls and raises puts: the option holder does not receive dividends." },
  { key: "option", label: "Type", type: "select",
    options: [{ value: "call", label: "Call" }, { value: "put", label: "Put" }],
    tip: "Call = right to buy at K. Put = right to sell at K." },
];

const SMILE_DEFAULTS = {
  lambda_jump: 0.75, mu_jump: -0.1, sigma_jump: 0.15,
  kappa: 2.0, xi: 0.4, rho: -0.7,
};

const SMILE_FIELDS = [
  { key: "lambda_jump", label: "Jump λ", min: 0, max: 20, step: 0.05, hint: "per year",
    tip: "Merton: expected number of jumps per year. Higher means fatter tails and a more pronounced smile." },
  { key: "mu_jump", label: "Jump mean", min: -1, max: 1, step: 0.01,
    tip: "Merton: average log jump size. Negative means crashes are larger than rallies, which tilts the smile into a downward skew." },
  { key: "sigma_jump", label: "Jump σ", min: 0.001, max: 2, step: 0.01,
    tip: "Merton: dispersion of jump sizes. Widens both tails symmetrically." },
  { key: "kappa", label: "Heston κ", min: 0.05, max: 25, step: 0.1,
    tip: "Heston: how fast variance reverts to its long-run level. Half-life = ln(2)/κ. Higher κ flattens the smile at long maturities." },
  { key: "xi", label: "Vol-of-vol ξ", min: 0.01, max: 2, step: 0.02,
    tip: "Heston: volatility of the variance process itself. This is what creates the smile — set it to zero and Heston collapses to Black-Scholes." },
  { key: "rho", label: "Corr ρ", min: -0.99, max: 0.99, step: 0.05,
    tip: "Heston: correlation between price and volatility shocks. Negative (about −0.7 for equities) is the leverage effect: prices fall as volatility rises. This is what tilts the smile into a skew." },
];

export default function OptionsPricing() {
  const [mode, setMode] = useState("market");
  const [ticker, setTicker] = useState("AAPL");
  const [theory, setTheory] = useState(THEORY_DEFAULTS);
  const [smileParams, setSmileParams] = useState(SMILE_DEFAULTS);

  const resetTheory = useCallback(() => setTheory(THEORY_DEFAULTS), []);
  const resetSmile = useCallback(() => setSmileParams(SMILE_DEFAULTS), []);

  return (
    <motion.div variants={container} initial="hidden" animate="show">
      <motion.div className="section-header" variants={item}>
        <div className="section-ico options"><Icon name="options" size={23} /></div>
        <div>
          <h2>Options Pricing &amp; Volatility Surface</h2>
          <p>Black-Scholes, jump-diffusion and stochastic volatility — priced on live market inputs</p>
        </div>
      </motion.div>

      <motion.div className="section-intro" variants={item}>
        <span className="intro-ico"><Icon name="info" size={18} /></span>
        <span>
          An option is a claim on <strong>future volatility</strong>. Black-Scholes prices one by
          assuming volatility is a single constant — which implies every strike should trade at the
          same implied volatility. Real markets show a <strong>skew</strong>: out-of-the-money puts
          are dearer, because crashes are real. <strong>Merton</strong> adds jumps and{" "}
          <strong>Heston</strong> makes volatility itself random; both reproduce that skew. It is the
          same fat-tailed behaviour the GARCH tab measures, seen through option prices instead of
          through returns.
        </span>
      </motion.div>

      <motion.div variants={item} className="toolbar-card">
        <div style={{ display: "flex", gap: "0.4rem" }}>
          {[
            { id: "market", label: "Market", icon: "globe" },
            { id: "theory", label: "Theory", icon: "layers" },
          ].map((m) => (
            <button
              key={m.id}
              className="param-reset"
              onClick={() => setMode(m.id)}
              style={
                mode === m.id
                  ? { background: "var(--accent-primary-dim)", borderColor: "var(--accent-primary)", color: "var(--accent-primary)" }
                  : undefined
              }
            >
              <Icon name={m.icon} size={13} /> {m.label}
            </button>
          ))}
        </div>
        {mode === "market" && <TickerSearch value={ticker} onSelect={setTicker} label="Underlying" />}
      </motion.div>

      {mode === "market"
        ? <MarketMode ticker={ticker} />
        : <TheoryMode
            theory={theory} setTheory={setTheory} resetTheory={resetTheory}
            smileParams={smileParams} setSmileParams={setSmileParams} resetSmile={resetSmile}
          />}
    </motion.div>
  );
}

/* ==========================================================================
   MARKET MODE
   ========================================================================== */

function MarketMode({ ticker }) {
  const opt = useApiData(() => getMarketOption(ticker), [ticker]);
  const vol = useApiData(() => getVolTermStructure(ticker, 30), [ticker]);
  const smile = useApiData(() => getMarketSmile(ticker, 60), [ticker]);

  const loading = opt.loading || vol.loading;
  const error = opt.error || vol.error;

  if (loading) {
    return <LoadingState message={`Pricing options on ${ticker}…`}
      subtext="Fitting GARCH, calibrating jumps, fetching the option chain" />;
  }
  if (error) {
    return <ErrorState message={error} onRetry={() => { opt.reload(); vol.reload(); smile.reload(); }} />;
  }

  const d = opt.data;
  if (!d) return null;
  const mi = d.market_inputs || {};
  const mp = d.model_prices || {};
  const cmp = d.market_comparison;

  return (
    <>
      {/* Market inputs actually used */}
      <motion.div className="stats-grid" variants={item}>
        <StatBox value={mi.spot} label="Spot" highlight
          tip="Latest close from Yahoo Finance." />
        <StatBox value={mi.strike} label="Strike"
          tip="Defaults to at-the-money (strike = spot) when none is specified." />
        <StatBox value={`${mi.days_to_expiry}d`} label="Expiry"
          tip="Days to expiry. Defaults to about 30 days." />
        <StatBox value={`${(mi.risk_free_rate * 100).toFixed(2)}%`} label="Risk-Free r"
          tip="From the 10-year Treasury (^TNX), converted to a continuously-compounded rate via r = ln(1+y) — which is what Black-Scholes requires." />
        <StatBox value={`${(mi.dividend_yield * 100).toFixed(2)}%`} label="Dividend q"
          tip="Actual reported dividend yield. Ignoring it systematically overprices calls and underprices puts." />
        <StatBox value={`${mi.sigma_model_pct}%`} label="GARCH σ" highlight
          tip="Volatility forecast from GARCH(1,1), averaged over this option's life and annualised. An option is a claim on FUTURE variance, so a forecast is the right input — not a backward-looking historical average." />
      </motion.div>

      <div className="charts-grid">
        {/* Model prices */}
        <motion.div className="card" variants={item}>
          <div className="card-header">
            <div>
              <div className="card-title">
                Model Prices
                <InfoTip text="The same option priced by every model, all using the market inputs above. Differences between them are differences in assumptions about how prices move — not arithmetic errors." />
              </div>
              <div className="card-subtitle">
                {ticker} {mi.strike} {d.option_type} · {mi.days_to_expiry} days
              </div>
            </div>
          </div>
          <div className="model-rows">
            <ModelRow name="Black-Scholes-Merton" sub="constant volatility, closed form"
              value={mp.black_scholes_merton} />
            <ModelRow name="Binomial (European)" sub="300-step lattice"
              value={mp.binomial_european} />
            <ModelRow name="Binomial (American)" sub="with early exercise"
              value={mp.binomial_american}
              err={mp.early_exercise_premium ? `+${fmtNum(mp.early_exercise_premium, 4)}` : "no premium"} />
            <ModelRow name="Merton jump-diffusion" sub="jumps fitted to this ticker's tails"
              value={mp.merton_jump_diffusion} />
            <ModelRow name="Heston stochastic vol" sub="seeded from GARCH"
              value={mp.heston_stochastic_vol} />
            <ModelRow name="Monte Carlo (GBM)" sub="antithetic + control variate"
              value={mp.monte_carlo_gbm}
              err={`± ${fmtNum(mp.monte_carlo_std_error, 4)}`} />
          </div>
          <div className="card-note" style={{ marginTop: "0.7rem" }}>
            Monte Carlo should agree with Black-Scholes to within a few standard errors — that
            agreement is the correctness check on both implementations.
          </div>
        </motion.div>

        {/* Greeks */}
        <motion.div className="card" variants={item}>
          <div className="card-header">
            <div>
              <div className="card-title">
                Greeks — Risk Sensitivities
                <InfoTip text="How the option's value responds to each input. First-order Greeks tell you your exposure; second-order Greeks tell you how fast that exposure changes, which is what actually costs money to hedge." />
              </div>
              <div className="card-subtitle">First and second order, analytically derived</div>
            </div>
          </div>
          <GreeksTable greeks={d.greeks} />
        </motion.div>

        {/* Volatility term structure */}
        {vol.data?.term_structure && (
          <motion.div className="card" variants={item}>
            <div className="card-header">
              <div>
                <div className="card-title">
                  GARCH Volatility Term Structure
                  <InfoTip text="The GARCH forecast for different option maturities. It slopes because volatility mean-reverts: if today is calm the forecast rises toward the long-run level, and if today is turbulent it falls. A single historical standard deviation is one flat number and gets this qualitatively wrong." />
                </div>
                <div className="card-subtitle">
                  {vol.data.regime || "forecast horizon vs annualised volatility"}
                </div>
              </div>
            </div>
            <div className="chart-container">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={vol.data.term_structure}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
                  <XAxis dataKey="days" stroke={CHART.axis} tick={{ fontSize: 11 }}
                    label={{ value: "days to expiry", position: "insideBottom", offset: -4, fill: CHART.axis, fontSize: 10 }} />
                  <YAxis stroke={CHART.axis} tick={{ fontSize: 11 }}
                    label={{ value: "ann. vol %", angle: -90, position: "insideLeft", fill: CHART.axis, fontSize: 10 }} />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle}
                    formatter={(v) => [`${v}%`, "annualised vol"]} />
                  {vol.data.long_run_annualized_pct && (
                    <ReferenceLine y={vol.data.long_run_annualized_pct} stroke={CHART.gold}
                      strokeDasharray="5 5"
                      label={{ value: "long-run", fill: CHART.gold, fontSize: 10, position: "right" }} />
                  )}
                  <Line type="monotone" dataKey="annualized_vol_pct" stroke={CHART.teal}
                    strokeWidth={2} dot={{ r: 3 }} name="GARCH forecast" />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="stats-grid" style={{ marginTop: "0.8rem" }}>
              <StatBox value={`${vol.data.current_annualized_pct}%`} label="Current σ"
                tip="Today's GARCH conditional volatility, annualised." />
              <StatBox value={`${vol.data.sigma_realised_1y_pct}%`} label="Realised 1Y σ"
                tip="Plain historical standard deviation over the last year — backward-looking, shown for contrast." />
              <StatBox value={vol.data.garch_params?.persistence} label="Persistence"
                tip="α + β. How slowly volatility shocks decay. Close to 1 means a shock today still matters months later, so the term structure is nearly flat." />
              <StatBox value={vol.data.variance_half_life_days} label="σ Half-Life (d)"
                tip="Days for a volatility shock to decay halfway back to normal." />
            </div>
            {vol.data.caveat && (
              <div className="card-note" style={{ marginTop: "0.7rem", color: "var(--accent-warning)" }}>
                <Icon name="alert" size={13} style={{ verticalAlign: "-2px", marginRight: 4 }} />
                {vol.data.caveat}
              </div>
            )}
          </motion.div>
        )}

        {/* Variance risk premium */}
        <motion.div className="card" variants={item}>
          <div className="card-header">
            <div>
              <div className="card-title">
                Variance Risk Premium
                <InfoTip text="Market implied volatility minus our GARCH forecast, maturity-matched. Persistently positive in index options: option sellers are paid a premium because they lose badly in crashes. A negative reading is the genuinely unusual state — protection is cheap relative to forecast risk." />
              </div>
              <div className="card-subtitle">What the market charges vs what the model forecasts</div>
            </div>
          </div>
          {cmp?.available ? (
            <>
              <div className="stats-grid">
                <StatBox value={`${cmp.market_implied_vol_pct}%`} label="Market IV" highlight
                  tip="Implied volatility we back out ourselves from the mid quote — not Yahoo's field, which uses an undisclosed model and is often stale." />
                <StatBox value={`${cmp.model_forecast_vol_pct}%`} label="GARCH Forecast"
                  tip="Our GARCH volatility forecast for the same maturity." />
                <StatBox
                  value={`${cmp.variance_risk_premium_pct > 0 ? "+" : ""}${cmp.variance_risk_premium_pct}`}
                  label="Premium (pts)"
                  cls={cmp.variance_risk_premium_pct > 0 ? "negative" : "positive"}
                  tip="Implied minus forecast, in volatility points. Positive means options look rich." />
                <StatBox value={cmp.iv_to_model_ratio} label="IV / Model"
                  tip="Ratio of implied to forecast volatility. Above 1.15 is 'rich', below 0.85 is 'cheap'." />
              </div>
              <div className="model-rows" style={{ marginTop: "0.8rem" }}>
                <ModelRow name="Market price" sub={`${cmp.price_source} · bid ${cmp.bid} / ask ${cmp.ask}`}
                  value={cmp.market_price} />
                <ModelRow name="Our model price" sub={`strike ${cmp.nearest_strike} · exp ${cmp.expiry_used}`}
                  value={cmp.our_model_price}
                  err={`${cmp.model_minus_market > 0 ? "+" : ""}${fmtNum(cmp.model_minus_market, 3)}`} />
              </div>
              {cmp.verdict && (
                <div className="card-note" style={{ marginTop: "0.7rem" }}>
                  <strong>Verdict:</strong> {cmp.verdict}. {cmp.note}
                </div>
              )}
            </>
          ) : (
            <div style={{ padding: "1.5rem 0.5rem", color: "var(--text-muted)", fontSize: "0.86rem", lineHeight: 1.6 }}>
              {cmp?.message || "No listed option chain available."}
              <div style={{ marginTop: "0.6rem" }}>
                Indices and FX pairs generally have no chain on Yahoo Finance. Try a large
                single stock such as <strong>AAPL</strong>, <strong>MSFT</strong>,{" "}
                <strong>NVDA</strong> or <strong>SPY</strong> to see the premium computed against
                real quotes.
              </div>
            </div>
          )}
        </motion.div>

        {/* Calibrated smile */}
        {smile.data?.smile && (
          <motion.div className="card" variants={item} style={{ gridColumn: "1 / -1" }}>
            <div className="card-header">
              <div>
                <div className="card-title">
                  Volatility Smile — Calibrated to {ticker}
                  <InfoTip text="Each curve is the Black-Scholes implied volatility that would reproduce that model's price at each strike. Black-Scholes is flat by construction. Merton and Heston bend, and where a real chain exists the market's own points are overlaid so you can see which model tracks reality." />
                </div>
                <div className="card-subtitle">
                  Jump and Heston parameters fitted from this ticker's own return history
                </div>
              </div>
            </div>
            <SmileChart smile={smile.data} showMarket />
            <SmileMetrics metrics={smile.data.metrics} flat={smile.data.flatness_check} />
          </motion.div>
        )}

        {/* Jump calibration */}
        {d.jump_calibration && !d.jump_calibration.error && (
          <motion.div className="card" variants={item}>
            <div className="card-header">
              <div>
                <div className="card-title">
                  Jump Calibration
                  <InfoTip text="Returns beyond 3 robust standard deviations are classified as jumps. Robust means MAD-based, so the outliers we are hunting do not inflate the threshold used to find them. The diffusive volatility is then estimated from the remaining returns only, so jump variance is not counted twice." />
                </div>
                <div className="card-subtitle">Merton parameters fitted from {ticker}'s return distribution</div>
              </div>
            </div>
            <div className="stats-grid">
              <StatBox value={d.jump_calibration.lambda_jump} label="Jumps / Year" highlight
                tip="Estimated jump frequency λ." />
              <StatBox value={`${(d.jump_calibration.mu_jump * 100).toFixed(2)}%`} label="Mean Jump"
                cls={d.jump_calibration.mu_jump < 0 ? "negative" : "positive"}
                tip="Average jump size in log terms. Negative means downward jumps dominate — crashes are sharper than rallies." />
              <StatBox value={`${(d.jump_calibration.sigma_jump * 100).toFixed(2)}%`} label="Jump σ"
                tip="Dispersion of jump sizes." />
              <StatBox value={`${(d.jump_calibration.sigma_diffusive * 100).toFixed(1)}%`} label="Diffusive σ"
                tip="Annualised volatility of the NON-jump returns. Kept separate so the jump component is not double-counted." />
              <StatBox value={d.jump_calibration.num_jumps_detected} label="Jumps Found"
                tip={`Over ${d.jump_calibration.years_observed} years of data.`} />
              <StatBox value={`${d.jump_calibration.threshold_pct}%`} label="Threshold"
                tip="Daily move required to be classified as a jump." />
            </div>
            <div className="card-note" style={{ marginTop: "0.7rem" }}>
              {d.jump_calibration.method}
            </div>
          </motion.div>
        )}

        {/* Heston calibration + validation */}
        <motion.div className="card" variants={item}>
          <div className="card-header">
            <div>
              <div className="card-title">
                Heston Calibration &amp; Validation
                <InfoTip text="Heston is seeded from GARCH rather than fitted separately — the two describe the same volatility dynamics, one in discrete time and one in continuous time. The validation checks below confirm the pricing code is correct without assuming any model is true." />
              </div>
              <div className="card-subtitle">GARCH → Heston parameter mapping, plus arbitrage checks</div>
            </div>
          </div>
          <div className="model-rows">
            <ModelRow name="v₀ (current variance)" sub="from GARCH conditional variance"
              value={d.heston_calibration?.v0} />
            <ModelRow name="θ (long-run variance)" sub="from GARCH unconditional variance"
              value={d.heston_calibration?.theta_long_run_variance} />
            <ModelRow name="κ (reversion speed)" sub="−ln(persistence) × 252"
              value={d.heston_calibration?.kappa} />
            <ModelRow name="ξ (vol-of-vol)" sub="capped to satisfy Feller"
              value={d.heston_calibration?.xi_vol_of_vol} />
            <ModelRow name="ρ (spot/vol corr)" sub="leverage effect"
              value={d.heston_calibration?.rho} />
          </div>
          <div style={{ marginTop: "0.9rem" }}>
            <CheckRow
              ok={d.validation?.put_call_parity?.parity_holds}
              label="Put-call parity"
              detail={`violation ${d.validation?.put_call_parity?.abs_violation ?? "—"}`}
              tip="C − P = S·e^(−qT) − K·e^(−rT). Pure arbitrage, true regardless of model. A violation would mean a risk-free profit exists." />
            <CheckRow
              ok={d.heston_calibration?.feller_satisfied}
              label="Feller condition (2κθ ≥ ξ²)"
              detail={d.heston_calibration?.feller_satisfied ? "satisfied" : "violated"}
              tip="When satisfied, the Heston variance process never reaches zero. If violated, the numerical scheme's treatment of negative variance starts to matter for the price." />
          </div>
          <div className="card-note" style={{ marginTop: "0.7rem" }}>
            {d.heston_calibration?.mapping}
          </div>
        </motion.div>
      </div>
    </>
  );
}

/* ==========================================================================
   THEORY MODE
   ========================================================================== */

function TheoryMode({ theory, setTheory, resetTheory, smileParams, setSmileParams, resetSmile }) {
  const key = JSON.stringify(theory);
  const smileKey = JSON.stringify({ ...theory, ...smileParams });

  const multi = useApiData(() => getOptionsMultiMarket(theory), [key]);
  const smile = useApiData(
    () => getOptionsSmile({
      spot: theory.spot, t_years: theory.t_years, rate: theory.rate,
      sigma: theory.sigma, dividend: theory.dividend, ...smileParams,
    }),
    [smileKey]
  );
  const conv = useApiData(
    () => getBinomialConvergence({ ...theory, option: "put" }),
    [key]
  );

  return (
    <>
      <motion.div className="card" variants={item} style={{ marginBottom: "1.25rem" }}>
        <div className="card-header">
          <div>
            <div className="card-title">
              Model Parameters
              <InfoTip text="Drive the models directly. Hover any label for what that input means and which direction it pushes the price." />
            </div>
            <div className="card-subtitle">Press Enter or click away to apply</div>
          </div>
        </div>
        <ParamControls fields={THEORY_FIELDS} values={theory} onChange={setTheory} onReset={resetTheory} />
      </motion.div>

      {multi.loading && <LoadingState message="Pricing across all models…" subtext="Closed forms, lattices, Monte Carlo and validation" />}
      {multi.error && !multi.loading && <ErrorState message={multi.error} onRetry={multi.reload} />}

      {!multi.loading && !multi.error && multi.data && (
        <div className="charts-grid">
          {/* Cross-market closed forms */}
          <motion.div className="card" variants={item}>
            <div className="card-header">
              <div>
                <div className="card-title">
                  One Engine, Four Markets
                  <InfoTip text="All four formulae share a single implementation and differ only in how the underlying carries: BSM uses a dividend yield q, Garman-Kohlhagen sets q = the foreign interest rate, Black-76 sets q = r because futures have no carry, and Bachelier replaces lognormal prices with normal ones." />
                </div>
                <div className="card-subtitle">Same option, different market conventions</div>
              </div>
            </div>
            <div className="model-rows">
              <ModelRow name="Black-Scholes-Merton" sub="equities, dividend yield q"
                value={multi.data.closed_form_models?.bsm_equity} />
              <ModelRow name="Garman-Kohlhagen" sub="FX, q = foreign rate"
                value={multi.data.closed_form_models?.garman_kohlhagen_forex} />
              <ModelRow name="Black-76" sub="futures/commodities, q = r"
                value={multi.data.closed_form_models?.black76_commodities} />
              <ModelRow name="Bachelier (1900)" sub="normal, permits negative prices"
                value={multi.data.closed_form_models?.bachelier_normal} />
            </div>
            <div className="card-note" style={{ marginTop: "0.7rem" }}>
              Bachelier predates Black-Scholes by 73 years and allows negative prices — a defect for
              equities, but exactly right for spread options and for WTI crude in April 2020, when
              futures settled below zero and lognormal models could not represent the state at all.
            </div>
          </motion.div>

          {/* Greeks */}
          <motion.div className="card" variants={item}>
            <div className="card-header">
              <div>
                <div className="card-title">
                  Greeks
                  <InfoTip text="Every value is cross-checked against a central finite difference of the pricer. Agreement below 1e-4 confirms the hand-derived analytical formulae." />
                </div>
                <div className="card-subtitle">Analytical, verified numerically</div>
              </div>
            </div>
            <GreeksTable greeks={multi.data.greeks} />
            <div style={{ marginTop: "0.8rem" }}>
              <CheckRow ok={multi.data.validation?.put_call_parity?.parity_holds}
                label="Put-call parity"
                detail={`violation ${multi.data.validation?.put_call_parity?.abs_violation ?? "—"}`}
                tip="Model-independent arbitrage identity." />
              <CheckRow ok={multi.data.validation?.greeks_finite_difference?.all_match}
                label="Greeks vs finite difference"
                detail={`max diff ${multi.data.validation?.greeks_finite_difference?.max_abs_difference ?? "—"}`}
                tip="Central differences have O(h²) error, so close agreement validates the closed forms." />
              <CheckRow ok={multi.data.validation?.monte_carlo_vs_analytic?.within_3_se}
                label="Monte Carlo vs analytic"
                detail={`Δ ${multi.data.validation?.monte_carlo_vs_analytic?.abs_diff ?? "—"} (±${multi.data.validation?.monte_carlo_vs_analytic?.std_error ?? "—"})`}
                tip="Simulation should land within about three standard errors of the closed form." />
            </div>
          </motion.div>

          {/* THE SMILE — headline result */}
          <motion.div className="card" variants={item} style={{ gridColumn: "1 / -1" }}>
            <div className="card-header">
              <div>
                <div className="card-title">
                  The Volatility Smile — Why Black-Scholes Is Not Enough
                  <InfoTip text="Price each strike with the richer model, then ask what single Black-Scholes volatility reproduces that price. Black-Scholes answers with a flat line because it assumes one constant volatility. Merton's jumps and Heston's random volatility both bend the curve, and negative jump-mean / negative correlation tilt it into the downward skew that real index options show." />
                </div>
                <div className="card-subtitle">
                  Implied volatility by strike · Black-Scholes is flat by construction
                </div>
              </div>
            </div>
            <div style={{ marginBottom: "1rem" }}>
              <ParamControls fields={SMILE_FIELDS} values={smileParams} onChange={setSmileParams} onReset={resetSmile} />
            </div>
            {smile.loading && <LoadingState message="Generating smiles…" subtext="Inverting Merton and Heston prices for implied volatility" />}
            {smile.error && !smile.loading && <ErrorState message={smile.error} onRetry={smile.reload} />}
            {smile.data?.smile && (
              <>
                <SmileChart smile={smile.data} />
                <SmileMetrics metrics={smile.data.metrics} flat={smile.data.flatness_check} />
                <div className="card-note" style={{ marginTop: "0.8rem" }}>
                  Try setting <strong>vol-of-vol ξ</strong> near zero — Heston collapses onto the flat
                  Black-Scholes line, because randomness in volatility is precisely what creates the
                  smile. Then set <strong>ρ</strong> to 0 and watch the skew straighten into a
                  symmetric smile: the tilt comes from the leverage effect, not the volatility
                  randomness itself.
                </div>
              </>
            )}
          </motion.div>

          {/* SDE Monte Carlo */}
          <motion.div className="card" variants={item}>
            <div className="card-header">
              <div>
                <div className="card-title">
                  Stochastic Models vs Exact Benchmarks
                  <InfoTip text="Each Monte Carlo estimate sits next to the exact price for the same model — a Poisson series for Merton, Fourier inversion of the characteristic function for Heston. Agreement within three standard errors is the correctness criterion, and it is a much stronger claim than 'the simulation looks plausible'." />
                </div>
                <div className="card-subtitle">Simulation validated against analytic solutions</div>
              </div>
            </div>
            <div className="model-rows">
              <ModelRow name="GBM Monte Carlo" sub="antithetic + control variate"
                value={multi.data.stochastic_models?.gbm_monte_carlo?.price}
                err={`± ${fmtNum(multi.data.stochastic_models?.gbm_monte_carlo?.std_error, 4)}`} />
              <ModelRow name="Merton (Monte Carlo)" sub="Poisson jumps, one-step exact"
                value={multi.data.stochastic_models?.merton_jump_diffusion?.price}
                err={`± ${fmtNum(multi.data.stochastic_models?.merton_jump_diffusion?.std_error, 4)}`} />
              <ModelRow name="Merton (closed form)" sub="Poisson-weighted BS series"
                value={multi.data.stochastic_models?.merton_jump_diffusion?.analytic_price} />
              <ModelRow name="Heston (Monte Carlo)" sub="log-Euler, full truncation"
                value={multi.data.stochastic_models?.heston_stochastic_volatility?.price}
                err={`± ${fmtNum(multi.data.stochastic_models?.heston_stochastic_volatility?.std_error, 4)}`} />
              <ModelRow name="Heston (semi-analytic)" sub="Fourier inversion"
                value={multi.data.stochastic_models?.heston_stochastic_volatility?.analytic_price} />
            </div>
            <div style={{ marginTop: "0.8rem" }}>
              <CheckRow ok={multi.data.stochastic_models?.merton_jump_diffusion?.within_3_se}
                label="Merton: MC matches closed form"
                detail={`Δ ${multi.data.stochastic_models?.merton_jump_diffusion?.abs_diff_vs_analytic ?? "—"}`}
                tip="The Poisson series is exact, so this validates the simulation." />
              <CheckRow ok={multi.data.stochastic_models?.heston_stochastic_volatility?.within_3_se}
                label="Heston: MC matches Fourier price"
                detail={`Δ ${multi.data.stochastic_models?.heston_stochastic_volatility?.abs_diff_vs_analytic ?? "—"}`}
                tip="Heston needs time-stepping, so a little discretisation bias remains — which is exactly why the comparison is shown." />
            </div>
          </motion.div>

          {/* Binomial convergence */}
          {conv.data?.convergence && (
            <motion.div className="card" variants={item} style={{ gridColumn: "1 / -1" }}>
              <div className="card-header">
                <div>
                  <div className="card-title">
                    Lattice Convergence &amp; Early Exercise
                    <InfoTip text="The European lattice price approaches Black-Scholes with error proportional to 1/N, and oscillates on the way because whether a node lands on the strike flips with step parity. The American premium is the extra value of being able to exercise early — positive for puts, exactly zero for calls on a non-dividend stock." />
                  </div>
                  <div className="card-subtitle">
                    Put option · analytic Black-Scholes = {conv.data.analytic_black_scholes}
                  </div>
                </div>
              </div>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={conv.data.convergence}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
                    <XAxis dataKey="steps" scale="log" domain={["auto", "auto"]}
                      stroke={CHART.axis} tick={{ fontSize: 11 }}
                      label={{ value: "lattice steps (log)", position: "insideBottom", offset: -4, fill: CHART.axis, fontSize: 10 }} />
                    <YAxis stroke={CHART.axis} tick={{ fontSize: 11 }}
                      label={{ value: "price", angle: -90, position: "insideLeft", fill: CHART.axis, fontSize: 10 }} />
                    <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} />
                    <Legend />
                    <ReferenceLine y={conv.data.analytic_black_scholes} stroke={CHART.gold}
                      strokeDasharray="5 5"
                      label={{ value: "Black-Scholes", fill: CHART.gold, fontSize: 10, position: "right" }} />
                    <Line type="monotone" dataKey="european" stroke={CHART.teal} strokeWidth={1.8}
                      dot={{ r: 2.5 }} name="European lattice" />
                    <Line type="monotone" dataKey="american" stroke={CHART.violet} strokeWidth={1.8}
                      dot={{ r: 2.5 }} name="American lattice" />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
              <div style={{ overflowX: "auto", marginTop: "0.9rem", maxHeight: 260, overflowY: "auto" }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Steps</th><th>European</th><th>Abs Error</th>
                      <th>American</th><th>Early-Exercise Premium</th>
                    </tr>
                  </thead>
                  <tbody>
                    {conv.data.convergence.map((r) => (
                      <tr key={r.steps}>
                        <td>{r.steps}</td>
                        <td>{r.european}</td>
                        <td className={r.abs_error < 0.01 ? "significant" : ""}>{r.abs_error}</td>
                        <td>{r.american}</td>
                        <td className={r.early_exercise_premium > 0 ? "significant" : "not-significant"}>
                          {r.early_exercise_premium}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="card-note" style={{ marginTop: "0.7rem" }}>
                {conv.data.interpretation}
              </div>
            </motion.div>
          )}
        </div>
      )}
    </>
  );
}

/* ==========================================================================
   Shared sub-components
   ========================================================================== */

function StatBox({ value, label, tip, highlight, cls }) {
  const klass = cls || (highlight ? "highlight" : "neutral");
  return (
    <div className="stat-box">
      <div className={`stat-value ${klass}`}>{value ?? "—"}</div>
      <div className="stat-label">
        {tip ? <LabelWithTip tip={tip}>{label}</LabelWithTip> : label}
      </div>
    </div>
  );
}

function ModelRow({ name, sub, value, err }) {
  return (
    <div className="model-row">
      <div>
        <div className="model-row-name">{name}</div>
        {sub && <div className="model-row-sub">{sub}</div>}
      </div>
      <div className="model-row-value">{value ?? "—"}</div>
      <div className="model-row-err">{err || ""}</div>
    </div>
  );
}

function CheckRow({ ok, label, detail, tip }) {
  return (
    <div className={`check-row ${ok ? "pass" : "fail"}`}>
      <span className="check-ico">
        <Icon name={ok ? "check" : "alert"} size={15} />
      </span>
      {tip ? <LabelWithTip tip={tip}>{label}</LabelWithTip> : label}
      <span className="check-detail">{detail}</span>
    </div>
  );
}

const GREEK_TIPS = {
  delta: "∂V/∂S — how much the option value moves per $1 of underlying. Also the hedge ratio: shares to hold per option sold.",
  gamma: "∂²V/∂S² — how fast delta itself changes. High gamma means the hedge needs constant rebalancing, which is where hedging costs actually come from.",
  vega: "∂V/∂σ per 1 percentage point of volatility. Identical for calls and puts, because put-call parity differs by a term that has no volatility in it.",
  theta: "∂V/∂t per calendar day — time decay. Usually negative: an option loses value simply because expiry approaches.",
  rho: "∂V/∂r per 1 percentage point of interest rate. Positive for calls, negative for puts.",
  vanna: "∂²V/∂S∂σ — how delta drifts as volatility moves. Central to FX risk-reversal trading.",
  volga: "∂²V/∂σ² — vega convexity. This is why volatility-of-volatility carries a price.",
  prob_itm_risk_neutral: "N(d₂) for a call — the risk-neutral probability of finishing in the money. Not a real-world probability.",
  d1: "d₁ — the standardised log-moneyness under the share measure. N(d₁) is delta.",
  d2: "d₂ = d₁ − σ√T. N(d₂) is the risk-neutral exercise probability.",
};

const GREEK_ORDER = [
  ["delta", "Delta", "per $1 spot"],
  ["gamma", "Gamma", "delta per $1 spot"],
  ["vega", "Vega", "per 1% vol"],
  ["theta", "Theta", "per day"],
  ["rho", "Rho", "per 1% rate"],
  ["vanna", "Vanna", "delta per 1% vol"],
  ["volga", "Volga", "vega per 1% vol"],
];

function GreeksTable({ greeks }) {
  if (!greeks) return null;
  return (
    <>
      <div className="model-rows">
        {GREEK_ORDER.map(([key, label, unit]) => (
          <div className="model-row" key={key}>
            <div>
              <div className="model-row-name">
                <LabelWithTip tip={GREEK_TIPS[key]}>{label}</LabelWithTip>
              </div>
              <div className="model-row-sub">{unit}</div>
            </div>
            <div className="model-row-value">{greeks[key] ?? "—"}</div>
            <div className="model-row-err">
              {key === "delta" || key === "gamma" ? "1st/2nd order" : ""}
            </div>
          </div>
        ))}
      </div>
      <div className="evidence-chips" style={{ marginTop: "0.7rem" }}>
        {["d1", "d2", "prob_itm_risk_neutral"].map((k) =>
          greeks[k] !== undefined ? (
            <span className="evidence-chip" key={k}>
              <LabelWithTip tip={GREEK_TIPS[k]}>{k.replace(/_/g, " ")}</LabelWithTip>
              : <b>{greeks[k]}</b>
            </span>
          ) : null
        )}
      </div>
    </>
  );
}

function SmileChart({ smile, showMarket }) {
  const data = useMemo(() => {
    const rows = (smile.smile || []).map((r) => ({
      moneyness: r.moneyness,
      bs: r.bs_iv,
      merton: r.merton_iv,
      heston: r.heston_iv,
    }));
    if (showMarket && smile.market_observed?.points?.length) {
      // Merge the observed market points onto the nearest model moneyness so a
      // single x-axis carries both, letting the eye compare directly.
      smile.market_observed.points.forEach((p) => {
        let best = null, bestD = Infinity;
        rows.forEach((row) => {
          const d = Math.abs(row.moneyness - p.moneyness);
          if (d < bestD) { bestD = d; best = row; }
        });
        if (best && bestD < 0.03) best.market = p.market_iv_pct;
      });
    }
    return rows;
  }, [smile, showMarket]);

  const hasMarket = showMarket && data.some((d) => d.market !== undefined);

  return (
    <div className="chart-container tall">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
          <XAxis dataKey="moneyness" stroke={CHART.axis} tick={{ fontSize: 11 }}
            tickFormatter={(v) => v.toFixed(2)}
            label={{ value: "moneyness (K / S)", position: "insideBottom", offset: -4, fill: CHART.axis, fontSize: 10 }} />
          <YAxis stroke={CHART.axis} tick={{ fontSize: 11 }}
            label={{ value: "implied vol %", angle: -90, position: "insideLeft", fill: CHART.axis, fontSize: 10 }} />
          <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle}
            formatter={(v, n) => [v != null ? `${Number(v).toFixed(2)}%` : "—", n]}
            labelFormatter={(v) => `K/S = ${Number(v).toFixed(3)}`} />
          <Legend />
          <ReferenceLine x={1.0} stroke={CHART.axis} strokeDasharray="3 3"
            label={{ value: "ATM", fill: CHART.axis, fontSize: 10, position: "top" }} />
          <Line type="monotone" dataKey="bs" stroke={CHART.gold} strokeWidth={2} dot={false}
            name="Black-Scholes (flat)" />
          <Line type="monotone" dataKey="merton" stroke={CHART.cyan} strokeWidth={2} dot={false}
            name="Merton (jumps)" />
          <Line type="monotone" dataKey="heston" stroke={CHART.violet} strokeWidth={2} dot={false}
            name="Heston (stoch. vol)" />
          {hasMarket && (
            <Scatter dataKey="market" fill={CHART.up} name="Market (observed)"
              shape="circle" legendType="circle" />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function SmileMetrics({ metrics, flat }) {
  if (!metrics) return null;
  const rows = [
    ["Black-Scholes", metrics.black_scholes, flat?.bs_iv_std, CHART.gold],
    ["Merton", metrics.merton, flat?.merton_iv_std, CHART.cyan],
    ["Heston", metrics.heston, flat?.heston_iv_std, CHART.violet],
  ];
  return (
    <div style={{ overflowX: "auto", marginTop: "0.9rem" }}>
      <table className="data-table">
        <thead>
          <tr>
            <th>Model</th>
            <th><LabelWithTip tip="Implied volatility at the money (K ≈ S).">ATM IV</LabelWithTip></th>
            <th><LabelWithTip tip="Average implied vol of out-of-the-money puts (K ≤ 0.92·S) — the crash-protection strikes.">OTM Put IV</LabelWithTip></th>
            <th><LabelWithTip tip="Average implied vol of out-of-the-money calls (K ≥ 1.08·S).">OTM Call IV</LabelWithTip></th>
            <th><LabelWithTip tip="Put IV minus call IV. Positive means a downward skew: crash protection costs more. Real equity indices show a clear positive skew.">Skew</LabelWithTip></th>
            <th><LabelWithTip tip="Curvature of the smile: (put + call − 2×ATM). Positive means both wings sit above the middle, i.e. fat tails on both sides.">Curvature</LabelWithTip></th>
            <th><LabelWithTip tip="Standard deviation of implied vol across all strikes. Exactly zero for Black-Scholes, which is the whole point — it cannot produce a smile.">IV Spread</LabelWithTip></th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([name, m, std, color]) => (
            <tr key={name}>
              <td style={{ color, fontWeight: 600 }}>{name}</td>
              <td>{m ? `${m.atm_iv_pct}%` : "—"}</td>
              <td>{m ? `${m.otm_put_iv_pct}%` : "—"}</td>
              <td>{m ? `${m.otm_call_iv_pct}%` : "—"}</td>
              <td className={m && m.skew_put_minus_call > 0.5 ? "significant" : ""}>
                {m ? `${m.skew_put_minus_call > 0 ? "+" : ""}${m.skew_put_minus_call}` : "—"}
              </td>
              <td>{m ? m.smile_curvature : "—"}</td>
              <td className={std === 0 ? "not-significant" : "significant"}>
                {std !== undefined ? fmtNum(std, 3) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
