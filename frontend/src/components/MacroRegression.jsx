/**
 * MacroRegression.jsx
 * --------------------
 * Pillar 1: Macro Factor & Lag Regression dashboard panel.
 * Supports any ticker via TickerSearch. Shows OLS results, Granger causality,
 * correlation heatmap, and macro time series.
 */

import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell, Legend
} from "recharts";
import useApiData from "../hooks/useApiData";
import { getMacroOLS, getMacroGranger, getMacroHeatmap, getMacroTimeSeries } from "../api";
import { LoadingState, ErrorState } from "./common/StatusStates";
import TickerSearch from "./common/TickerSearch";

const COLORS = ["#6366f1", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#a855f7", "#ec4899"];

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.1 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

export default function MacroRegression() {
  const [ticker, setTicker] = useState("^GSPC");

  const ols = useApiData(() => getMacroOLS(ticker), [ticker]);
  const granger = useApiData(() => getMacroGranger(ticker), [ticker]);
  const heatmap = useApiData(() => getMacroHeatmap(ticker), [ticker]);
  const ts = useApiData(() => getMacroTimeSeries(ticker), [ticker]);

  const loading = ols.loading || granger.loading || heatmap.loading || ts.loading;
  const error = ols.error || granger.error || heatmap.error || ts.error;

  return (
    <motion.div variants={container} initial="hidden" animate="show">
      <motion.div className="section-header" variants={item}>
        <h2>📈 Macro Factor & Lag Regression</h2>
        <p>Analyzing how US macroeconomic variables explain equity returns with time lags</p>
      </motion.div>

      {/* Ticker selector */}
      <motion.div variants={item} style={{ marginBottom: "1.5rem" }}>
        <div className="card" style={{ padding: "1rem 1.5rem" }}>
          <TickerSearch value={ticker} onSelect={setTicker} label="Analyze Ticker" />
        </div>
      </motion.div>

      {loading && <LoadingState message={`Running regressions for ${ticker}…`} subtext="OLS, Granger causality & correlation analysis" />}
      {error && !loading && <ErrorState message={error} onRetry={() => { ols.reload(); granger.reload(); heatmap.reload(); ts.reload(); }} />}

      {!loading && !error && (
        <>
          {/* OLS Summary Stats */}
          {ols.data && (
            <motion.div className="stats-grid" variants={item}>
              <div className="stat-box">
                <div className="stat-value highlight">{ols.data.r_squared}</div>
                <div className="stat-label">R-Squared</div>
              </div>
              <div className="stat-box">
                <div className="stat-value neutral">{ols.data.adj_r_squared}</div>
                <div className="stat-label">Adj. R-Squared</div>
              </div>
              <div className="stat-box">
                <div className="stat-value neutral">
                  {ols.data.coefficients ? ols.data.coefficients.filter(c => c.significant).length : 0}
                </div>
                <div className="stat-label">Significant Factors</div>
              </div>
              <div className="stat-box">
                <div className="stat-value neutral">
                  {ols.data.lag_comparison ? ols.data.lag_comparison.length : 0}
                </div>
                <div className="stat-label">Lag Depths Tested</div>
              </div>
            </motion.div>
          )}

          <div className="charts-grid">
            {/* Lag Model Comparison */}
            {ols.data?.lag_comparison && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">Model Fit by Lag Depth</div>
                    <div className="card-subtitle">R² and Adjusted R² across lag configurations</div>
                  </div>
                </div>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={ols.data.lag_comparison}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis dataKey="max_lag" stroke="#64748b" tick={{ fontSize: 12 }} label={{ value: "Max Lag (months)", position: "bottom", offset: -2, fill: "#64748b", fontSize: 12 }} />
                      <YAxis stroke="#64748b" tick={{ fontSize: 12 }} />
                      <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8 }} labelStyle={{ color: "#f1f5f9" }} itemStyle={{ color: "#94a3b8" }} />
                      <Legend />
                      <Bar dataKey="r_squared" name="R²" fill="#6366f1" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="adj_r_squared" name="Adj. R²" fill="#06b6d4" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>
            )}

            {/* Correlation Heatmap */}
            {heatmap.data?.heatmap_data && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">Lagged Correlation Heatmap</div>
                    <div className="card-subtitle">Correlation of each factor (lagged 0–3 months) with {ticker} returns</div>
                  </div>
                </div>
                <HeatmapChart data={heatmap.data.heatmap_data} factors={heatmap.data.factors} maxLag={heatmap.data.max_lag} />
              </motion.div>
            )}

            {/* Granger Causality */}
            {granger.data?.granger_results && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">Granger Causality Tests</div>
                    <div className="card-subtitle">Does the macro factor help predict {ticker} returns? (p &lt; 0.05 = significant)</div>
                  </div>
                </div>
                <div style={{ overflowX: "auto" }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Factor</th>
                        <th>Lag</th>
                        <th>F-Statistic</th>
                        <th>P-Value</th>
                        <th>Result</th>
                      </tr>
                    </thead>
                    <tbody>
                      {granger.data.granger_results.map((r, i) => (
                        <tr key={i}>
                          <td style={{ color: "#f1f5f9", fontFamily: "var(--font-main)" }}>{r.factor}</td>
                          <td>{r.lag}</td>
                          <td>{r.f_stat}</td>
                          <td className={r.significant ? "significant" : "not-significant"}>{r.p_value}</td>
                          <td>
                            <span className={`badge ${r.significant ? "success" : "danger"}`}>
                              {r.significant ? "Significant" : "Not Sig."}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}

            {/* OLS Coefficients */}
            {ols.data?.coefficients && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">OLS Regression Coefficients</div>
                    <div className="card-subtitle">Full model with 3-month lags for {ticker}</div>
                  </div>
                </div>
                <div className="chart-container tall">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={ols.data.coefficients.filter(c => c.variable !== "const")}
                      layout="vertical"
                      margin={{ left: 120, right: 30 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis type="number" stroke="#64748b" tick={{ fontSize: 11 }} />
                      <YAxis type="category" dataKey="variable" stroke="#64748b" tick={{ fontSize: 10 }} width={110} />
                      <Tooltip
                        contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8 }}
                        labelStyle={{ color: "#f1f5f9" }}
                        formatter={(val, name, props) => [
                          `${val} (p=${props.payload.p_value})`,
                          "Coefficient"
                        ]}
                      />
                      <Bar dataKey="coefficient" radius={[0, 4, 4, 0]}>
                        {ols.data.coefficients
                          .filter(c => c.variable !== "const")
                          .map((entry, idx) => (
                            <Cell key={idx} fill={entry.significant ? "#10b981" : "#334155"} />
                          ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>
            )}

            {/* Macro Time Series */}
            {ts.data?.time_series && (
              <motion.div className="card" variants={item} style={{ gridColumn: "1 / -1" }}>
                <div className="card-header">
                  <div>
                    <div className="card-title">Macro Factor Time Series — {ticker}</div>
                    <div className="card-subtitle">Monthly data from 2015 – 2025</div>
                  </div>
                </div>
                <MacroTimeSeriesChart data={ts.data} />
              </motion.div>
            )}
          </div>
        </>
      )}
    </motion.div>
  );
}

/* ---- Sub-components ---- */

function HeatmapChart({ data, factors, maxLag }) {
  const lags = Array.from({ length: maxLag + 1 }, (_, i) => i);
  const maxAbsCorr = Math.max(...data.map(d => Math.abs(d.correlation)), 0.01);

  function getColor(val) {
    const ratio = val / maxAbsCorr;
    if (ratio > 0) {
      const intensity = Math.min(Math.round(ratio * 200), 200);
      return `rgba(16, 185, 129, ${0.15 + intensity / 280})`;
    } else {
      const intensity = Math.min(Math.round(Math.abs(ratio) * 200), 200);
      return `rgba(239, 68, 68, ${0.15 + intensity / 280})`;
    }
  }

  return (
    <div style={{ padding: "0.5rem 0" }}>
      <div style={{ display: "grid", gridTemplateColumns: `140px repeat(${lags.length}, 1fr)`, gap: 3, marginBottom: 3 }}>
        <div className="heatmap-label" style={{ textAlign: "right" }}></div>
        {lags.map(l => (
          <div key={l} className="heatmap-label">Lag {l}</div>
        ))}
      </div>
      {factors.map(factor => (
        <div key={factor} style={{ display: "grid", gridTemplateColumns: `140px repeat(${lags.length}, 1fr)`, gap: 3, marginBottom: 3 }}>
          <div className="heatmap-label" style={{ textAlign: "right", fontSize: "0.72rem", paddingRight: 8 }}>{factor}</div>
          {lags.map(lag => {
            const d = data.find(dd => dd.factor === factor && dd.lag === lag);
            const val = d ? d.correlation : 0;
            return (
              <div
                key={lag}
                className="heatmap-cell"
                style={{ background: getColor(val), color: Math.abs(val) > maxAbsCorr * 0.5 ? "#fff" : "#94a3b8" }}
                title={`${factor} lag ${lag}: ${val}`}
              >
                {val.toFixed(2)}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function MacroTimeSeriesChart({ data }) {
  const [selectedSeries, setSelectedSeries] = useState(["Equity_Return", "VIX"]);
  const columns = data.columns || [];

  const allDates = new Set();
  columns.forEach(col => {
    (data.time_series[col] || []).forEach(d => allDates.add(d.date));
  });
  const sortedDates = Array.from(allDates).sort();

  const chartData = sortedDates.map(date => {
    const row = { date };
    selectedSeries.forEach(col => {
      const point = (data.time_series[col] || []).find(d => d.date === date);
      if (point) row[col] = point.value;
    });
    return row;
  });

  return (
    <div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 16 }}>
        {columns.map((col, i) => (
          <button
            key={col}
            onClick={() => {
              setSelectedSeries(prev =>
                prev.includes(col) ? prev.filter(c => c !== col) : [...prev, col]
              );
            }}
            style={{
              padding: "4px 12px",
              borderRadius: 999,
              border: `1px solid ${selectedSeries.includes(col) ? COLORS[i % COLORS.length] : "rgba(255,255,255,0.1)"}`,
              background: selectedSeries.includes(col) ? `${COLORS[i % COLORS.length]}22` : "transparent",
              color: selectedSeries.includes(col) ? COLORS[i % COLORS.length] : "#64748b",
              fontSize: "0.75rem",
              fontWeight: 500,
              cursor: "pointer",
              fontFamily: "var(--font-main)",
              transition: "all 0.2s ease",
            }}
          >
            {col}
          </button>
        ))}
      </div>
      <div className="chart-container tall">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
            <XAxis dataKey="date" stroke="#64748b" tick={{ fontSize: 10 }} tickFormatter={v => v.slice(0, 7)} interval={Math.floor(chartData.length / 8)} />
            <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
            <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8 }} labelStyle={{ color: "#f1f5f9" }} itemStyle={{ fontFamily: "var(--font-mono)", fontSize: "0.78rem" }} />
            <Legend />
            {selectedSeries.map((col) => (
              <Line key={col} type="monotone" dataKey={col} stroke={COLORS[columns.indexOf(col) % COLORS.length]} dot={false} strokeWidth={1.5} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
