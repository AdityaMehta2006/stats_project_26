/**
 * MacroRegression.jsx
 * --------------------
 * Pillar 1: Macro Factor & Lag Regression dashboard panel.
 * Supports any ticker via TickerSearch. Shows OLS results, Granger causality,
 * correlation heatmap, and macro time series.
 */

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, BarChart, Bar, Cell, Legend
} from "recharts";
import useApiData from "../hooks/useApiData";
import { useTicker } from "../ticker";
import { getMacroOLS, getMacroGranger, getMacroHeatmap, getMacroTimeSeries } from "../api";
import { ErrorState, StatsSkeleton, ChartSkeleton } from "./common/StatusStates";
import TickerSearch from "./common/TickerSearch";
import Icon from "./common/Icon";
import { InfoTip, LabelWithTip } from "./common/Tooltip";
import TimeRangeFilter from "./common/TimeRangeFilter";
import { filterByRange, axisInterval, MONTHLY_RANGES } from "../timeRange";
import { CHART, SERIES, divergingFill, tooltipStyle, tooltipLabelStyle, tooltipItemStyle } from "../theme";
import { fmtPval, fmtBeta, fmtZ } from "../utils/format";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.1 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

export default function MacroRegression() {
  const { ticker, setTicker } = useTicker();

  const ols = useApiData(() => getMacroOLS(ticker), [ticker], "macro-ols");
  const granger = useApiData(() => getMacroGranger(ticker), [ticker], "macro-granger");
  const heatmap = useApiData(() => getMacroHeatmap(ticker), [ticker], "macro-heatmap");
  const ts = useApiData(() => getMacroTimeSeries(ticker), [ticker], "macro-ts");

  const loading = ols.loading || granger.loading || heatmap.loading || ts.loading;
  const error = ols.error || granger.error || heatmap.error || ts.error;

  const hasData = Boolean(ols.data || granger.data || heatmap.data || ts.data);
  const firstLoad = loading && !hasData;
  const refetching = loading && hasData;

  return (
    <motion.div variants={container} initial="hidden" animate="show"
      className={refetching ? "is-refetching" : undefined}>
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

      {firstLoad && (
        <>
          <StatsSkeleton boxes={4} />
          <div className="charts-grid">
            <ChartSkeleton />
            <ChartSkeleton />
          </div>
        </>
      )}
      {error && !firstLoad && <ErrorState message={error} onRetry={() => { ols.reload(); granger.reload(); heatmap.reload(); ts.reload(); }} />}

      {!firstLoad && !error && (
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
                      <XAxis dataKey="max_lag" stroke={CHART.axis} tick={{ fontSize: 12 }} label={{ value: "Max Lag (months)", position: "bottom", offset: -2, fill: CHART.axis, fontSize: 12 }}  minTickGap={24} tickMargin={8} height={52} />
                      <YAxis stroke={CHART.axis} tick={{ fontSize: 12 }}  tickMargin={6} />
                      <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={{ fill: "var(--surface-sunk)" }} />
                      {/* Legend to the top: at the default bottom placement it
                          sat on top of the "Max Lag (months)" axis label. */}
                      <Legend verticalAlign="top" height={30} />
                      <Bar dataKey="r_squared" name="R²" fill={SERIES[0]} radius={[3, 3, 0, 0]} />
                      <Bar dataKey="adj_r_squared" name="Adj. R²" fill={SERIES[4]} radius={[3, 3, 0, 0]} />
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
                            <span className={`badge ${r.significant ? "success" : "muted"}`}>
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

            {/* Driver Ranking */}
            {ols.data?.driver_ranking && ols.data.driver_ranking.length > 0 && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">
                      Top Return Drivers
                      <InfoTip text="Standardized betas ranked by absolute size — each coefficient shows the effect on equity returns per 1 standard deviation move in that factor. Larger = stronger driver. VIX is measured as its monthly log-change." />
                    </div>
                    <div className="card-subtitle">Factors ranked by |standardized beta| · {ticker}</div>
                  </div>
                </div>
                <div style={{ overflowX: "auto" }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Variable</th>
                        <th>Std. Beta</th>
                        <th>P-Value</th>
                        <th>Significant</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ols.data.driver_ranking.slice(0, 12).map((r, i) => (
                        <tr key={i}>
                          <td style={{ color: "var(--text-muted)" }}>{i + 1}</td>
                          <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.78rem" }}>{r.variable}</td>
                          <td style={{ color: r.coefficient > 0 ? CHART.up : CHART.down, fontFamily: "var(--font-mono)" }}>
                            {fmtBeta(r.coefficient)}
                          </td>
                          <td style={{ fontFamily: "var(--font-mono)" }}>{fmtPval(r.p_value)}</td>
                          <td>
                            <span className={`badge ${r.significant ? "success" : "muted"}`}>
                              {r.significant ? "Yes" : "No"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}

            {/* Factor Current State */}
            {ols.data?.factor_stats && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">
                      Factor Current State
                      <InfoTip text="Where each macro factor sits today relative to its own history. Z-score > ±2 indicates an extreme reading. VIX shows its latest monthly log-change." />
                    </div>
                    <div className="card-subtitle">Latest z-score and historical percentile for each factor</div>
                  </div>
                </div>
                <div style={{ overflowX: "auto" }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Factor</th>
                        <th>Latest Value</th>
                        <th>Z-Score</th>
                        <th>Percentile</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(ols.data.factor_stats).map(([factor, stats]) => {
                        const isExtreme = stats.percentile >= 0.88 || stats.percentile <= 0.12;
                        const pctLabel = `${(stats.percentile * 100).toFixed(0)}th`;
                        return (
                          <tr key={factor}>
                            <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.78rem" }}>{factor}</td>
                            <td style={{ fontFamily: "var(--font-mono)" }}>{stats.latest_raw.toFixed(4)}</td>
                            <td style={{ color: Math.abs(stats.latest_z) >= 2 ? CHART.down : "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
                              {fmtZ(stats.latest_z)}
                            </td>
                            <td style={{ fontFamily: "var(--font-mono)" }}>{pctLabel}</td>
                            <td>
                              <span className={`badge ${isExtreme ? "danger" : "info"}`}>
                                {isExtreme ? "Extreme" : "Normal"}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
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
                      <InfoTip text="The estimated effect of each factor on returns, per one standard-deviation move. Bars point right for a positive effect and left for a negative one; faded bars are not statistically significant (p ≥ 0.05), meaning they are not distinguishable from zero." />
                    </div>
                    <div className="card-subtitle">Full model with lags for {ticker}</div>
                  </div>
                </div>
                <div className="chart-container xtall">
                  <ResponsiveContainer width="100%" height="100%">
                    {/* margin.left AND YAxis width both reserved space for the
                        category labels, so the plot was pushed 230px right and
                        the bars no longer lined up with their labels. The axis
                        width alone does the job. */}
                    <BarChart
                      data={ols.data.coefficients.filter(c => c.variable !== "const")}
                      layout="vertical"
                      margin={{ top: 4, right: 24, bottom: 4, left: 8 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} horizontal={false} />
                      <XAxis type="number" stroke={CHART.axis} tick={{ fontSize: 11 }} minTickGap={24} tickMargin={8} />
                      <YAxis
                        type="category"
                        dataKey="variable"
                        stroke={CHART.axis}
                        tick={{ fontSize: 10 }}
                        width={132}
                        tickMargin={6}
                        interval={0}
                      />
                      {/* Coefficients are signed, so zero is the reference. */}
                      <ReferenceLine x={0} stroke={CHART.axis} />
                      <Tooltip
                        contentStyle={tooltipStyle}
                        labelStyle={tooltipLabelStyle}
                        itemStyle={tooltipItemStyle}
                        cursor={{ fill: "var(--surface-sunk)" }}
                        formatter={(val, name, props) => [
                          `${fmtBeta(val)} (p=${fmtPval(props.payload.p_value)})`,
                          "Std. Beta",
                        ]}
                      />
                      <Bar dataKey="coefficient" radius={[0, 4, 4, 0]}>
                        {/* Sign is direction, so it earns the hue. Significance
                            is not a direction, so it rides opacity instead. */}
                        {ols.data.coefficients
                          .filter(c => c.variable !== "const")
                          .map((entry, idx) => (
                            <Cell
                              key={idx}
                              fill={entry.coefficient >= 0 ? CHART.up : CHART.down}
                              fillOpacity={entry.significant ? 1 : 0.32}
                            />
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

  // Correlation has a sign, so it earns colour — the system's direction pair.
  const getColor = (val) => divergingFill(val, maxAbsCorr);

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
                style={{ background: getColor(val), color: Math.abs(val) > maxAbsCorr * 0.5 ? "var(--ink)" : "var(--ink-secondary)" }}
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
  const [range, setRange] = useState("All");
  const [scale, setScale] = useState("z");
  const columns = data.columns || [];

  const allDates = new Set();
  columns.forEach(col => {
    (data.time_series[col] || []).forEach(d => allDates.add(d.date));
  });
  const sortedDates = Array.from(allDates).sort();

  const rawData = filterByRange(sortedDates.map(date => {
    const row = { date };
    selectedSeries.forEach(col => {
      const point = (data.time_series[col] || []).find(d => d.date === date);
      if (point) row[col] = point.value;
    });
    return row;
  }), range);

  /**
   * These factors live on wildly different scales — VIX runs 15–40, Fed Funds
   * 0–5, and equity returns hover around ±0.05. On one raw axis VIX owns the
   * range and everything else is a flat line on zero, which is what made this
   * chart useless for comparison.
   *
   * Standardising to z-scores puts every factor in the same unit (standard
   * deviations from its own mean over the visible window), which is both
   * comparable and the same transform the regression itself uses. Raw values
   * stay one click away, and the tooltip always shows them.
   */
  const chartData = useMemo(() => {
    if (scale === "raw") return rawData;
    const stats = {};
    selectedSeries.forEach(col => {
      const vals = rawData.map(r => r[col]).filter(v => typeof v === "number");
      if (!vals.length) return;
      const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
      const sd = Math.sqrt(vals.reduce((a, b) => a + (b - mean) ** 2, 0) / vals.length) || 1;
      stats[col] = { mean, sd };
    });
    return rawData.map(row => {
      const out = { date: row.date };
      selectedSeries.forEach(col => {
        if (typeof row[col] === "number" && stats[col]) {
          out[col] = (row[col] - stats[col].mean) / stats[col].sd;
          out[`${col}__raw`] = row[col];
        }
      });
      return out;
    });
  }, [rawData, selectedSeries, scale]);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10, marginBottom: 16 }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {columns.map((col, i) => {
          const on = selectedSeries.includes(col);
          return (
            <button
              key={col}
              className={`series-pill ${on ? "on" : ""}`}
              onClick={() =>
                setSelectedSeries(prev =>
                  prev.includes(col) ? prev.filter(c => c !== col) : [...prev, col]
                )
              }
            >
              {/* The swatch carries the series' ramp step; the pill itself stays
                  ink. Previously this interpolated `${SERIES[i]}22` for the
                  background, which produced literal "var(--ramp-1)22" — not a
                  colour at all once the palette moved to tokens. */}
              <span
                className="series-swatch"
                style={{ background: on ? SERIES[(i * 3) % SERIES.length] : "var(--hairline)" }}
              />
              {col}
            </button>
          );
        })}
        </div>
        <div className="series-controls">
          <div className="trf-wrap">
            <span className="trf-label">Scale</span>
            <div className="time-filter">
              {[["z", "Standardised"], ["raw", "Raw"]].map(([v, label]) => (
                <button
                  key={v}
                  className={`time-pill ${scale === v ? "active" : ""}`}
                  onClick={() => setScale(v)}
                >
                  <span className="time-pill-label">{label}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="trf-wrap"><span className="trf-label">Range</span>
            <TimeRangeFilter value={range} onChange={setRange} ranges={MONTHLY_RANGES} layoutId="macro-range" />
          </div>
        </div>
      </div>

      {scale === "z" && (
        <p className="chart-note">
          Each factor is shown in standard deviations from its own mean over the
          visible window, so series on different scales can be compared. Switch to
          Raw for actual units.
        </p>
      )}
      <div className="chart-container tall">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
            <XAxis dataKey="date" stroke={CHART.axis} tick={{ fontSize: 10 }} tickFormatter={v => v.slice(0, 7)} interval={axisInterval(chartData.length)} minTickGap={24} tickMargin={8} />
            <YAxis
              stroke={CHART.axis}
              tick={{ fontSize: 11 }}
              tickMargin={6}
              width={52}
              tickFormatter={(v) => (scale === "z" ? `${v > 0 ? "+" : ""}${v.toFixed(1)}σ` : v)}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={tooltipLabelStyle}
              itemStyle={tooltipItemStyle}
              formatter={(val, name, props) => {
                const raw = props.payload?.[`${name}__raw`];
                return scale === "z" && raw !== undefined
                  ? [`${val >= 0 ? "+" : ""}${val.toFixed(2)}σ  (${raw})`, name]
                  : [val, name];
              }}
            />
            <Legend verticalAlign="top" height={30} iconType="plainline" />
            {scale === "z" && <ReferenceLine y={0} stroke={CHART.axis} strokeDasharray="2 4" />}
            {selectedSeries.map((col) => (
              <Line
                key={col}
                type="monotone"
                dataKey={col}
                stroke={SERIES[(columns.indexOf(col) * 3) % SERIES.length]}
                dot={false}
                strokeWidth={1.6}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
