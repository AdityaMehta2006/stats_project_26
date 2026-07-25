/**
 * PairTrading.jsx
 * ----------------
 * Pillar 3: Pair Trading in Forex dashboard panel.
 * Supports custom forex pair selection. Shows cointegration tests,
 * spread/z-score chart, signals, and correlation matrix.
 */

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, ReferenceArea, Scatter, Legend, ComposedChart
} from "recharts";
import useApiData from "../hooks/useApiData";
import { useTicker } from "../ticker";
import { getPairsCointegration, getPairsBest, getPairsCorrelation } from "../api";
import { ErrorState, StatsSkeleton, ChartSkeleton } from "./common/StatusStates";
import ForexPairSelector from "./common/ForexPairSelector";
import Icon from "./common/Icon";
import { InfoTip, LabelWithTip } from "./common/Tooltip";
import TimeRangeFilter from "./common/TimeRangeFilter";
import { filterByRange, axisInterval } from "../timeRange";
import { CHART, SERIES, tooltipStyle, tooltipLabelStyle, tooltipItemStyle } from "../theme";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.1 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

export default function PairTrading() {
  // Shared with the engine: the basket picked here is what the pairs detector scans.
  const { pairs: selectedPairs, setPairs: setSelectedPairs } = useTicker();

  const coint = useApiData(() => getPairsCointegration(selectedPairs), [selectedPairs.join(",")], "pairs-coint");
  const best = useApiData(() => getPairsBest(selectedPairs), [selectedPairs.join(",")], "pairs-best");
  const corr = useApiData(() => getPairsCorrelation(selectedPairs), [selectedPairs.join(",")], "pairs-corr");

  const loading = coint.loading || best.loading || corr.loading;
  const error = coint.error || best.error || corr.error;

  const hasData = Boolean(coint.data || best.data || corr.data);
  const firstLoad = loading && !hasData;
  const refetching = loading && hasData;

  const [range, setRange] = useState("1Y");
  const spreadData = useMemo(() => filterByRange(best.data?.spread_series || [], range), [best.data, range]);
  const priceData = useMemo(() => filterByRange(best.data?.price_series || [], range), [best.data, range]);
  /**
   * Fold the generated entries/exits onto the z-score series so the chart shows
   * where the rule actually fired, not just where the bands are. Buys and sells
   * ride separate keys so each can carry its own direction colour.
   */
  const zData = useMemo(() => {
    const rows = spreadData.filter((d) => d.z_score !== undefined);
    const byDate = new Map((best.data?.signals || []).map((s) => [s.date, s.signal]));
    return rows.map((d) => {
      const sig = byDate.get(d.date);
      return {
        ...d,
        entry_buy: sig === "buy" ? d.z_score : undefined,
        entry_sell: sig === "sell" ? d.z_score : undefined,
        exit: sig === "close_long" || sig === "close_short" ? d.z_score : undefined,
      };
    });
  }, [spreadData, best.data]);

  /** Mean and ±1σ/±2σ for the spread — what "mean reversion" is reverting to. */
  const spreadStats = useMemo(() => {
    const vals = spreadData.map((d) => d.spread).filter((v) => typeof v === "number");
    if (!vals.length) return null;
    const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
    const sd = Math.sqrt(vals.reduce((a, b) => a + (b - mean) ** 2, 0) / vals.length);
    return { mean, sd };
  }, [spreadData]);

  return (
    <motion.div variants={container} initial="hidden" animate="show"
      className={refetching ? "is-refetching" : undefined}>
      <motion.div className="section-header" variants={item}>
        <div className="section-ico pairs"><Icon name="exchange" size={24} /></div>
        <div>
          <h2>Forex Pair Trading</h2>
          <p>Cointegration analysis and mean-reversion signals for currency pairs</p>
        </div>
      </motion.div>

      <motion.div className="section-intro" variants={item}>
        <span className="intro-ico"><Icon name="info" size={18} /></span>
        <span>
          Two currency pairs can drift apart day to day yet stay tethered over the long run —
          a relationship called <strong>cointegration</strong>. We find the most tethered pair,
          build the <strong>spread</strong> between them, and standardise it into a
          <strong> z-score</strong>. When the z-score stretches far from zero we bet it snaps
          back (<strong>mean reversion</strong>): buy the spread below −2, sell above +2, exit near 0.
        </span>
      </motion.div>

      {/* Pair selector */}
      <motion.div variants={item} className="toolbar-card">
        <ForexPairSelector selectedPairs={selectedPairs} onPairsChange={setSelectedPairs} />
        <div className="trf-wrap"><span className="trf-label">Range</span>
          <TimeRangeFilter value={range} onChange={setRange} layoutId="pairs-range" />
        </div>
      </motion.div>

      {firstLoad && (
        <>
          <StatsSkeleton boxes={6} />
          <div className="charts-grid">
            <ChartSkeleton />
            <ChartSkeleton />
          </div>
        </>
      )}
      {error && !firstLoad && <ErrorState message={error} onRetry={() => { coint.reload(); best.reload(); corr.reload(); }} />}

      {!firstLoad && !error && (
        <>
          {best.data && coint.data && (
            <motion.div className="stats-grid" variants={item}>
              <div className="stat-box">
                <div className="stat-value text">{best.data.pair_a}/{best.data.pair_b}</div>
                <div className="stat-label">
                  <LabelWithTip tip="The pair with the strongest long-run link (lowest cointegration p-value) among your selection — the one we trade.">
                    Best Cointegrated Pair
                  </LabelWithTip>
                </div>
              </div>
              <div className="stat-box">
                <div className={`stat-value ${best.data.coint_pvalue < 0.05 ? "positive" : "negative"}`}>
                  {best.data.coint_pvalue}
                </div>
                <div className="stat-label">
                  <LabelWithTip tip="Engle-Granger p-value. Below 0.05 means the two prices are statistically cointegrated and the spread should mean-revert.">
                    Coint. P-Value
                  </LabelWithTip>
                </div>
              </div>
              <div className="stat-box">
                <div className="stat-value neutral">{best.data.hedge_ratio}</div>
                <div className="stat-label">
                  <LabelWithTip tip="How many units of pair B to short for each unit of pair A so the combined spread is stationary (β from the regression A = β·B + α).">
                    Hedge Ratio
                  </LabelWithTip>
                </div>
              </div>
              <div className="stat-box">
                <div className="stat-value neutral">{best.data.half_life_days || "∞"}</div>
                <div className="stat-label">
                  <LabelWithTip tip="Expected days for the spread to close half of a deviation. Shorter = faster mean reversion, so trades resolve quicker.">
                    Half-Life (days)
                  </LabelWithTip>
                </div>
              </div>
              <div className="stat-box">
                <div className="stat-value neutral">{best.data.total_signals}</div>
                <div className="stat-label">
                  <LabelWithTip tip="Total buy/sell/exit signals the z-score rule generated over the full history.">
                    Total Signals
                  </LabelWithTip>
                </div>
              </div>
              <div className="stat-box">
                <div className="stat-value neutral">{coint.data.cointegrated_pairs}/{coint.data.pairs_tested}</div>
                <div className="stat-label">
                  <LabelWithTip tip="How many of all tested pair combinations were cointegrated (p < 0.05) out of the total tested.">
                    Cointegrated / Tested
                  </LabelWithTip>
                </div>
              </div>
            </motion.div>
          )}

          <div className="charts-grid">
            {/* Z-Score Chart with Signals */}
            {best.data?.spread_series && (
              <motion.div className="card" variants={item} style={{ gridColumn: "1 / -1" }}>
                <div className="card-header">
                  <div>
                    <div className="card-title">
                      Z-Score & Trading Signals — {best.data.pair_a}/{best.data.pair_b}
                      <InfoTip text="The standardised spread. Each time the line crosses ±2 and returns to 0, the strategy opens and closes a mean-reversion trade." />
                    </div>
                    <div className="card-subtitle">Buy when z &lt; −2, sell when z &gt; +2, exit at z = 0</div>
                  </div>
                </div>
                <div className="chart-container tall">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={zData} margin={{ top: 8, right: 20, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
                      <XAxis dataKey="date" stroke={CHART.axis} tick={{ fontSize: 10 }} tickFormatter={v => v.slice(0, 7)} interval={axisInterval(zData.length)} minTickGap={24} tickMargin={8} />
                      <YAxis
                        stroke={CHART.axis}
                        tick={{ fontSize: 11 }}
                        tickMargin={6}
                        width={48}
                        domain={[(min) => Math.min(-3, Math.floor(min)), (max) => Math.max(3, Math.ceil(max))]}
                        tickFormatter={(v) => `${v > 0 ? "+" : ""}${v}σ`}
                      />
                      <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} />

                      {/* Shaded bands beyond ±2 read as "tradeable territory" far
                          faster than two dashed lines do. */}
                      <ReferenceArea y1={2} y2={100} fill="var(--bear-wash)" fillOpacity={1} />
                      <ReferenceArea y1={-100} y2={-2} fill="var(--bull-wash)" fillOpacity={1} />
                      <ReferenceLine y={2} stroke={CHART.down} strokeDasharray="4 4" label={{ value: "sell +2σ", fill: CHART.down, fontSize: 10, position: "insideTopRight" }} />
                      <ReferenceLine y={-2} stroke={CHART.up} strokeDasharray="4 4" label={{ value: "buy −2σ", fill: CHART.up, fontSize: 10, position: "insideBottomRight" }} />
                      <ReferenceLine y={0} stroke={CHART.axis} />

                      <Line type="monotone" dataKey="z_score" stroke={CHART.ink} dot={false} strokeWidth={1.5} name="Z-score" isAnimationActive={false} />
                      {/* Where the rule actually fired. */}
                      <Scatter dataKey="entry_buy" name="Buy signal" fill={CHART.up} shape="circle" />
                      <Scatter dataKey="entry_sell" name="Sell signal" fill={CHART.down} shape="circle" />
                      <Scatter dataKey="exit" name="Exit" fill={CHART.axis} shape="cross" />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>
            )}

            {/* Price Series for Best Pair */}
            {best.data?.price_series && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">
                      Price Series
                      <InfoTip text="The two raw exchange rates on separate axes. Cointegrated pairs tend to wander together rather than drift apart permanently." />
                    </div>
                    <div className="card-subtitle">{best.data.pair_a} vs {best.data.pair_b}</div>
                  </div>
                </div>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={priceData}>
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
                      <XAxis dataKey="date" stroke={CHART.axis} tick={{ fontSize: 10 }} tickFormatter={v => v.slice(0, 7)} interval={axisInterval(priceData.length, 6)}  minTickGap={24} tickMargin={8} />
                      <YAxis yAxisId="left" stroke={SERIES[0]} tick={{ fontSize: 11 }} tickMargin={6} width={60} domain={["auto", "auto"]} />
                      <YAxis yAxisId="right" orientation="right" stroke={SERIES[5]} tick={{ fontSize: 11 }} tickMargin={6} width={60} domain={["auto", "auto"]} />
                      <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} />
                      <Legend verticalAlign="top" height={30} iconType="plainline" />
                      <Line yAxisId="left" type="monotone" dataKey={best.data.pair_a} stroke={SERIES[0]} dot={false} strokeWidth={1.6} isAnimationActive={false} />
                      <Line yAxisId="right" type="monotone" dataKey={best.data.pair_b} stroke={SERIES[5]} dot={false} strokeWidth={1.6} isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>
            )}

            {/* Spread */}
            {best.data?.spread_series && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">
                      Spread
                      <InfoTip text="Pair A minus the hedge-ratio-scaled pair B. A stationary, mean-reverting spread is what makes the pair tradeable." />
                    </div>
                    <div className="card-subtitle">{best.data.pair_a} − {best.data.hedge_ratio}×{best.data.pair_b}</div>
                  </div>
                </div>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={spreadData} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
                      <XAxis dataKey="date" stroke={CHART.axis} tick={{ fontSize: 10 }} tickFormatter={v => v.slice(0, 7)} interval={axisInterval(spreadData.length, 6)} minTickGap={24} tickMargin={8} />
                      <YAxis stroke={CHART.axis} tick={{ fontSize: 11 }} tickMargin={6} width={62} domain={["auto", "auto"]} tickFormatter={(v) => v.toFixed(3)} />
                      <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} />
                      {/* Mean and ±1σ/±2σ: without them "mean reverting" is a
                          claim about a line with nothing to revert to. */}
                      {spreadStats && (
                        <>
                          <ReferenceArea
                            y1={spreadStats.mean - spreadStats.sd}
                            y2={spreadStats.mean + spreadStats.sd}
                            fill="var(--ink)"
                            fillOpacity={0.06}
                          />
                          <ReferenceLine y={spreadStats.mean} stroke={CHART.axis} label={{ value: "mean", fill: CHART.axis, fontSize: 10, position: "insideTopLeft" }} />
                          <ReferenceLine y={spreadStats.mean + 2 * spreadStats.sd} stroke={CHART.grid} strokeDasharray="4 4" />
                          <ReferenceLine y={spreadStats.mean - 2 * spreadStats.sd} stroke={CHART.grid} strokeDasharray="4 4" />
                        </>
                      )}
                      <Line type="monotone" dataKey="spread" stroke={CHART.ink} dot={false} strokeWidth={1.5} name="Spread" isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>
            )}

            {/* Cointegration Results Table */}
            {coint.data?.cointegration_results && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">
                      Cointegration Test Results
                      <InfoTip text="Engle-Granger test for every pair combination. p < 0.05 (green) means a stable long-run relationship suitable for spread trading." />
                    </div>
                    <div className="card-subtitle">All pair combinations · p &lt; 0.05 = cointegrated</div>
                  </div>
                </div>
                <div style={{ overflowX: "auto", maxHeight: 360, overflowY: "auto" }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Pair</th>
                        <th>Test Statistic</th>
                        <th>P-Value</th>
                        <th>Result</th>
                      </tr>
                    </thead>
                    <tbody>
                      {coint.data.cointegration_results.map((r, i) => (
                        <tr key={i}>
                          <td style={{ color: "var(--text-primary)", fontFamily: "var(--font-main)", fontWeight: 500 }}>{r.pair_label}</td>
                          <td>{r.coint_stat}</td>
                          <td className={r.cointegrated ? "significant" : "not-significant"}>{r.p_value}</td>
                          <td>
                            <span className={`badge ${r.cointegrated ? "success" : "danger"}`}>
                              {r.cointegrated ? "Cointegrated" : "Not Coint."}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}

            {/* Correlation Matrix Heatmap */}
            {corr.data?.correlation_matrix && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">
                      Forex Correlation Matrix
                      <InfoTip text="Day-to-day price correlation between pairs. Note: high correlation is NOT the same as cointegration — correlation is short-term co-movement, cointegration is a long-run anchor." />
                    </div>
                    <div className="card-subtitle">Pairwise price correlations</div>
                  </div>
                </div>
                <ForexCorrelationHeatmap data={corr.data.correlation_matrix} pairs={corr.data.pairs} />
                <div className="legend-row">
                  <span className="legend-item"><span className="legend-swatch" style={{ background: "rgba(45,212,191,0.7)" }} /> Positive</span>
                  <span className="legend-item"><span className="legend-swatch" style={{ background: "var(--hairline)" }} /> Neutral</span>
                  <span className="legend-item"><span className="legend-swatch" style={{ background: "rgba(248,113,113,0.7)" }} /> Negative</span>
                </div>
              </motion.div>
            )}

            {/* Signals Table */}
            {best.data?.signals && best.data.signals.length > 0 && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">
                      Trading Signals
                      <InfoTip text="Every entry and exit the z-score rule fired. BUY/SELL open a position; CLOSE LONG/SHORT take profit as the spread reverts to its mean." />
                    </div>
                    <div className="card-subtitle">{best.data.total_signals} signals for {best.data.pair_a}/{best.data.pair_b}</div>
                  </div>
                </div>
                <div className="legend-row" style={{ marginBottom: 12 }}>
                  <span className="legend-item"><span className="badge success">BUY</span></span>
                  <span className="legend-item"><span className="badge danger">SELL</span></span>
                  <span className="legend-item"><span className="badge info">CLOSE LONG</span></span>
                  <span className="legend-item"><span className="badge warning">CLOSE SHORT</span></span>
                </div>
                <div style={{ overflowX: "auto", maxHeight: 320, overflowY: "auto" }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Z-Score</th>
                        <th>Signal</th>
                      </tr>
                    </thead>
                    <tbody>
                      {best.data.signals.map((s, i) => {
                        const signalColors = {
                          buy: "success",
                          sell: "danger",
                          close_long: "info",
                          close_short: "warning",
                        };
                        return (
                          <tr key={i}>
                            <td>{s.date}</td>
                            <td>{s.z_score}</td>
                            <td>
                              <span className={`badge ${signalColors[s.signal] || "info"}`}>
                                {s.signal.replace("_", " ").toUpperCase()}
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
          </div>
        </>
      )}
    </motion.div>
  );
}

/* ---- Sub-components ---- */

function ForexCorrelationHeatmap({ data, pairs }) {
  function getColor(val) {
    if (val >= 0.8) return `oklch(from var(--bull) l c h / 0.62)`;
    if (val >= 0.5) return `oklch(from var(--bull) l c h / 0.36)`;
    if (val >= 0.2) return `oklch(from var(--bull) l c h / 0.16)`;
    if (val >= -0.2) return "rgba(148, 163, 184, 0.12)";
    if (val >= -0.5) return `oklch(from var(--bear) l c h / 0.2)`;
    if (val >= -0.8) return `oklch(from var(--bear) l c h / 0.42)`;
    return `oklch(from var(--bear) l c h / 0.7)`;
  }

  return (
    <div style={{ padding: "0.5rem 0" }}>
      <div style={{ display: "grid", gridTemplateColumns: `80px repeat(${pairs.length}, 1fr)`, gap: 3, marginBottom: 3 }}>
        <div></div>
        {pairs.map(p => (
          <div key={p} className="heatmap-label">{p}</div>
        ))}
      </div>
      {pairs.map(rowPair => (
        <div key={rowPair} style={{ display: "grid", gridTemplateColumns: `80px repeat(${pairs.length}, 1fr)`, gap: 3, marginBottom: 3 }}>
          <div className="heatmap-label" style={{ textAlign: "right", paddingRight: 6, fontSize: "0.7rem" }}>{rowPair}</div>
          {pairs.map(colPair => {
            const d = data.find(dd => dd.pair_a === rowPair && dd.pair_b === colPair);
            const val = d ? d.correlation : 0;
            return (
              <div
                key={colPair}
                className="heatmap-cell"
                style={{
                  background: getColor(val),
                  color: Math.abs(val) > 0.5 ? "#06231f" : "var(--text-secondary)",
                  minHeight: 36,
                }}
                title={`${rowPair}/${colPair}: ${val}`}
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
