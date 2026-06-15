/**
 * MacroRegression.jsx
 * --------------------
 * Pillar 1: Macro Factor & Lag Regression dashboard panel.
 * Supports any ticker via TickerSearch. Shows OLS results, Granger causality,
 * correlation heatmap, and macro time series.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell, Legend
} from "recharts";
import useApiData from "../hooks/useApiData";
import { getMacroOLS, getMacroGranger, getMacroHeatmap, getMacroTimeSeries } from "../api";
import { LoadingState, ErrorState } from "./common/StatusStates";
import TickerSearch from "./common/TickerSearch";
import Icon from "./common/Icon";
import { InfoTip, LabelWithTip } from "./common/Tooltip";
import { CHART, SERIES, tooltipStyle, tooltipLabelStyle, tooltipItemStyle } from "../theme";

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
        <div className="section-ico macro"><Icon name="trendingUp" size={24} /></div>
        <div>
          <h2>Macro Factor & Lag Regression</h2>
          <p>How macroeconomic variables explain equity returns — and with what time delay</p>
        </div>
      </motion.div>

      <motion.div className="section-intro" variants={item}>
        <span className="intro-ico"><Icon name="info" size={18} /></span>
        <span>
          We regress an asset's monthly return on eight macro factors (VIX, oil, gold, the
          dollar, the 10Y yield, Fed Funds, inflation and unemployment), each included at
          several monthly <strong>lags</strong>. The goal is to see which forces actually
          drive returns and whether they act <strong>now</strong> or <strong>months later</strong> —
          a violation of the "markets are efficient and forward-looking" assumption.
        </span>
      </motion.div>

      {/* Ticker selector */}
      <motion.div variants={item} className="toolbar-card">
        <TickerSearch value={ticker} onSelect={setTicker} label="Analyze Ticker" />
      </motion.div>

      {loading && <LoadingState message={`Running regressions for ${ticker}…`} subtext="OLS, Granger causality & correlation analysis" />}
      {error && !loading && <ErrorState message={error} onRetry={() => { ols.reload(); granger.reload(); heatmap.reload(); ts.reload(); }} />}

      {!loading && !error && (
        <>
          {ols.data && (
            <motion.div className="stats-grid" variants={item}>
              <div className="stat-box">
                <div className="stat-value highlight">{ols.data.r_squared}</div>
                <div className="stat-label">
                  <LabelWithTip tip="Share of the asset's return variation explained by the macro factors. 0 = no explanatory power, 1 = perfectly explained.">
                    R-Squared
                  </LabelWithTip>
                </div>
              </div>
              <div className="stat-box">
                <div className="stat-value neutral">{ols.data.adj_r_squared}</div>
                <div className="stat-label">
                  <LabelWithTip tip="R-Squared penalised for the number of factors used. A fairer score that does not reward simply adding more variables.">
                    Adj. R-Squared
                  </LabelWithTip>
                </div>
              </div>
              <div className="stat-box">
                <div className="stat-value neutral">
                  {ols.data.coefficients ? ols.data.coefficients.filter(c => c.significant).length : 0}
                </div>
                <div className="stat-label">
                  <LabelWithTip tip="Number of factor/lag terms whose p-value is below 0.05 — i.e. statistically unlikely to be zero by chance.">
                    Significant Factors
                  </LabelWithTip>
                </div>
              </div>
              <div className="stat-box">
                <div className="stat-value neutral">
                  {ols.data.lag_comparison ? ols.data.lag_comparison.length : 0}
                </div>
                <div className="stat-label">
                  <LabelWithTip tip="How many lag depths were compared (0 months up to the maximum), to find how far back macro effects reach.">
                    Lag Depths Tested
                  </LabelWithTip>
                </div>
              </div>
            </motion.div>
          )}

          <div className="charts-grid">
            {/* Lag Model Comparison */}
            {ols.data?.lag_comparison && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">
                      Model Fit by Lag Depth
                      <InfoTip text="Each bar adds one more month of lagged factors. If the bars keep rising, macro effects reach further into the past." />
                    </div>
                    <div className="card-subtitle">R² and Adjusted R² across lag configurations</div>
                  </div>
                </div>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={ols.data.lag_comparison}>
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
                      <XAxis dataKey="max_lag" stroke={CHART.axis} tick={{ fontSize: 12 }} label={{ value: "Max Lag (months)", position: "bottom", offset: -2, fill: CHART.axis, fontSize: 12 }} />
                      <YAxis stroke={CHART.axis} tick={{ fontSize: 12 }} />
                      <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={{ fill: "rgba(148,163,184,0.06)" }} />
                      <Legend />
                      <Bar dataKey="r_squared" name="R²" fill={CHART.teal} radius={[4, 4, 0, 0]} />
                      <Bar dataKey="adj_r_squared" name="Adj. R²" fill={CHART.cyan} radius={[4, 4, 0, 0]} />
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
                    <div className="card-title">
                      Lagged Correlation Heatmap
                      <InfoTip text="Correlation between each macro factor (shifted back 0–3 months) and the asset's return. Teal = move together, red = move opposite." />
                    </div>
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
                    <div className="card-title">
                      Granger Causality Tests
                      <InfoTip text="Tests whether a factor's past values help predict future returns beyond what past returns alone predict. Significant = it leads returns." />
                    </div>
                    <div className="card-subtitle">Does the macro factor help predict {ticker} returns? (p &lt; 0.05 = significant)</div>
                  </div>
                </div>
                <div style={{ overflowX: "auto", maxHeight: 400, overflowY: "auto" }}>
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
                          <td style={{ color: "var(--text-primary)", fontFamily: "var(--font-main)" }}>{r.factor}</td>
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
                    <div className="card-title">
                      OLS Regression Coefficients
                      <InfoTip text="The estimated effect of each factor on returns. Teal bars are statistically significant (p < 0.05); grey bars are not distinguishable from zero." />
                    </div>
                    <div className="card-subtitle">Full model with lags for {ticker}</div>
                  </div>
                </div>
                <div className="chart-container tall">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={ols.data.coefficients.filter(c => c.variable !== "const")}
                      layout="vertical"
                      margin={{ left: 120, right: 30 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
                      <XAxis type="number" stroke={CHART.axis} tick={{ fontSize: 11 }} />
                      <YAxis type="category" dataKey="variable" stroke={CHART.axis} tick={{ fontSize: 10 }} width={110} />
                      <Tooltip
                        contentStyle={tooltipStyle}
                        labelStyle={tooltipLabelStyle}
                        itemStyle={tooltipItemStyle}
                        cursor={{ fill: "rgba(148,163,184,0.06)" }}
                        formatter={(val, name, props) => [`${val} (p=${props.payload.p_value})`, "Coefficient"]}
                      />
                      <Bar dataKey="coefficient" radius={[0, 4, 4, 0]}>
                        {ols.data.coefficients
                          .filter(c => c.variable !== "const")
                          .map((entry, idx) => (
                            <Cell key={idx} fill={entry.significant ? CHART.teal : "#3A4658"} />
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
                    <div className="card-title">
                      Macro Factor Time Series — {ticker}
                      <InfoTip text="The raw monthly history of each factor. Toggle the chips to overlay series and eyeball how they co-move." />
                    </div>
                    <div className="card-subtitle">Monthly data from 2015 – 2025 · click a chip to show/hide a series</div>
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
    if (ratio >= 0) {
      return `rgba(45, 212, 191, ${0.12 + Math.min(Math.abs(ratio), 1) * 0.6})`;
    }
    return `rgba(248, 113, 113, ${0.12 + Math.min(Math.abs(ratio), 1) * 0.6})`;
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
                style={{ background: getColor(val), color: Math.abs(val) > maxAbsCorr * 0.5 ? "#06231f" : "var(--text-secondary)" }}
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
              border: `1px solid ${selectedSeries.includes(col) ? SERIES[i % SERIES.length] : "var(--border-subtle)"}`,
              background: selectedSeries.includes(col) ? `${SERIES[i % SERIES.length]}22` : "transparent",
              color: selectedSeries.includes(col) ? SERIES[i % SERIES.length] : "var(--text-muted)",
              fontSize: "0.75rem",
              fontWeight: 500,
              cursor: "pointer",
              fontFamily: "var(--font-mono)",
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
            <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
            <XAxis dataKey="date" stroke={CHART.axis} tick={{ fontSize: 10 }} tickFormatter={v => v.slice(0, 7)} interval={Math.floor(chartData.length / 8)} />
            <YAxis stroke={CHART.axis} tick={{ fontSize: 11 }} />
            <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} />
            <Legend />
            {selectedSeries.map((col) => (
              <Line key={col} type="monotone" dataKey={col} stroke={SERIES[columns.indexOf(col) % SERIES.length]} dot={false} strokeWidth={1.6} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
