/**
 * Options.jsx
 * -----------
 * Pillar 4: Black-Scholes options pricing.
 *
 * The point of this panel is not the Greeks table — it is the one comparison
 * underneath it: what the market charges for volatility versus how much the
 * asset has actually moved. Rich premium favours selling it, cheap favours
 * buying it. The same reading feeds the engine's vol-mispricing detector.
 *
 * The volatility we compare against is *realised* (1-year daily returns), not a
 * GARCH forecast — labelled as such everywhere, because calling it a forecast
 * when it isn't one is the kind of small lie a dashboard never recovers from.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import useApiData from "../hooks/useApiData";
import { useTicker } from "../ticker";
import { getBlackScholes } from "../api";
import { ErrorState, StatsSkeleton, ChartSkeleton } from "./common/StatusStates";
import TickerSearch from "./common/TickerSearch";
import TimeRangeFilter from "./common/TimeRangeFilter";
import Icon from "./common/Icon";
import { InfoTip, LabelWithTip } from "./common/Tooltip";
import { fmtPct, fmtNum } from "../utils/format";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.1 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

/** Δ Γ ν Θ ρ, each with the unit the backend actually scaled it to. */
const GREEKS = [
  ["delta", "Δ Delta", "Change in option price per $1 move in the underlying. Also reads as the rough probability of finishing in the money."],
  ["gamma", "Γ Gamma", "How fast delta itself changes. High gamma means the position's directional exposure shifts quickly as price moves."],
  ["vega",  "ν Vega",  "Change in option price per 1 percentage point move in volatility. This is the lever the rich/cheap verdict above is about."],
  ["theta", "Θ Theta", "Value lost per calendar day, all else equal. The cost of holding the option through time."],
  ["rho",   "ρ Rho",   "Change in option price per 1 percentage point move in the risk-free rate. Usually the smallest of the five."],
];

/**
 * Deliberately off the bull/bear palette. In this dashboard red means bearish and
 * green means bullish, and "premium is expensive" is neither — it is a statement
 * about what the market charges for vol, not about direction.
 */
const VERDICT_BADGE = (v = "") =>
  v.startsWith("rich") ? "warning" : v.startsWith("cheap") ? "info" : "muted";

