import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import useApiData from "../hooks/useApiData";
import { getRecommendations } from "../api";
import { LoadingState, ErrorState } from "./common/StatusStates";
import TickerSearch from "./common/TickerSearch";
import Icon from "./common/Icon";
import { InfoTip, LabelWithTip } from "./common/Tooltip";
import { CHART } from "../theme";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.07 } },
};
const item = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.38 } },
};

function sevClass(s) { return s >= 0.66 ? "sev-high" : s >= 0.4 ? "sev-mid" : "sev-low"; }
function sevColor(s) { return s >= 0.66 ? CHART.down : s >= 0.4 ? CHART.gold : CHART.cyan; }

const STANCE_META = {
  strong_bullish: { cls: "bullish", icon: "trendingUp", label: "Strong Bullish" },
  lean_bullish:   { cls: "bullish", icon: "trendingUp", label: "Lean Bullish" },
  neutral:        { cls: "neutral", icon: "exchange",   label: "Neutral" },
  no_position:    { cls: "neutral", icon: "close",      label: "No Position" },
  lean_bearish:   { cls: "bearish", icon: "activity",   label: "Lean Bearish" },
  strong_bearish: { cls: "bearish", icon: "activity",   label: "Strong Bearish" },
};

/**
 * The rule-engine verdict, shown with its full working.
 *
 * Everything here is deterministic: same signals in, same decision out. The
 * rationale list is the audit trail — it names which signal drove the stance,
 * which ones were discounted for redundancy, and exactly how the position size
 * was derived. That transparency is the point of doing this in rules rather
 * than handing the whole job to a model.
 */
