/**
 * format.js — numeric display utilities for financial dashboards.
 * All functions return strings safe to render directly.
 */

/** Format a decimal as a percentage string: 0.0423 → "4.23%" */
export function fmtPct(v, decimals = 2) {
  if (v == null || isNaN(v)) return "—";
  return `${(v * 100).toFixed(decimals)}%`;
}

/** Format an absolute percentage (already ×100): 4.23 → "4.23%" */
export function fmtPctRaw(v, decimals = 1) {
  if (v == null || isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(decimals)}%`;
}

/** General number formatter with auto-precision */
export function fmtNum(v, decimals = 4) {
  if (v == null || isNaN(v)) return "—";
  return Number(v).toFixed(decimals);
}

/** Format a p-value: show "<0.001" below threshold, otherwise fixed */
export function fmtPval(v) {
  if (v == null || isNaN(v)) return "—";
  if (v < 0.001) return "<0.001";
  if (v < 0.01)  return v.toFixed(3);
  return v.toFixed(3);
}

/** Format a test statistic (t/F/z) with sign and 3 decimal places */
export function fmtStat(v) {
  if (v == null || isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${Number(v).toFixed(3)}`;
}

/** Format a standardized beta: "+0.142" */
export function fmtBeta(v) {
  if (v == null || isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${Number(v).toFixed(3)}`;
}

/** Format a z-score with sign: "+2.34σ" */
export function fmtZ(v) {
  if (v == null || isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${Number(v).toFixed(2)}σ`;
}
