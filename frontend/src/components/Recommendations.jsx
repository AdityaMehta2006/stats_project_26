/**
 * Recommendations.jsx
 * -------------------
 * Anomaly & Opportunity engine panel. Deterministic detectors rank signals
 * (rules mode, instant); an optional local-LLM note explains them in prose.
 */

import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import useApiData from "../hooks/useApiData";
import { getRecommendations } from "../api";
import { LoadingState, ErrorState } from "./common/StatusStates";
import TickerSearch from "./common/TickerSearch";
import Icon from "./common/Icon";
import { InfoTip } from "./common/Tooltip";
import { CHART } from "../theme";

const container = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const item = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

function sevClass(s) { return s >= 0.66 ? "sev-high" : s >= 0.4 ? "sev-mid" : "sev-low"; }
function sevColor(s) { return s >= 0.66 ? CHART.down : s >= 0.4 ? CHART.gold : CHART.cyan; }

export default function Recommendations() {
  const [ticker, setTicker] = useState("^GSPC");
  const [narrative, setNarrative] = useState(null);
  const [narrLoading, setNarrLoading] = useState(false);
  const [narrError, setNarrError] = useState(null);

  const rec = useApiData(() => getRecommendations(ticker, false), [ticker]);

  // AI note is fetched on demand (local model is slower)
  const runAI = useCallback(async () => {
    setNarrLoading(true); setNarrError(null); setNarrative(null);
    try {
      const data = await getRecommendations(ticker, true);
      setNarrative(data.llm_narrative || "The model returned no note.");
    } catch (e) {
      setNarrError(e.message || "AI note failed");
    } finally {
      setNarrLoading(false);
    }
  }, [ticker]);

  const onSelect = (t) => { setTicker(t); setNarrative(null); setNarrError(null); };

  const data = rec.data;
  const llmAvailable = data?.llm?.available;

  return (
    <motion.div variants={container} initial="hidden" animate="show">
      <motion.div className="section-header" variants={item}>
        <div className="section-ico macro"><Icon name="target" size={24} /></div>
        <div>
          <h2>Opportunities & Anomalies</h2>
          <p>Automated scan that ranks what's unusual or actionable right now</p>
        </div>
      </motion.div>

      <motion.div className="section-intro" variants={item}>
        <span className="intro-ico"><Icon name="info" size={18} /></span>
        <span>
          Deterministic detectors run across all three pillars — <strong>volatility regime</strong>,
          <strong> tail moves</strong>, <strong>trend</strong>, and <strong>forex mean-reversion</strong> —
          and rank each finding by severity. The numbers come purely from the stats; the optional
          <strong> AI note</strong> (a local model) only explains them in plain English and never
          invents figures.
        </span>
      </motion.div>

      <motion.div variants={item} className="toolbar-card">
        <TickerSearch value={ticker} onSelect={onSelect} label="Scan Ticker" />
      </motion.div>

      {rec.loading && <LoadingState message={`Scanning ${ticker}…`} subtext="Running anomaly & opportunity detectors" />}
      {rec.error && !rec.loading && <ErrorState message={rec.error} onRetry={rec.reload} />}

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
              <div style={{ textAlign: "right", minWidth: 120 }}>
                <div className="stat-value highlight" style={{ fontSize: "1.4rem" }}>
                  {Math.round(data.overall.confidence * 100)}%
                </div>
                <div className="stat-label" style={{ justifyContent: "flex-end" }}>Confidence</div>
              </div>
            </div>
            <div className="conf-meter">
              <motion.div
                className="conf-fill"
                initial={{ width: 0 }}
                animate={{ width: `${data.overall.confidence * 100}%` }}
                transition={{ duration: 0.8, ease: "easeOut" }}
              />
            </div>
          </motion.div>

          {/* AI note */}
          <motion.div className="ai-panel" variants={item}>
            <div className="ai-panel-head">
              <div className="card-title">
                <Icon name="sparkles" size={18} style={{ color: "var(--accent-primary)" }} />
                AI Analyst Note
                <InfoTip text={`Generated locally by ${data.llm?.model || "the configured model"}. Grounded strictly in the detected numbers above.`} />
              </div>
              <button className="ai-btn" onClick={runAI} disabled={narrLoading || !llmAvailable}>
                {narrLoading
                  ? <><span className="loading-spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Generating…</>
                  : <><Icon name="sparkles" size={14} /> {narrative ? "Regenerate" : "Generate note"}</>}
              </button>
            </div>
            {!llmAvailable && (
              <div className="ai-narrative" style={{ color: "var(--text-muted)" }}>
                Local model unavailable — set up the LLM runtime to enable AI notes (rules-based signals still work).
              </div>
            )}
            {narrError && <div className="ai-narrative" style={{ color: "var(--accent-danger)" }}>{narrError}</div>}
            {narrLoading && (
              <div className="ai-narrative" style={{ color: "var(--text-muted)" }}>
                Running the local model (CPU) — this takes ~15–30s…
              </div>
            )}
            {narrative && !narrLoading && <div className="ai-narrative">{narrative}</div>}
            {!narrative && !narrLoading && !narrError && llmAvailable && (
              <div className="ai-narrative" style={{ color: "var(--text-muted)" }}>
                Click “Generate note” for a plain-English read of the signals below.
              </div>
            )}
          </motion.div>

          {/* Signal cards */}
          {data.signals.length === 0 ? (
            <motion.div className="card" variants={item} style={{ marginTop: "1.25rem", textAlign: "center", color: "var(--text-muted)" }}>
              No notable anomalies detected for {ticker} right now.
            </motion.div>
          ) : (
            <div className="signals-grid">
              {data.signals.map((s, i) => (
                <motion.div key={i} className={`signal-card ${sevClass(s.severity)}`} variants={item}>
                  <div className="signal-top">
                    <span className="signal-type">{s.type.replace(/_/g, " ")}</span>
                    <span className="badge info">{s.asset}</span>
                  </div>
                  <div className="severity-meter">
                    <motion.div
                      className="severity-fill"
                      initial={{ width: 0 }}
                      animate={{ width: `${s.severity * 100}%` }}
                      transition={{ duration: 0.7, ease: "easeOut", delay: 0.1 + i * 0.05 }}
                      style={{ background: sevColor(s.severity) }}
                    />
                  </div>
                  <div className="signal-label">{s.label}</div>
                  <div className="signal-note">{s.note}</div>
                  <div className="signal-rec"><Icon name="arrowRight" size={14} /> {s.recommendation}</div>
                  {s.evidence && (
                    <div className="evidence-chips">
                      {Object.entries(s.evidence).map(([k, v]) => (
                        <span key={k} className="evidence-chip">{k.replace(/_/g, " ")}: <b>{String(v)}</b></span>
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
