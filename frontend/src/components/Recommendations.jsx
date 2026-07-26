import { motion } from "framer-motion";
import useApiData from "../hooks/useApiData";
import useNarration from "../hooks/useNarration";
import { getEngineAsset } from "../api";
import { useTicker } from "../ticker";
import { ErrorState, VerdictSkeleton, SignalSkeleton } from "./common/StatusStates";
import TickerSearch from "./common/TickerSearch";
import TiltGauge, { RiskMeter } from "./common/TiltGauge";
import Icon from "./common/Icon";
import { InfoTip, LabelWithTip } from "./common/Tooltip";
import { CHART } from "../theme";
import {
  stanceGloss, stanceTone, riskWord,
  DETECTOR_TIPS, SOURCE_TAB, SOURCE_LABEL, prettyType,
} from "../verdict";

const TIPS = {
  gauge:
    "Where the evidence lands on a bear-to-bull axis, and how firmly. The marker is the balance of signals, weighted by how extreme each one is and how far its own statistics justify trusting it. The band is the uncertainty: wide means thin evidence, tight means the detectors agree.",
  risk:
    "How turbulent conditions are, from the volatility and tail-move detectors. Deliberately separate from direction — a volatility spike says the ride is rough, not which way it goes.",
  dissent:
    "These detectors point against the verdict. They are not discarded — disagreement is what widens the band above, so the read stays honest about how mixed the evidence is.",
};

/**
 * One signal as a row, not a card. A single column means one left alignment
 * axis and one width for every signal, which is what stops the dissenting
 * signals rendering at a different size from the agreeing ones.
 */
function SignalRow({ s, onDrill }) {
  const tab = SOURCE_TAB[s.source];
  const weight = s.severity * s.reliability;

  return (
    <motion.article
      className="signal-row"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
    >
      <header className="signal-row-head">
        <span className="signal-type">
          {prettyType(s.type)}
          <InfoTip text={DETECTOR_TIPS[s.type] || "A detector reading."} />
        </span>

        {/* Weight as bar length — the only encoding of it on the row. Sits in
            the header so it reads as a measurement, not as a divider rule. */}
        <span
          className="signal-weight"
          title={`severity ${s.severity.toFixed(2)} × reliability ${s.reliability.toFixed(2)}`}
        >
          <span className="signal-weight-fill" style={{ width: `${Math.max(5, weight * 100)}%` }} />
        </span>

        <span className="signal-spacer" />
        {tab ? (
          <button
            className="source-link"
            onClick={() => onDrill(tab, s.asset, s.source)}
            title={`Open ${SOURCE_LABEL[s.source]} for ${s.asset}`}
          >
            {s.asset} <Icon name="arrowRight" size={11} />
          </button>
        ) : (
          <span className="source-label">{s.asset}</span>
        )}
      </header>

      <h3 className="signal-label">{s.label}</h3>
      <p className="signal-note">{s.note}</p>

      <footer className="signal-foot">
        <span className="signal-rec">{s.recommendation}</span>
        {s.evidence && Object.keys(s.evidence).length > 0 && (
          <span className="evidence-chips">
            {Object.entries(s.evidence).map(([k, v]) => (
              <span key={k} className="evidence-chip">
                {k.replace(/_/g, " ")} <b>{String(v)}</b>
              </span>
            ))}
          </span>
        )}
      </footer>
    </motion.article>
  );
}

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
    <motion.div className="decision-panel">
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


function AnalystPanel({ verdict, narr, llmDown }) {
  const disagrees = narr.stance && narr.stance !== verdict.stance && !narr.streaming;

  return (
    <section className="analyst">
      <header className="analyst-head">
        <h2 className="block-title">
          AI analyst
          <InfoTip text="A local language model reads the detections below and explains them. It never computes the numbers — the statistics do that — and every figure it writes is checked back against them." />
        </h2>
        <button className="btn" onClick={narr.start} disabled={narr.streaming || llmDown}>
          {narr.streaming ? "Writing…" : narr.text ? "Regenerate" : "Explain this"}
        </button>
      </header>

      {(narr.stance || narr.streaming) && (
        <div className="stance-pair">
          <div className="stance-col">
            <span className="micro-label">
              Statistics say
              <InfoTip text="The verdict computed from the detectors — arithmetic only, no model involved." />
            </span>
            <span className={`stance-value ${stanceTone(verdict.stance)}`}>{verdict.stance}</span>
          </div>
          <div className="stance-col">
            <span className="micro-label">
              The model reads it as
              <InfoTip text="The model's own label, written before its explanation. It sees the same numbers and may weigh them differently." />
            </span>
            <span className={`stance-value ${narr.stance ? stanceTone(narr.stance) : ""}`}>
              {narr.stance || "…"}
            </span>
          </div>
        </div>
      )}

      {disagrees && (
        <p className="note-line">
          The model reads this differently from the computed verdict. Its reasoning is
          below; the numbers above are unchanged.
        </p>
      )}

      {llmDown && (
        <p className="analyst-text muted">
          Local model unavailable. Every signal on this page is unaffected — the
          statistics run without it.
        </p>
      )}
      {narr.error && <p className="analyst-text bear-text">{narr.error}</p>}
      {narr.skipped && <p className="analyst-text muted">Nothing to explain — {narr.skipped}.</p>}

      {narr.text && (
        <p className="analyst-text">
          {narr.text}
          {narr.streaming && <span className="stream-caret" />}
        </p>
      )}

      {!narr.text && !narr.streaming && !llmDown && !narr.error && !narr.skipped && (
        <p className="analyst-text muted">
          Read the signals in plain English, grounded in the evidence below.
        </p>
      )}

      {narr.unverified && (
        <p className={`grounding ${narr.unverified.length ? "flagged" : "clean"}`}>
          <Icon name={narr.unverified.length ? "alert" : "check"} size={13} />
          {narr.unverified.length ? (
            <span>
              {narr.unverified.length} figure{narr.unverified.length > 1 ? "s" : ""} not
              found in the evidence: <b className="mono-dim">{narr.unverified.join(", ")}</b>
            </span>
          ) : (
            <span>Every figure traced back to the evidence below.</span>
          )}
          <InfoTip text="Each number in the note is matched against the detected evidence. It is advisory — ordinary counts like '3 signals' get flagged too — and exists to catch a model inventing a price or a statistic." />
        </p>
      )}
    </section>
  );
}