function DecisionPanel({ decision: d }) {
  const meta = STANCE_META[d.stance] || STANCE_META.neutral;
  const t = d.breakdown?.totals || {};
  const maxEvidence = Math.max(t.bullish || 0, t.bearish || 0, t.risk_off || 0, t.neutral || 0, 0.01);

  const bars = [
    { key: "bullish", label: "Bullish", color: CHART.up },
    { key: "bearish", label: "Bearish", color: CHART.down },
    { key: "risk_off", label: "Risk-off", color: CHART.gold },
    { key: "neutral", label: "Informational", color: CHART.cyan },
  ];

  return (
    <motion.div className="decision-panel" variants={item}>
      <div className="decision-head">
        <div>
          <div className={`decision-stance ${meta.cls}`}>
            <Icon name={meta.icon} size={20} />
            {meta.label}
            {d.conflict_flagged && (
              <span className="badge warning" style={{ marginLeft: 6 }}>CONFLICT</span>
            )}
          </div>
          <div className="decision-action">{d.action}</div>
        </div>
        <div style={{ textAlign: "right", flexShrink: 0 }}>
          <div className="stat-value highlight" style={{ fontSize: "1.5rem" }}>
            {d.position_size_pct}%
          </div>
          <div className="stat-label" style={{ justifyContent: "flex-end" }}>
            <LabelWithTip tip="Suggested share of a notional risk budget, not of your portfolio. Derived as base size (by stance) × conviction × risk multiplier, capped at 25%. Educational output, not investment advice.">
              Position Size
            </LabelWithTip>
          </div>
        </div>
      </div>

      <div className="decision-metrics">
        <Metric value={`${Math.round(d.conviction * 100)}%`} label="Conviction"
          tip="Strength of the directional case: |net score| plus a bonus for agreement across independent signal families, minus a penalty for internal disagreement." />
        <Metric value={d.net_score > 0 ? `+${d.net_score}` : d.net_score} label="Net Score"
          tip="Direction agreement × evidence strength, in [−1, +1]. Split this way so that one lone weak signal cannot score as maximum conviction just because nothing opposes it." />
        <Metric value={d.conflict_ratio} label="Conflict"
          tip="Share of directional evidence pointing the opposite way. Above 0.35 the stance is demoted one step rather than averaged — the honest response to contradictory evidence is less conviction, not a confident middle." />
        <Metric value={d.independent_families} label="Families"
          tip="Number of independent evidence families agreeing on direction. Two unrelated lines of evidence are worth far more than two correlated ones." />
        <Metric value={`${d.risk_multiplier}×`} label="Risk Multiplier"
          tip="Size reduction from risk-off signals and high-volatility regimes. It scales the position without changing direction — those are genuinely separate questions." />
      </div>

      {/* Evidence breakdown */}
      <div style={{ marginBottom: "0.9rem" }}>
        <div className="stat-label" style={{ marginBottom: 8 }}>
          <LabelWithTip tip="Total weight per category after each signal is scored as reliability × severity and then discounted for overlap with stronger signals in the same family.">
            Evidence Weight
          </LabelWithTip>
        </div>
        {bars.map((b) => (
          <div className="evidence-bar-row" key={b.key}>
            <span style={{ color: "var(--text-secondary)" }}>{b.label}</span>
            <div className="evidence-bar-track">
              <motion.div
                className="evidence-bar-fill"
                initial={{ width: 0 }}
                animate={{ width: `${((t[b.key] || 0) / maxEvidence) * 100}%` }}
                transition={{ duration: 0.7, ease: "easeOut" }}
                style={{ background: b.color }}
              />
            </div>
            <span className="mono" style={{ textAlign: "right", color: "var(--text-muted)", fontSize: "0.74rem" }}>
              {(t[b.key] || 0).toFixed(2)}
            </span>
          </div>
        ))}
      </div>

      {/* Audit trail */}
      <div>
        <div className="stat-label" style={{ marginBottom: 8 }}>
          <LabelWithTip tip="Every step the engine took, in order. Fully reproducible — the same inputs always yield the same decision.">
            Reasoning
          </LabelWithTip>
        </div>
        <ul className="rationale-list">
          {(d.rationale || []).map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      </div>

      {d.disclaimer && (
        <div className="card-note" style={{ marginTop: "0.9rem" }}>{d.disclaimer}</div>
      )}
    </motion.div>
  );
}

function Metric({ value, label, tip }) {
  return (
    <div className="decision-metric">
      <div className="decision-metric-value">{value ?? "—"}</div>
      <div className="decision-metric-label">
        {tip ? <LabelWithTip tip={tip}>{label}</LabelWithTip> : label}
      </div>
    </div>
  );
}

export default function Recommendations() {
  const [ticker, setTicker] = useState("^GSPC");
  const [narrative, setNarrative] = useState(null);
  const [narrLoading, setNarrLoading] = useState(false);
  const [narrError, setNarrError] = useState(null);

  const rec = useApiData(() => getRecommendations(ticker, false), [ticker]);

  const runAI = useCallback(async () => {
    setNarrLoading(true);
    setNarrError(null);
    setNarrative(null);
    try {
      const data = await getRecommendations(ticker, true);
      setNarrative(data.llm_narrative || "The model returned no note.");
    } catch (e) {
      setNarrError(e.message || "AI note failed");
    } finally {
      setNarrLoading(false);
    }
  }, [ticker]);

  const onSelect = (t) => {
    setTicker(t);
    setNarrative(null);
    setNarrError(null);
  };

  const data = rec.data;
  const llmAvailable = data?.llm?.available;

  return (
    <motion.div variants={container} initial="hidden" animate="show">
      <motion.div className="section-header" variants={item}>
        <div className="section-ico macro">
          <Icon name="target" size={22} strokeWidth={1.7} />
        </div>
        <div>
          <h2>Opportunities &amp; Anomalies</h2>
          <p>Automated scan that ranks what's unusual or actionable right now</p>
        </div>
      </motion.div>

      <motion.div className="section-intro" variants={item}>
        <span className="intro-ico"><Icon name="info" size={17} /></span>
        <span>
          Three strictly separated layers. <strong>Stats detect</strong>: thirteen
          deterministic detectors run across every pillar — volatility regime, tail moves,
          trend, momentum, mean reversion, macro dislocation, breakout, volume, seasonality,
          correlation regime, options mispricing and forex cointegration.{" "}
          <strong>Rules decide</strong>: signals are weighted by reliability, discounted where
          they overlap, netted into a stance, and sized — with genuine disagreement flagged
          rather than averaged away. <strong>The AI only explains</strong>: it receives the
          numbers and the decision, and can never change either.
        </span>
      </motion.div>

      <motion.div variants={item} className="toolbar-card">
        <TickerSearch value={ticker} onSelect={onSelect} label="Scan Ticker" />
      </motion.div>

      {rec.loading && (
        <LoadingState
          message={`Scanning ${ticker}…`}
          subtext="Running anomaly & opportunity detectors"
        />
      )}
      {rec.error && !rec.loading && (
        <ErrorState message={rec.error} onRetry={rec.reload} />
      )}

      {!rec.loading && !rec.error && data && (
        <>
          {/* Overall verdict */}
          <motion.div className="card" variants={item}>
            <div className="card-header">
              <div>
                <div className="card-title">
                  {data.overall.headline}
                  <InfoTip text="The highest-severity signal found. Confidence scales with how many detectors fired and how strong the top signal is." />
                </div>
                <div className="card-subtitle">{data.rules_summary}</div>
              </div>
              <div style={{ textAlign: "right", flexShrink: 0 }}>
                <div className="stat-value highlight" style={{ fontSize: "1.35rem" }}>
                  {Math.round(data.overall.confidence * 100)}%
                </div>
                <div className="stat-label" style={{ justifyContent: "flex-end" }}>
                  Confidence
                </div>
              </div>
            </div>
            <div className="conf-meter">
              <motion.div
                className="conf-fill"
                initial={{ width: 0 }}
                animate={{ width: `${data.overall.confidence * 100}%` }}
                transition={{ duration: 0.9, ease: "easeOut" }}
              />
            </div>
          </motion.div>

          {/* Rule-based decision */}
          {data.decision && <DecisionPanel decision={data.decision} />}

          {/* AI note */}
          <motion.div className="ai-panel" variants={item}>
            <div className="ai-panel-head">
              <div className="card-title">
                <Icon name="sparkles" size={17} style={{ color: "var(--accent-primary)" }} />
                AI Analyst Note
                <InfoTip
                  text={`Generated locally by ${
                    data.llm?.model || "the configured model"
                  }. Grounded strictly in the detected numbers above.`}
                />
              </div>
              <button
                className="ai-btn"
                onClick={runAI}
                disabled={narrLoading || !llmAvailable}
              >
                {narrLoading ? (
                  <>
                    <span
                      className="loading-spinner"
                      style={{ width: 13, height: 13, borderWidth: 2 }}
                    />{" "}
                    Generating…
                  </>
                ) : (
                  <>
                    <Icon name="sparkles" size={13} />{" "}
                    {narrative ? "Regenerate" : "Generate note"}
                  </>
                )}
              </button>
            </div>

            {!llmAvailable && (
              <div className="ai-narrative" style={{ color: "var(--text-muted)" }}>
                Local model unavailable — set up the LLM runtime to enable AI
                notes (rules-based signals still work).
              </div>
            )}
            {narrError && (
              <div className="ai-narrative" style={{ color: "var(--accent-danger)" }}>
                {narrError}
              </div>
            )}
            {narrLoading && (
              <div className="ai-narrative" style={{ color: "var(--text-muted)" }}>
                Running the local model (CPU) — this takes ~15–30s…
              </div>
            )}
            {narrative && !narrLoading && (
              <div className="ai-narrative">{narrative}</div>
            )}
            {!narrative && !narrLoading && !narrError && llmAvailable && (
              <div className="ai-narrative" style={{ color: "var(--text-muted)" }}>
                Click "Generate note" for a plain-English read of the signals below.
              </div>
            )}
          </motion.div>

          {/* Detector coverage */}
          {data.detectors_run != null && (
            <motion.div variants={item} className="card-note"
              style={{ marginBottom: "1rem", textAlign: "center" }}>
              {data.detectors_fired} of {data.detectors_run} detectors fired.
              Detectors that stay silent are not failures — they are conditions that are
              simply not present right now.
              {data.diagnostics && Object.keys(data.diagnostics).length > 0 && (
                <> {Object.keys(data.diagnostics).length} could not run (missing data or no
                option chain).</>
              )}
            </motion.div>
          )}

          {/* Signal cards */}
          {data.signals.length === 0 ? (
            <motion.div
              className="card"
              variants={item}
              style={{ marginTop: "1rem", textAlign: "center", color: "var(--text-muted)", padding: "2.5rem" }}
            >
              No notable anomalies detected for {ticker} right now.
            </motion.div>
          ) : (
            <div className="signals-grid">
              {data.signals.map((s, i) => (
                <motion.div
                  key={i}
                  className={`signal-card ${sevClass(s.severity)}`}
                  variants={item}
                >
                  <div className="signal-top">
                    <span className="signal-type">{s.type.replace(/_/g, " ")}</span>
                    <span className="badge info">{s.asset}</span>
                  </div>
                  <div className="severity-meter">
                    <motion.div
                      className="severity-fill"
                      initial={{ width: 0 }}
                      animate={{ width: `${s.severity * 100}%` }}
                      transition={{ duration: 0.7, ease: "easeOut", delay: 0.08 + i * 0.04 }}
                      style={{ background: sevColor(s.severity) }}
                    />
                  </div>
                  <div className="signal-label">{s.label}</div>
                  <div className="signal-note">{s.note}</div>
                  <div className="signal-rec">
                    <Icon name="arrowRight" size={13} /> {s.recommendation}
                  </div>
                  {s.evidence && (
                    <div className="evidence-chips">
                      {Object.entries(s.evidence).map(([k, v]) => (
                        <span key={k} className="evidence-chip">
                          {k.replace(/_/g, " ")}: <b>{String(v)}</b>
                        </span>
                      ))}
                    </div>
                  )}
                </motion.div>
              ))}
            </div>
          )}
        </>
      )}
    </motion.div>
  );
}
