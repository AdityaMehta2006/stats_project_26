/**
 * GarchVolatility.jsx
 * --------------------
 * Pillar 2: GARCH & Volatility Clustering dashboard panel.
 * Supports any ticker. Shows conditional volatility, return distribution,
 * QQ plot, volatility clustering ACF, and model comparison.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import {
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, ScatterChart, Scatter,
  AreaChart, Area, Cell, ReferenceLine
} from "recharts";
import useApiData from "../hooks/useApiData";
import { getGarchFit, getGarchClustering, getGarchDistribution, getGarchCompare } from "../api";
import { LoadingState, ErrorState } from "./common/StatusStates";
import TickerSearch from "./common/TickerSearch";
import Icon from "./common/Icon";
import { InfoTip, LabelWithTip } from "./common/Tooltip";
import { CHART, tooltipStyle, tooltipLabelStyle, tooltipItemStyle } from "../theme";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.1 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

export default function GarchVolatility() {
  const [ticker, setTicker] = useState("^GSPC");

  const garch = useApiData(() => getGarchFit(ticker), [ticker]);
  const clustering = useApiData(() => getGarchClustering(ticker), [ticker]);
  const dist = useApiData(() => getGarchDistribution(ticker), [ticker]);
  const compare = useApiData(() => getGarchCompare(ticker), [ticker]);

  const loading = garch.loading || clustering.loading || dist.loading || compare.loading;
  const error = garch.error || clustering.error || dist.error || compare.error;

  return (
    <motion.div variants={container} initial="hidden" animate="show">
      <motion.div className="section-header" variants={item}>
        <div className="section-ico garch"><Icon name="activity" size={24} /></div>
        <div>
          <h2>GARCH & Volatility Clustering</h2>
          <p>Modeling time-varying risk and testing for fat tails in returns</p>
        </div>
      </motion.div>

      <motion.div className="section-intro" variants={item}>
        <span className="intro-ico"><Icon name="info" size={18} /></span>
        <span>
          Market risk is not constant — big moves cluster together (<strong>volatility
          clustering</strong>), and crashes happen more often than a bell curve predicts
          (<strong>fat tails</strong>). A <strong>GARCH(1,1)</strong> model captures this by
          letting today's expected volatility depend on yesterday's shock and yesterday's
          volatility. The charts below show that estimated risk over time and quantify how
          far returns stray from normality.
        </span>
      </motion.div>

      {/* Ticker selector */}
      <motion.div variants={item} className="toolbar-card">
        <TickerSearch value={ticker} onSelect={setTicker} label="Analyze Ticker" />
      </motion.div>

      {loading && <LoadingState message={`Fitting GARCH model for ${ticker}…`} subtext="This may take a moment for new tickers" />}
      {error && !loading && <ErrorState message={error} onRetry={() => { garch.reload(); clustering.reload(); dist.reload(); compare.reload(); }} />}

      {!loading && !error && (
        <>
          {garch.data && (
            <motion.div className="stats-grid" variants={item}>
              <div className="stat-box">
                <div className="stat-value highlight">{garch.data.persistence}</div>
                <div className="stat-label">
                  <LabelWithTip tip="α + β. How long volatility shocks last. Close to 1 means today's turbulence fades very slowly — risk is highly persistent.">
                    Persistence (α+β)
                  </LabelWithTip>
                </div>
              </div>
              <div className="stat-box">
                <div className="stat-value neutral">{garch.data.aic}</div>
                <div className="stat-label">
                  <LabelWithTip tip="Akaike Information Criterion — a model-quality score balancing fit and complexity. Lower is better; only meaningful when comparing models.">
                    AIC
                  </LabelWithTip>
                </div>
              </div>
              <div className="stat-box">
                <div className="stat-value neutral">{garch.data.n_obs}</div>
                <div className="stat-label">
                  <LabelWithTip tip="Number of daily return observations used to fit the model.">
                    Observations
                  </LabelWithTip>
                </div>
              </div>
              {dist.data?.descriptive_stats && (
                <>
                  <div className="stat-box">
                    <div className={`stat-value ${dist.data.descriptive_stats.kurtosis > 3 ? "negative" : "positive"}`}>
                      {dist.data.descriptive_stats.kurtosis}
                    </div>
                    <div className="stat-label">
                      <LabelWithTip tip="Excess kurtosis measures tail fatness vs a normal curve (0 = normal). Large positive values mean extreme moves are far more likely than the bell curve assumes.">
                        Excess Kurtosis
                      </LabelWithTip>
                    </div>
                  </div>
                  <div className="stat-box">
                    <div className="stat-value neutral">{dist.data.descriptive_stats.skewness}</div>
                    <div className="stat-label">
                      <LabelWithTip tip="Asymmetry of returns. Negative skew means crashes (large down days) are bigger/more frequent than rallies.">
                        Skewness
                      </LabelWithTip>
                    </div>
                  </div>
                </>
              )}
            </motion.div>
          )}

          <div className="charts-grid">
            {/* Conditional Volatility */}
            {garch.data?.conditional_volatility && (
              <motion.div className="card" variants={item} style={{ gridColumn: "1 / -1" }}>
                <div className="card-header">
                  <div>
                    <div className="card-title">
                      Conditional Volatility — {ticker}
                      <InfoTip text="The model's day-by-day estimate of risk (σ). Tall sustained humps are turbulent regimes; flat stretches are calm markets." />
                    </div>
                    <div className="card-subtitle">GARCH(1,1) with Student-t distribution</div>
                  </div>
                </div>
                <div className="chart-container tall">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={garch.data.conditional_volatility}>
                      <defs>
                        <linearGradient id="volGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={CHART.teal} stopOpacity={0.35} />
                          <stop offset="95%" stopColor={CHART.teal} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
                      <XAxis dataKey="date" stroke={CHART.axis} tick={{ fontSize: 10 }} tickFormatter={v => v.slice(0, 7)} interval={Math.floor(garch.data.conditional_volatility.length / 8)} />
                      <YAxis stroke={CHART.axis} tick={{ fontSize: 11 }} />
                      <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} />
                      <Area type="monotone" dataKey="volatility" stroke={CHART.teal} fill="url(#volGradient)" strokeWidth={1.6} name="Cond. Volatility (σ)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>
            )}

            {/* Returns */}
            {garch.data?.returns && (
              <motion.div className="card" variants={item} style={{ gridColumn: "1 / -1" }}>
                <div className="card-header">
                  <div>
                    <div className="card-title">
                      Daily Log Returns (%) — {ticker}
                      <InfoTip text="Notice how large bars (up and down) bunch together in the same periods — that visual clumping is volatility clustering." />
                    </div>
                    <div className="card-subtitle">Calm and turbulent periods alternate — the hallmark of clustering</div>
                  </div>
                </div>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={garch.data.returns} barSize={1.5}>
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
                      <XAxis dataKey="date" stroke={CHART.axis} tick={{ fontSize: 10 }} tickFormatter={v => v.slice(0, 7)} interval={Math.floor(garch.data.returns.length / 8)} />
                      <YAxis stroke={CHART.axis} tick={{ fontSize: 11 }} />
                      <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} />
                      <ReferenceLine y={0} stroke={CHART.axis} strokeDasharray="3 3" />
                      <Bar dataKey="return" name="Return (%)" radius={0}>
                        {garch.data.returns.map((entry, idx) => (
                          <Cell key={idx} fill={entry.return >= 0 ? "rgba(52,211,153,0.75)" : "rgba(248,113,113,0.75)"} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>
            )}

            {/* Return Distribution Histogram */}
            {dist.data?.histogram && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">
                      Return Distribution
                      <InfoTip text="Histogram of daily returns. Fat tails show up as more mass in the far left/right than a normal curve would have. The Jarque-Bera test formalises this." />
                    </div>
                    <div className="card-subtitle">
                      Jarque-Bera: {dist.data.descriptive_stats?.is_normal ?
                        <span className="badge success">Normal</span> :
                        <span className="badge danger">Non-Normal (p={dist.data.descriptive_stats?.jarque_bera_pvalue})</span>
                      }
                    </div>
                  </div>
                </div>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={dist.data.histogram} barSize={6}>
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
                      <XAxis dataKey="bin_mid" stroke={CHART.axis} tick={{ fontSize: 10 }} label={{ value: "Return (%)", position: "bottom", offset: -2, fill: CHART.axis, fontSize: 11 }} />
                      <YAxis stroke={CHART.axis} tick={{ fontSize: 11 }} />
                      <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={{ fill: "rgba(148,163,184,0.06)" }} formatter={(v) => [v, "Count"]} />
                      <Bar dataKey="count" fill={CHART.cyan} radius={[2, 2, 0, 0]} opacity={0.85} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>
            )}

            {/* QQ Plot */}
            {dist.data?.qq_plot && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">
                      Q-Q Plot (Normal)
                      <InfoTip text="Compares actual return quantiles to a normal distribution. Points hugging the gold diagonal = normal; points curling away at the ends = fat tails." />
                    </div>
                    <div className="card-subtitle">Deviation from the diagonal indicates fat tails</div>
                  </div>
                </div>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ left: 10, right: 20, top: 10, bottom: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
                      <XAxis dataKey="theoretical" name="Theoretical" stroke={CHART.axis} tick={{ fontSize: 10 }} label={{ value: "Theoretical Quantiles", position: "bottom", offset: 0, fill: CHART.axis, fontSize: 11 }} />
                      <YAxis dataKey="actual" name="Actual" stroke={CHART.axis} tick={{ fontSize: 10 }} label={{ value: "Sample Quantiles", angle: -90, position: "insideLeft", fill: CHART.axis, fontSize: 11 }} />
                      <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={{ strokeDasharray: "3 3" }} />
                      <Scatter data={dist.data.qq_plot} fill={CHART.teal} fillOpacity={0.6} r={2} />
                      <ReferenceLine segment={[
                        { x: dist.data.qq_plot[0]?.theoretical, y: dist.data.qq_plot[0]?.theoretical },
                        { x: dist.data.qq_plot[dist.data.qq_plot.length - 1]?.theoretical, y: dist.data.qq_plot[dist.data.qq_plot.length - 1]?.theoretical }
                      ]} stroke={CHART.gold} strokeDasharray="5 5" />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>
            )}

            {/* Squared Return ACF */}
            {clustering.data?.squared_return_acf && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">
                      ACF of Squared Returns
                      <InfoTip text="Autocorrelation of squared returns at each lag. Bars staying well above zero prove that big days are followed by big days — i.e. ARCH effects." />
                    </div>
                    <div className="card-subtitle">High autocorrelation = volatility clustering (ARCH effects)</div>
                  </div>
                </div>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={clustering.data.squared_return_acf}>
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
                      <XAxis dataKey="lag" stroke={CHART.axis} tick={{ fontSize: 11 }} label={{ value: "Lag", position: "bottom", offset: -2, fill: CHART.axis, fontSize: 11 }} />
                      <YAxis stroke={CHART.axis} tick={{ fontSize: 11 }} domain={[0, "auto"]} />
                      <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={{ fill: "rgba(148,163,184,0.06)" }} />
                      <Bar dataKey="autocorrelation" fill={CHART.violet} radius={[3, 3, 0, 0]} name="Autocorrelation" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>
            )}

            {/* GARCH Model Comparison */}
            {compare.data?.model_comparison && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">
                      GARCH(1,1) Model Comparison
                      <InfoTip text="Refits the model with different assumptions about the error distribution. The lowest-AIC row (badged 'Best') fits the data most efficiently." />
                    </div>
                    <div className="card-subtitle">Error distribution variants — lower AIC = better fit</div>
                  </div>
                </div>
                <div style={{ overflowX: "auto" }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Distribution</th>
                        <th>AIC</th>
                        <th>BIC</th>
                        <th>Log-Likelihood</th>
                        <th>Persistence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {compare.data.model_comparison.map((m) => {
                        const isBest = m.aic === Math.min(...compare.data.model_comparison.map(x => x.aic));
                        return (
                          <tr key={m.distribution}>
                            <td style={{ color: "var(--text-primary)", fontFamily: "var(--font-main)", fontWeight: isBest ? 600 : 400 }}>
                              {m.distribution} {isBest && <span className="badge success" style={{ marginLeft: 6 }}>Best</span>}
                            </td>
                            <td>{m.aic}</td>
                            <td>{m.bic}</td>
                            <td>{m.log_likelihood}</td>
                            <td>{m.persistence}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}

            {/* GARCH Parameters */}
            {garch.data?.parameters && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">
                      GARCH(1,1) Parameters
                      <InfoTip text="ω (baseline variance), α (reaction to the latest shock) and β (carry-over of past volatility). A significant α and β confirm the model is doing real work." />
                    </div>
                    <div className="card-subtitle">σ²ₜ = ω + α·ε²ₜ₋₁ + β·σ²ₜ₋₁</div>
                  </div>
                </div>
                <div style={{ overflowX: "auto" }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Parameter</th>
                        <th>Value</th>
                        <th>P-Value</th>
                        <th>Significance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(garch.data.parameters).map(([name, param]) => (
                        <tr key={name}>
                          <td style={{ color: "var(--text-primary)", fontFamily: "var(--font-main)" }}>{name}</td>
                          <td>{param.value}</td>
                          <td className={param.p_value < 0.05 ? "significant" : "not-significant"}>{param.p_value}</td>
                          <td>
                            <span className={`badge ${param.p_value < 0.05 ? "success" : "danger"}`}>
                              {param.p_value < 0.05 ? "Significant" : "Not Sig."}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}

            {/* Ljung-Box Test */}
            {clustering.data?.ljung_box_test && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">
                      Ljung-Box Test on Squared Returns
                      <InfoTip text="A formal test for ARCH effects. A p-value below 0.05 means the clustering seen in the ACF chart is statistically real, not noise." />
                    </div>
                    <div className="card-subtitle">p &lt; 0.05 confirms ARCH effects exist</div>
                  </div>
                </div>
                <div style={{ overflowX: "auto" }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Lag</th>
                        <th>LB Statistic</th>
                        <th>P-Value</th>
                        <th>ARCH Effects?</th>
                      </tr>
                    </thead>
                    <tbody>
                      {clustering.data.ljung_box_test.map((r) => (
                        <tr key={r.lag}>
                          <td>{r.lag}</td>
                          <td>{r.lb_stat}</td>
                          <td className={r.lb_pvalue < 0.05 ? "significant" : "not-significant"}>{r.lb_pvalue}</td>
                          <td>
                            <span className={`badge ${r.lb_pvalue < 0.05 ? "success" : "warning"}`}>
                              {r.lb_pvalue < 0.05 ? "Confirmed" : "Not Detected"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}
          </div>
        </>
      )}
    </motion.div>
  );
}
