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
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, ScatterChart, Scatter,
  AreaChart, Area, Legend, Cell, ReferenceLine
} from "recharts";
import useApiData from "../hooks/useApiData";
import { getGarchFit, getGarchClustering, getGarchDistribution, getGarchCompare } from "../api";
import { LoadingState, ErrorState } from "./common/StatusStates";
import TickerSearch from "./common/TickerSearch";

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
        <h2>🌊 GARCH & Volatility Clustering</h2>
        <p>Modeling time-varying volatility and testing for ARCH effects in equity returns</p>
      </motion.div>

      {/* Ticker selector */}
      <motion.div variants={item} style={{ marginBottom: "1.5rem" }}>
        <div className="card" style={{ padding: "1rem 1.5rem" }}>
          <TickerSearch value={ticker} onSelect={setTicker} label="Analyze Ticker" />
        </div>
      </motion.div>

      {loading && <LoadingState message={`Fitting GARCH model for ${ticker}…`} subtext="This may take a moment for new tickers" />}
      {error && !loading && <ErrorState message={error} onRetry={() => { garch.reload(); clustering.reload(); dist.reload(); compare.reload(); }} />}

      {!loading && !error && (
        <>
          {/* GARCH Summary Stats */}
          {garch.data && (
            <motion.div className="stats-grid" variants={item}>
              <div className="stat-box">
                <div className="stat-value highlight">{garch.data.persistence}</div>
                <div className="stat-label">Persistence (α+β)</div>
              </div>
              <div className="stat-box">
                <div className="stat-value neutral">{garch.data.aic}</div>
                <div className="stat-label">AIC</div>
              </div>
              <div className="stat-box">
                <div className="stat-value neutral">{garch.data.n_obs}</div>
                <div className="stat-label">Observations</div>
              </div>
              {dist.data?.descriptive_stats && (
                <>
                  <div className="stat-box">
                    <div className={`stat-value ${dist.data.descriptive_stats.kurtosis > 3 ? "negative" : "positive"}`}>
                      {dist.data.descriptive_stats.kurtosis}
                    </div>
                    <div className="stat-label">Excess Kurtosis</div>
                  </div>
                  <div className="stat-box">
                    <div className="stat-value neutral">{dist.data.descriptive_stats.skewness}</div>
                    <div className="stat-label">Skewness</div>
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
                    <div className="card-title">Conditional Volatility — {ticker}</div>
                    <div className="card-subtitle">GARCH(1,1) with Student-t distribution</div>
                  </div>
                </div>
                <div className="chart-container tall">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={garch.data.conditional_volatility}>
                      <defs>
                        <linearGradient id="volGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis dataKey="date" stroke="#64748b" tick={{ fontSize: 10 }} tickFormatter={v => v.slice(0, 7)} interval={Math.floor(garch.data.conditional_volatility.length / 8)} />
                      <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                      <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8 }} labelStyle={{ color: "#f1f5f9" }} />
                      <Area type="monotone" dataKey="volatility" stroke="#6366f1" fill="url(#volGradient)" strokeWidth={1.5} name="Cond. Volatility (σ)" />
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
                    <div className="card-title">Daily Log Returns (%) — {ticker}</div>
                    <div className="card-subtitle">Observe volatility clustering: calm and turbulent periods</div>
                  </div>
                </div>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={garch.data.returns} barSize={1.5}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis dataKey="date" stroke="#64748b" tick={{ fontSize: 10 }} tickFormatter={v => v.slice(0, 7)} interval={Math.floor(garch.data.returns.length / 8)} />
                      <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                      <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8 }} labelStyle={{ color: "#f1f5f9" }} />
                      <ReferenceLine y={0} stroke="#64748b" strokeDasharray="3 3" />
                      <Bar dataKey="return" name="Return (%)" radius={0}>
                        {garch.data.returns.map((entry, idx) => (
                          <Cell key={idx} fill={entry.return >= 0 ? "rgba(16,185,129,0.7)" : "rgba(239,68,68,0.7)"} />
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
                    <div className="card-title">Return Distribution</div>
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
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis dataKey="bin_mid" stroke="#64748b" tick={{ fontSize: 10 }} label={{ value: "Return (%)", position: "bottom", offset: -2, fill: "#64748b", fontSize: 11 }} />
                      <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                      <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8 }} labelStyle={{ color: "#f1f5f9" }} formatter={(v) => [v, "Count"]} />
                      <Bar dataKey="count" fill="#6366f1" radius={[2, 2, 0, 0]} opacity={0.8} />
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
                    <div className="card-title">Q-Q Plot (Normal)</div>
                    <div className="card-subtitle">Deviation from the diagonal indicates fat tails</div>
                  </div>
                </div>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ left: 10, right: 20, top: 10, bottom: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis dataKey="theoretical" name="Theoretical" stroke="#64748b" tick={{ fontSize: 10 }} label={{ value: "Theoretical Quantiles", position: "bottom", offset: 0, fill: "#64748b", fontSize: 11 }} />
                      <YAxis dataKey="actual" name="Actual" stroke="#64748b" tick={{ fontSize: 10 }} label={{ value: "Sample Quantiles", angle: -90, position: "insideLeft", fill: "#64748b", fontSize: 11 }} />
                      <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8 }} labelStyle={{ color: "#f1f5f9" }} />
                      <Scatter data={dist.data.qq_plot} fill="#06b6d4" fillOpacity={0.6} r={2} />
                      {/* Reference diagonal */}
                      <ReferenceLine segment={[
                        { x: dist.data.qq_plot[0]?.theoretical, y: dist.data.qq_plot[0]?.theoretical },
                        { x: dist.data.qq_plot[dist.data.qq_plot.length - 1]?.theoretical, y: dist.data.qq_plot[dist.data.qq_plot.length - 1]?.theoretical }
                      ]} stroke="#ef4444" strokeDasharray="5 5" />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>
            )}

            {/* Squared Return ACF (Volatility Clustering Evidence) */}
            {clustering.data?.squared_return_acf && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">ACF of Squared Returns</div>
                    <div className="card-subtitle">High autocorrelation = volatility clustering (ARCH effects)</div>
                  </div>
                </div>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={clustering.data.squared_return_acf}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis dataKey="lag" stroke="#64748b" tick={{ fontSize: 11 }} label={{ value: "Lag", position: "bottom", offset: -2, fill: "#64748b", fontSize: 11 }} />
                      <YAxis stroke="#64748b" tick={{ fontSize: 11 }} domain={[0, "auto"]} />
                      <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8 }} labelStyle={{ color: "#f1f5f9" }} />
                      <Bar dataKey="autocorrelation" fill="#a855f7" radius={[3, 3, 0, 0]} name="Autocorrelation" />
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
                    <div className="card-title">GARCH(1,1) Model Comparison</div>
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
                      {compare.data.model_comparison.map((m, i) => {
                        const isBest = i === 0 || m.aic === Math.min(...compare.data.model_comparison.map(x => x.aic));
                        return (
                          <tr key={m.distribution}>
                            <td style={{ color: "#f1f5f9", fontFamily: "var(--font-main)", fontWeight: isBest ? 600 : 400 }}>
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
                    <div className="card-title">GARCH(1,1) Parameters</div>
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
                          <td style={{ color: "#f1f5f9", fontFamily: "var(--font-main)" }}>{name}</td>
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
                    <div className="card-title">Ljung-Box Test on Squared Returns</div>
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
