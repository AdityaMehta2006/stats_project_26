/**
 * theme.js
 * --------
 * Central chart palette for the "quant terminal" theme. Recharts reads colors
 * from props (not CSS variables), so we keep a single source of truth here to
 * stay consistent with the CSS design tokens in index.css.
 */

export const CHART = {
  teal: "#2DD4BF",     // primary data
  cyan: "#38BDF8",     // secondary data
  gold: "#FBBF24",     // highlights
  violet: "#A78BFA",   // 4th series
  pink: "#F472B6",     // 5th series
  blue: "#60A5FA",     // 6th series
  up: "#34D399",       // gains / positive
  down: "#F87171",     // losses / negative
  axis: "#5E6B7E",     // axis ticks & labels
  grid: "rgba(148, 163, 184, 0.10)",
  tooltipBg: "#0F1623",
  tooltipBorder: "rgba(148, 163, 184, 0.18)",
};

// Ordered palette for multi-series charts / categorical fills.
export const SERIES = [
  CHART.teal,
  CHART.cyan,
  CHART.gold,
  CHART.violet,
  CHART.pink,
  CHART.blue,
  CHART.up,
];

// Shared Recharts tooltip styling.
export const tooltipStyle = {
  background: CHART.tooltipBg,
  border: `1px solid ${CHART.tooltipBorder}`,
  borderRadius: 10,
  boxShadow: "0 8px 30px rgba(0,0,0,0.45)",
  fontFamily: "var(--font-main)",
  fontSize: "0.8rem",
};
export const tooltipLabelStyle = { color: "#E6EDF6", fontWeight: 600, marginBottom: 2 };
export const tooltipItemStyle = { color: "#97A6BA", fontFamily: "var(--font-mono)", fontSize: "0.78rem" };
