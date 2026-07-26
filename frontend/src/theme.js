/**
 * theme.js
 * --------
 * Chart palette. Recharts takes colours as props, which land as SVG
 * presentation attributes — and those resolve `var()`, so pointing them at the
 * CSS tokens means charts follow light/dark automatically with no JS.
 *
 * The house rule applies here too: colour means direction. A categorical series
 * gets a step on the ink ramp, not a hue. Series are told apart by value and by
 * labelling them directly; a rainbow legend is a colour key for a chart that
 * refused to label itself.
 */

export const CHART = {
  // Direction — the only hues allowed anywhere in the system.
  up: "var(--bull)",
  down: "var(--bear)",

  // Structure.
  ink: "var(--ink)",
  axis: "var(--ink-muted)",
  grid: "var(--hairline)",
  primary: "var(--ink)",

  tooltipBg: "var(--surface)",
  tooltipBorder: "var(--hairline)",

  // Legacy hue names, folded onto the ramp so existing chart props keep
  // working without reintroducing teal/violet/pink. Prefer SERIES[i].
  teal: "var(--ramp-1)",
  cyan: "var(--ramp-3)",
  gold: "var(--ramp-4)",
  violet: "var(--ramp-5)",
  pink: "var(--ramp-6)",
  blue: "var(--ramp-2)",
};

/**
 * Categorical series: eight lightness steps. Adjacent steps sit far apart in
 * lightness on purpose, so the series survive greyscale printing and
 * colour-blind viewers — which the old teal/violet/pink set never did.
 */
export const SERIES = [
  "var(--ramp-1)", "var(--ramp-2)", "var(--ramp-3)", "var(--ramp-4)",
  "var(--ramp-5)", "var(--ramp-6)", "var(--ramp-7)", "var(--ramp-8)",
];

/**
 * Diverging fill for correlation / residual cells. This one IS direction, so
 * it keeps its hue — exactly what the rule permits.
 */
export function divergingFill(value, max = 1) {
  const t = Math.max(-1, Math.min(1, value / max));
  if (Math.abs(t) < 0.04) return "var(--surface-sunk)";
  const alpha = (0.12 + 0.68 * Math.abs(t)).toFixed(3);
  return t > 0
    ? `oklch(from var(--bull) l c h / ${alpha})`
    : `oklch(from var(--bear) l c h / ${alpha})`;
}

export const tooltipStyle = {
  background: "var(--surface)",
  border: "1px solid var(--hairline)",
  borderRadius: 8,
  boxShadow: "var(--shadow-pop)",
  fontFamily: "var(--font-main)",
  fontSize: "0.8125rem",
  color: "var(--ink)",
};
export const tooltipLabelStyle = { color: "var(--ink)", fontWeight: 600, marginBottom: 2 };
export const tooltipItemStyle = {
  color: "var(--ink-secondary)",
  fontFamily: "var(--font-mono)",
  fontSize: "0.75rem",
};
