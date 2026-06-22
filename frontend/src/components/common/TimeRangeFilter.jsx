/**
 * TimeRangeFilter.jsx
 * -------------------
 * Animated segmented control for selecting a chart time range. The active
 * highlight slides between options via a shared-layout framer-motion element.
 */

import { motion } from "framer-motion";
import { DAILY_RANGES } from "../../timeRange";

export default function TimeRangeFilter({ value, onChange, ranges = DAILY_RANGES, layoutId = "trf" }) {
  return (
    <div className="time-filter" role="group" aria-label="Time range">
      {ranges.map((r) => (
        <button
          key={r}
          className={`time-pill ${value === r ? "active" : ""}`}
          onClick={() => onChange(r)}
        >
          {value === r && (
            <motion.span
              layoutId={layoutId}
              className="time-pill-bg"
              transition={{ type: "spring", stiffness: 420, damping: 34 }}
            />
          )}
          <span className="time-pill-label">{r}</span>
        </button>
      ))}
    </div>
  );
}
