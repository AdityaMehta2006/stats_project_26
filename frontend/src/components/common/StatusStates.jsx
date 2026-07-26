/**
 * StatusStates.jsx
 * ----------------
 * Waiting is part of this interface, not an interruption of it: a cold GARCH
 * fit runs ~3s, a fresh cointegration sweep takes seconds, and the local model
 * narrates in ~6s on CPU. So the waiting states are designed rather than
 * papered over with a spinner in the middle of empty space.
 *
 * Rule: skeletons on FIRST load (nothing on screen yet), dim-in-place on
 * REFETCH (data already visible). Blanking a populated screen back to skeletons
 * every time the ticker changes is worse than the spinner ever was.
 */

import { motion } from "framer-motion";
import Icon from "./Icon";

/** One shimmering block. Every skeleton shape is built from this. */
export function Skeleton({ w = "100%", h = 14, radius = 4, className = "", style }) {
  return (
    <span
      className={`skel ${className}`}
      style={{ width: w, height: h, borderRadius: radius, ...style }}
      aria-hidden="true"
    />
  );
}

/**
 * Matches the verdict block's real geometry — stance line, gauge, readout — so
 * nothing reflows when the data lands. That absence of jump is most of what
 * reads as "smooth".
 */
export function VerdictSkeleton() {
  return (
    <div className="verdict-block" aria-busy="true">
      <Skeleton w="42%" h={38} />
      <Skeleton w="60%" h={15} style={{ marginTop: 12 }} />
      <div style={{ marginTop: 28 }}>
        <Skeleton w="100%" h={8} radius={999} />
        <div className="skel-row" style={{ marginTop: 12 }}>
          <Skeleton w={92} h={12} />
          <Skeleton w={116} h={12} />
        </div>
      </div>
    </div>
  );
}

export function SignalSkeleton({ rows = 3 }) {
  return (
    <div className="signal-list" aria-busy="true">
      {Array.from({ length: rows }, (_, i) => (
        <div className="signal-row" key={i}>
          <div className="skel-row">
            <Skeleton w={132} h={11} />
            <Skeleton w={68} h={11} />
          </div>
          <Skeleton w="56%" h={17} style={{ marginTop: 14 }} />
          <Skeleton w="88%" h={13} style={{ marginTop: 10 }} />
          <div className="skel-row" style={{ marginTop: 14 }}>
            <Skeleton w={104} h={20} radius={4} />
            <Skeleton w={88} h={20} radius={4} />
            <Skeleton w={120} h={20} radius={4} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function StatsSkeleton({ boxes = 4 }) {
  return (
    <div className="stats-grid" aria-busy="true">
      {Array.from({ length: boxes }, (_, i) => (
        <div className="stat-box" key={i}>
          <Skeleton w="58%" h={26} />
          <Skeleton w="80%" h={11} style={{ marginTop: 12 }} />
        </div>
      ))}
    </div>
  );
}

export function ChartSkeleton({ height = 360 }) {
  return (
    <div className="card" aria-busy="true">
      <Skeleton w="34%" h={16} />
      <Skeleton w="52%" h={12} style={{ marginTop: 8 }} />
      <Skeleton w="100%" h={height - 60} radius={4} style={{ marginTop: 20 }} />
    </div>
  );
}

/**
 * Kept for the few places where there is genuinely no layout to predict.
 * `detail` should say what the wait is actually for — the engine's status
 * endpoint knows whether an asset is cold, so "first scan for NVDA, fitting
 * the volatility model" beats "Loading…".
 */
export function LoadingState({ message = "Working…", subtext, detail }) {
  return (
    <motion.div
      className="loading-container"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      aria-busy="true"
    >
      <div className="loading-text">{message}</div>
      {(detail || subtext) && <div className="loading-subtext">{detail || subtext}</div>}
      <Skeleton w={200} h={3} radius={999} style={{ marginTop: 14 }} />
    </motion.div>
  );
}

export function ErrorState({ title = "Something went wrong", message, onRetry }) {
  return (
    <motion.div
      className="error-container"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      role="alert"
    >
      <div className="error-icon">
        <Icon name="alert" size={22} />
      </div>
      <div className="error-title">{title}</div>
      <div className="error-message">
        {message ||
          "Could not reach the analysis backend. Start it from the backend folder with: python main.py"}
      </div>
      {onRetry && (
        <button className="retry-button" onClick={onRetry}>
          <Icon name="refresh" size={14} /> Try again
        </button>
      )}
    </motion.div>
  );
}