export default function Options() {
  const { ticker, setTicker } = useTicker();
  const [side, setSide] = useState("call");
  // Committed values — not every keystroke. Each change is a backend request
  // that re-fetches a live option chain.
  const [strike, setStrike] = useState("");
  const [strikeDraft, setStrikeDraft] = useState("");
  const [expiry, setExpiry] = useState("");

  const opt = useApiData(
    () => getBlackScholes(ticker, side, strike || null, expiry || null),
    [ticker, side, strike, expiry],
    "options-bs"
  );

  const d = opt.data;
  const firstLoad = opt.loading && !d;
  const refetching = opt.loading && Boolean(d);

  const mkt = d?.market;
  const ratio =
    mkt?.market_implied_vol && mkt?.model_volatility
      ? mkt.market_implied_vol / mkt.model_volatility
      : null;

  const commitStrike = () => setStrike(strikeDraft.trim());

  return (
    <motion.div variants={container} initial="hidden" animate="show"
      className={refetching ? "is-refetching" : undefined}>
      <motion.div className="section-header" variants={item}>
        <div className="section-ico options"><Icon name="contract" size={24} /></div>
        <div>
          <h2>Options & Implied Volatility</h2>
          <p>Black-Scholes fair value, the Greeks, and whether the market is overcharging for risk</p>
        </div>
      </motion.div>

      <motion.div className="section-intro" variants={item}>
        <span className="intro-ico"><Icon name="info" size={18} /></span>
        <span>
          <strong>Black-Scholes-Merton</strong> gives a fair price for an option from five
          inputs: spot, strike, time to expiry, the risk-free rate, and volatility. Four of
          those are observable — <strong>volatility is the guess</strong>. So the model can be
          run backwards: take the price the market is actually paying and solve for the
          volatility it implies. When that <strong>implied volatility</strong> sits well above
          what the asset has realised, option premium is expensive; well below, it is cheap.
        </span>
      </motion.div>

      <motion.div variants={item} className="toolbar-card">
        <TickerSearch value={ticker} onSelect={setTicker} label="Analyze Ticker" />

        <div className="trf-wrap">
          <span className="trf-label">Side</span>
          <TimeRangeFilter
            value={side}
            onChange={setSide}
            ranges={["call", "put"]}
            layoutId="options-side"
          />
        </div>

        {/* Spot in the placeholder is rounded: it hints that blank means
            at-the-money, it is not a readout. Exact spot is in Pricing Inputs. */}
        <div className="trf-wrap">
          <label className="trf-label" htmlFor="opt-strike">Strike</label>
          <input
            id="opt-strike"
            className="opt-input"
            type="number"
            step="any"
            inputMode="decimal"
            value={strikeDraft}
            placeholder={d?.inputs?.spot ? `ATM ${Math.round(d.inputs.spot)}` : "At the money"}
            onChange={(e) => setStrikeDraft(e.target.value)}
            onBlur={commitStrike}
            onKeyDown={(e) => e.key === "Enter" && commitStrike()}
          />
        </div>

        <div className="trf-wrap">
          <label className="trf-label" htmlFor="opt-expiry">Expiry</label>
          <select
            id="opt-expiry"
            className="opt-select"
            value={expiry}
            onChange={(e) => setExpiry(e.target.value)}
          >
            <option value="">Nearest ~30 days</option>
            {(d?.expiries || []).map((e) => (
              <option key={e} value={e}>{e}</option>
            ))}
          </select>
        </div>
      </motion.div>

      {firstLoad && (
        <>
          <StatsSkeleton boxes={5} />
          <div className="charts-grid">
            <ChartSkeleton height={260} />
            <ChartSkeleton height={260} />
          </div>
        </>
      )}
      {opt.error && !firstLoad && <ErrorState message={opt.error} onRetry={opt.reload} />}

      {!firstLoad && !opt.error && d && (
        <>
          <motion.div className="stats-grid" variants={item}>
            <div className="stat-box">
              <div className="stat-value highlight">{fmtNum(d.model_price, 2)}</div>
              <div className="stat-label">
                <LabelWithTip tip="What Black-Scholes says the contract is worth, given the current spot, the strike, time to expiry, the 10-year Treasury yield, and realised volatility.">
                  Model Price
                </LabelWithTip>
              </div>
            </div>
            <div className="stat-box">
              <div className="stat-value neutral">{mkt ? fmtNum(mkt.last_price, 2) : "—"}</div>
              <div className="stat-label">
                <LabelWithTip tip="The last traded price for the nearest listed strike on the chosen expiry. Absent when the ticker has no option chain — most indices and FX do not.">
                  Market Last
                </LabelWithTip>
              </div>
            </div>
            <div className="stat-box">
              <div className="stat-value">{mkt ? fmtPct(mkt.market_implied_vol, 1) : "—"}</div>
              <div className="stat-label">
                <LabelWithTip tip="The volatility the market's own price implies, annualized. Solved by running Black-Scholes backwards from the quoted premium.">
                  Implied σ
                </LabelWithTip>
              </div>
            </div>
            <div className="stat-box">
              <div className="stat-value neutral">{fmtPct(d.inputs?.model_volatility, 1)}</div>
              <div className="stat-label">
                <LabelWithTip tip="Annualized standard deviation of the last 252 daily log returns — what the asset has actually done, not a forecast of what it will do.">
                  Realised σ (1Y)
                </LabelWithTip>
              </div>
            </div>
            <div className="stat-box">
              <div className="stat-value text">
                <span className={`badge ${VERDICT_BADGE(mkt?.vol_verdict)}`}>
                  {mkt?.vol_verdict ? mkt.vol_verdict.split(" (")[0] : "no chain"}
                </span>
              </div>
              <div className="stat-label">
                <LabelWithTip tip="Implied divided by realised volatility. Beyond 1.15 the market is charging a premium over what the asset has actually moved; below 0.85 it is charging less.">
                  Premium Verdict
                </LabelWithTip>
              </div>
            </div>
          </motion.div>

          <div className="charts-grid">
            {/* Implied vs realised — the reading this panel exists for */}
            <motion.div className="card" variants={item}>
              <div className="card-header">
                <div>
                  <div className="card-title">
                    Implied vs Realised Volatility
                    <InfoTip text="Two bars, same units. The gap between them is the variance risk premium — what buyers of options pay above what the asset has historically delivered." />
                  </div>
                  <div className="card-subtitle">
                    {mkt
                      ? `${mkt.expiry_used} expiry · strike ${mkt.nearest_strike}`
                      : "No listed option chain for this ticker"}
                  </div>
                </div>
              </div>

              {mkt ? (
                <>
                  <p className="vol-gloss">
                    {ratio > 1.15
                      ? `The market is charging ${ratio.toFixed(2)}× what ${ticker} has actually moved. Premium looks expensive — selling it, or buying spreads rather than outright options, is the side of this with the edge.`
                      : ratio < 0.85
                      ? `The market is charging only ${ratio.toFixed(2)}× what ${ticker} has actually moved. Premium looks cheap — buying it is the side with the edge.`
                      : `Implied and realised volatility are within 15% of each other (${ratio.toFixed(2)}×). There is no premium edge either way here.`}
                  </p>
                  <div className="volbars">
                    <VolBar label="Implied σ" value={mkt.market_implied_vol} max={Math.max(mkt.market_implied_vol, mkt.model_volatility)} tone="implied" />
                    <VolBar label="Realised σ (1Y)" value={mkt.model_volatility} max={Math.max(mkt.market_implied_vol, mkt.model_volatility)} tone="realised" />
                  </div>
                  <table className="data-table">
                    <tbody>
                      <tr>
                        <td>Model price at {mkt.expiry_used}</td>
                        <td>{fmtNum(mkt.model_price_at_expiry, 2)}</td>
                      </tr>
                      <tr>
                        <td>Market last</td>
                        <td>{fmtNum(mkt.last_price, 2)}</td>
                      </tr>
                      <tr>
                        <td>
                          <LabelWithTip tip="Our own Newton/bisection solve on the market price, at that contract's horizon. It will differ a little from the exchange's figure, which uses the mid rather than the last trade and assumes a dividend yield.">
                            Implied σ, our solver
                          </LabelWithTip>
                        </td>
                        <td>{fmtPct(mkt.our_implied_vol, 1)}</td>
                      </tr>
                      <tr>
                        <td>Time to expiry</td>
                        <td>{fmtNum(mkt.T_years, 3)} yr</td>
                      </tr>
                    </tbody>
                  </table>
                </>
              ) : (
                <p className="vol-gloss">
                  Pricing and Greeks above are still valid — they only need spot, a rate and
                  a volatility. The rich/cheap comparison needs listed option quotes, which
                  this ticker does not have. Try a large-cap equity such as AAPL or NVDA.
                </p>
              )}
            </motion.div>

            {/* Greeks */}
            <motion.div className="card" variants={item}>
              <div className="card-header">
                <div>
                  <div className="card-title">
                    Greeks
                    <InfoTip text="The five partial derivatives of the Black-Scholes price. Each one answers 'if exactly one input moved, how much does this option's value change?'" />
                  </div>
                  <div className="card-subtitle">
                    Sensitivities of the {side} at strike {fmtNum(d.inputs?.strike, 2)}
                  </div>
                </div>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Greek</th>
                      <th>Value</th>
                      <th>Per</th>
                    </tr>
                  </thead>
                  <tbody>
                    {GREEKS.map(([key, label, tip]) => (
                      <tr key={key}>
                        <td style={{ color: "var(--text-primary)", fontFamily: "var(--font-main)" }}>
                          <LabelWithTip tip={tip}>{label}</LabelWithTip>
                        </td>
                        <td>{fmtNum(d.greeks?.[key], key === "gamma" ? 6 : 4)}</td>
                        <td className="mono-dim">
                          {key === "delta" ? "$1 spot"
                            : key === "gamma" ? "$1 spot, on delta"
                            : key === "theta" ? "calendar day"
                            : "1% move"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </motion.div>

            {/* Inputs — so nothing on this page is an unexplained number */}
            <motion.div className="card" variants={item} style={{ gridColumn: "1 / -1" }}>
              <div className="card-header">
                <div>
                  <div className="card-title">
                    Pricing Inputs
                    <InfoTip text="Every figure the model was given. Spot comes from the latest close, the rate from the 10-year Treasury yield via FRED, and volatility from realised daily returns." />
                  </div>
                  <div className="card-subtitle">
                    C = S·N(d₁) − K·e^(−rT)·N(d₂) &nbsp;·&nbsp; P = K·e^(−rT)·N(−d₂) − S·N(−d₁)
                  </div>
                </div>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Input</th><th>Symbol</th><th>Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr><td>Spot price</td><td className="mono-dim">S</td><td>{fmtNum(d.inputs?.spot, 2)}</td></tr>
                    <tr><td>Strike</td><td className="mono-dim">K</td><td>{fmtNum(d.inputs?.strike, 2)}</td></tr>
                    <tr><td>Time to expiry</td><td className="mono-dim">T</td><td>{fmtNum(d.inputs?.T_years, 4)} yr</td></tr>
                    <tr><td>Risk-free rate (10Y)</td><td className="mono-dim">r</td><td>{fmtPct(d.inputs?.risk_free_rate, 2)}</td></tr>
                    <tr><td>Realised volatility (1Y)</td><td className="mono-dim">σ</td><td>{fmtPct(d.inputs?.model_volatility, 2)}</td></tr>
                  </tbody>
                </table>
              </div>
            </motion.div>
          </div>
        </>
      )}
    </motion.div>
  );
}

/** One horizontal vol bar. Width carries the comparison, colour only labels it. */
function VolBar({ label, value, max, tone }) {
  return (
    <div className="volbar-row">
      <span className="volbar-label">{label}</span>
      <div className="volbar-track">
        <motion.div
          className={`volbar-fill ${tone}`}
          initial={{ width: 0 }}
          animate={{ width: `${max > 0 ? (value / max) * 100 : 0}%` }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>
      <span className="volbar-value">{fmtPct(value, 1)}</span>
    </div>
  );
}