export default function Recommendations({ onNavigate, llmAvailable, status }) {
  const { ticker, setTicker, pairs } = useTicker();
  const scan = useApiData((signal) => getEngineAsset(ticker, pairs, signal), [ticker, pairs], "engine-asset");
  const narr = useNarration(ticker, pairs);

  const data = scan.data;
  // Skeleton only when there is nothing on screen; otherwise dim in place.
  const firstLoad = scan.loading && !data;
  const refetching = scan.loading && !!data;

  const verdict = data?.verdict;
  const signals = data?.signals || [];
  const dissentIds = new Set(verdict?.dissent || []);
  const agreeing = signals.filter((s) => !dissentIds.has(s.id));
  const dissenting = signals.filter((s) => dissentIds.has(s.id));
  const llmDown = !llmAvailable || Boolean(narr.skipped?.includes("unavailable"));

  // The engine pre-warms a fixed universe; anything else pays for a cold GARCH
  // fit on first request. Say so rather than showing an unexplained wait.
  const cold = status?.universe && !status.universe.includes(ticker);

  const drill = (tab, asset, source) => {
    if (source !== "pairs") setTicker(asset);
    onNavigate?.(tab);
  };

  return (
    <div className="panel">
      <header className="panel-head">
        <h1>Opportunities</h1>
        <p>
          Eight detectors across volatility, macro, forex mean-reversion, options
          premium and price. Each is weighted by how extreme it is and how far its
          own statistics justify trusting it, then netted twice: into a verdict for
          direction and confidence, and into a sized position with its full working
          shown.
        </p>
      </header>

      <div className="panel-toolbar">
        <TickerSearch value={ticker} onSelect={setTicker} label="Scan" />
      </div>

      {scan.error && !scan.loading && <ErrorState message={scan.error} onRetry={scan.reload} />}

      {firstLoad && (
        <>
          {cold && (
            <p className="note-line">
              First scan for {ticker} — fitting the volatility model over ~2,700
              observations. Assets in the pre-warmed universe return instantly.
            </p>
          )}
          <VerdictSkeleton />
          <SignalSkeleton rows={3} />
        </>
      )}

      {!firstLoad && !scan.error && data && (
        <div className={refetching ? "is-refetching" : undefined}>
          <section className="verdict-block">
            <div className="verdict-head">
              <div>
                <h2 className={`verdict-stance ${stanceTone(verdict.stance)}`}>
                  {verdict.stance}
                </h2>
                <p className="verdict-gloss">{stanceGloss(verdict.stance)}</p>
              </div>
              <p className="verdict-asof">
                {signals.length} signal{signals.length === 1 ? "" : "s"}
                <br />
                <span className="mono-dim">data to {data.asof}</span>
              </p>
            </div>

            <div className="verdict-instruments">
              <div className="instrument">
                <span className="micro-label">
                  Where the evidence points
                  <InfoTip text={TIPS.gauge} />
                </span>
                <TiltGauge
                  tilt={verdict.tilt}
                  conviction={verdict.conviction}
                  stance={verdict.stance}
                />
              </div>

              <div className="instrument instrument-risk">
                <span className="micro-label">
                  Risk
                  <InfoTip text={TIPS.risk} />
                </span>
                <RiskMeter risk={verdict.risk} />
                <span className="instrument-word">{riskWord(verdict.risk)}</span>
              </div>
            </div>
          </section>

          {data.decision && <DecisionPanel decision={data.decision} />}

          <AnalystPanel verdict={verdict} narr={narr} llmDown={llmDown} />

          {signals.length === 0 ? (
            <p className="empty-note">
              No notable anomalies for {ticker} right now.
              {Object.keys(data.diagnostics || {}).length > 0 && (
                <span className="diag-note">
                  {" "}
                  {Object.keys(data.diagnostics).length} detector
                  {Object.keys(data.diagnostics).length > 1 ? "s" : ""} could not run, so
                  this is not the same as "nothing found".
                </span>
              )}
            </p>
          ) : (
            <div className="signal-list">
              {agreeing.map((s) => (
                <SignalRow key={s.id} s={s} onDrill={drill} />
              ))}

              {dissenting.length > 0 && (
                <>
                  <h2 className="list-divider">
                    Pushing the other way
                    <InfoTip text={TIPS.dissent} />
                  </h2>
                  {dissenting.map((s) => (
                    <SignalRow key={s.id} s={s} onDrill={drill} />
                  ))}
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
