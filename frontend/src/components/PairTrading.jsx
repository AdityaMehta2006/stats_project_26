/**
 * PairTrading.jsx
 * ----------------
 * Pillar 3: Pair Trading in Forex dashboard panel.
 * Supports custom forex pair selection. Shows cointegration tests,
 * spread/z-score chart, signals, and correlation matrix.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend, ComposedChart,
  Area, Scatter
} from "recharts";
import useApiData from "../hooks/useApiData";
import { getPairsCointegration, getPairsBest, getPairsCorrelation } from "../api";
import { LoadingState, ErrorState } from "./common/StatusStates";
import ForexPairSelector from "./common/ForexPairSelector";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.1 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

export default function PairTrading() {
  const [selectedPairs, setSelectedPairs] = useState(["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "EURGBP"]);

  const coint = useApiData(() => getPairsCointegration(selectedPairs), [selectedPairs.join(",")]);
  const best = useApiData(() => getPairsBest(selectedPairs), [selectedPairs.join(",")]);
  const corr = useApiData(() => getPairsCorrelation(selectedPairs), [selectedPairs.join(",")]);

  const loading = coint.loading || best.loading || corr.loading;
  const error = coint.error || best.error || corr.error;

  return (
    <motion.div variants={container} initial="hidden" animate="show">
      <motion.div className="section-header" variants={item}>
        <h2>💱 Forex Pair Trading</h2>
        <p>Cointegration analysis and mean-reversion signals for currency pairs</p>
      </motion.div>

      {/* Pair selector */}
      <motion.div variants={item} style={{ marginBottom: "1.5rem" }}>
        <div className="card" style={{ padding: "1rem 1.5rem" }}>
          <ForexPairSelector selectedPairs={selectedPairs} onPairsChange={setSelectedPairs} />
        </div>
      </motion.div>

      {loading && <LoadingState message="Testing cointegration across pairs…" subtext="Engle-Granger tests and spread construction" />}
      {error && !loading && <ErrorState message={error} onRetry={() => { coint.reload(); best.reload(); corr.reload(); }} />}

      {!loading && !error && (
        <>
          {/* Summary Stats */}
          {best.data && coint.data && (
            <motion.div className="stats-grid" variants={item}>
              <div className="stat-box">
                <div className="stat-value highlight">
                  {best.data.pair_a}/{best.data.pair_b}
                </div>
                <div className="stat-label">Best Cointegrated Pair</div>
              </div>
              <div className="stat-box">
                <div className={`stat-value ${best.data.coint_pvalue < 0.05 ? "positive" : "negative"}`}>
                  {best.data.coint_pvalue}
                </div>
                <div className="stat-label">Coint. P-Value</div>
              </div>
              <div className="stat-box">
                <div className="stat-value neutral">{best.data.hedge_ratio}</div>
                <div className="stat-label">Hedge Ratio</div>
              </div>
              <div className="stat-box">
                <div className="stat-value neutral">{best.data.half_life_days || "∞"}</div>
                <div className="stat-label">Half-Life (days)</div>
              </div>
              <div className="stat-box">
                <div className="stat-value neutral">{best.data.total_signals}</div>
                <div className="stat-label">Total Signals</div>
              </div>
              <div className="stat-box">
                <div className="stat-value neutral">{coint.data.cointegrated_pairs}/{coint.data.pairs_tested}</div>
                <div className="stat-label">Cointegrated / Tested</div>
              </div>
            </motion.div>
          )}

          <div className="charts-grid">
            {/* Z-Score Chart with Signals */}
            {best.data?.spread_series && (
              <motion.div className="card" variants={item} style={{ gridColumn: "1 / -1" }}>
                <div className="card-header">
                  <div>
                    <div className="card-title">Z-Score & Trading Signals — {best.data.pair_a}/{best.data.pair_b}</div>
                    <div className="card-subtitle">Buy when z &lt; -2 (green), Sell when z &gt; 2 (red), Exit at z = 0</div>
                  </div>
                </div>
                <div className="chart-container tall">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={best.data.spread_series.filter(d => d.z_score !== undefined)}>
                      <defs>
                        <linearGradient id="zGradPos" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2} />
                          <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="zGradNeg" x1="0" y1="1" x2="0" y2="0">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.2} />
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis dataKey="date" stroke="#64748b" tick={{ fontSize: 10 }} tickFormatter={v => v.slice(0, 7)} interval={Math.floor(best.data.spread_series.length / 8)} />
                      <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                      <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8 }} labelStyle={{ color: "#f1f5f9" }} />
                      <ReferenceLine y={2} stroke="#ef4444" strokeDasharray="5 5" label={{ value: "Sell Zone", fill: "#ef4444", fontSize: 10, position: "right" }} />
                      <ReferenceLine y={-2} stroke="#10b981" strokeDasharray="5 5" label={{ value: "Buy Zone", fill: "#10b981", fontSize: 10, position: "right" }} />
                      <ReferenceLine y={0} stroke="#64748b" strokeDasharray="3 3" />
                      <Line type="monotone" dataKey="z_score" stroke="#6366f1" dot={false} strokeWidth={1.5} name="Z-Score" />
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
                    <div className="card-title">Price Series</div>
                    <div className="card-subtitle">{best.data.pair_a} vs {best.data.pair_b}</div>
                  </div>
                </div>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={best.data.price_series}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis dataKey="date" stroke="#64748b" tick={{ fontSize: 10 }} tickFormatter={v => v.slice(0, 7)} interval={Math.floor(best.data.price_series.length / 6)} />
                      <YAxis yAxisId="left" stroke="#6366f1" tick={{ fontSize: 11 }} />
                      <YAxis yAxisId="right" orientation="right" stroke="#06b6d4" tick={{ fontSize: 11 }} />
                      <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8 }} labelStyle={{ color: "#f1f5f9" }} />
                      <Legend />
                      <Line yAxisId="left" type="monotone" dataKey={best.data.pair_a} stroke="#6366f1" dot={false} strokeWidth={1.5} />
                      <Line yAxisId="right" type="monotone" dataKey={best.data.pair_b} stroke="#06b6d4" dot={false} strokeWidth={1.5} />
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
                    <div className="card-title">Spread</div>
                    <div className="card-subtitle">{best.data.pair_a} − {best.data.hedge_ratio}×{best.data.pair_b}</div>
                  </div>
                </div>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={best.data.spread_series}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis dataKey="date" stroke="#64748b" tick={{ fontSize: 10 }} tickFormatter={v => v.slice(0, 7)} interval={Math.floor(best.data.spread_series.length / 6)} />
                      <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                      <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8 }} labelStyle={{ color: "#f1f5f9" }} />
                      <Line type="monotone" dataKey="spread" stroke="#a855f7" dot={false} strokeWidth={1.5} name="Spread" />
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
                    <div className="card-title">Cointegration Test Results</div>
                    <div className="card-subtitle">Engle-Granger test for all pair combinations (p &lt; 0.05 = cointegrated)</div>
                  </div>
                </div>
                <div style={{ overflowX: "auto" }}>
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
                          <td style={{ color: "#f1f5f9", fontFamily: "var(--font-main)", fontWeight: 500 }}>{r.pair_label}</td>
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
                    <div className="card-title">Forex Correlation Matrix</div>
                    <div className="card-subtitle">Pairwise price correlations</div>
                  </div>
                </div>
                <ForexCorrelationHeatmap data={corr.data.correlation_matrix} pairs={corr.data.pairs} />
              </motion.div>
            )}

            {/* Signals Table */}
            {best.data?.signals && best.data.signals.length > 0 && (
              <motion.div className="card" variants={item}>
                <div className="card-header">
                  <div>
                    <div className="card-title">Trading Signals</div>
                    <div className="card-subtitle">{best.data.total_signals} signals generated for {best.data.pair_a}/{best.data.pair_b}</div>
                  </div>
                </div>
                <div style={{ overflowX: "auto", maxHeight: 360, overflowY: "auto" }}>
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
    if (val >= 0.8) return "rgba(16, 185, 129, 0.7)";
    if (val >= 0.5) return "rgba(16, 185, 129, 0.4)";
    if (val >= 0.2) return "rgba(16, 185, 129, 0.2)";
    if (val >= -0.2) return "rgba(255, 255, 255, 0.05)";
    if (val >= -0.5) return "rgba(239, 68, 68, 0.2)";
    if (val >= -0.8) return "rgba(239, 68, 68, 0.4)";
    return "rgba(239, 68, 68, 0.7)";
  }

  return (
    <div style={{ padding: "0.5rem 0" }}>
      {/* Header */}
      <div style={{ display: "grid", gridTemplateColumns: `80px repeat(${pairs.length}, 1fr)`, gap: 3, marginBottom: 3 }}>
        <div></div>
        {pairs.map(p => (
          <div key={p} className="heatmap-label">{p}</div>
        ))}
      </div>
      {/* Rows */}
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
                  color: Math.abs(val) > 0.5 ? "#fff" : "#94a3b8",
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
