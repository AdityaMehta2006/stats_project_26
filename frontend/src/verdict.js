/**
 * verdict.js
 * ----------
 * Plain-English layer over the engine's numbers.
 *
 * House rule for this dashboard: every readout serves a beginner and a trader
 * from the same element — the sentence is the primary slot, the figure sits
 * beside it, and the mechanism lives in the InfoTip. Nothing a beginner needs
 * in order to read the screen is hidden behind a click.
 */

/** One sentence saying what the fused stance actually means. */
export function stanceGloss(stance) {
  switch (stance) {
    case "bullish":
      return "The signals agree and lean up.";
    case "cautiously bullish":
      return "More evidence points up than down, but it isn't decisive.";
    case "bearish":
      return "The signals agree and lean down.";
    case "cautiously bearish":
      return "More evidence points down than up, but it isn't decisive.";
    default:
      return "No clear direction — the evidence is thin or it cancels out.";
  }
}

export function stanceTone(stance = "") {
  if (stance.includes("bullish")) return "up";
  if (stance.includes("bearish")) return "down";
  return "flat";
}

/** Risk axis: volatility and tail readings, kept out of the direction call. */
export function riskWord(r) {
  if (r >= 0.66) return "high";
  if (r >= 0.35) return "elevated";
  if (r > 0) return "normal";
  return "quiet";
}

/** What each detector actually tests — the InfoTip tier on a signal card. */
export const DETECTOR_TIPS = {
  volatility_regime:
    "Compares today's GARCH volatility with its own history. High readings mean price swings are larger than usual — a risk reading, not a direction call.",
  tail_event:
    "Measures the latest move in standard deviations. Beyond about 3 it is a move the normal-distribution assumption says should almost never happen.",
  pairs_opportunity:
    "Two currency pairs that historically move together have drifted apart. The z-score says how far, in standard deviations of their usual gap.",
  trend:
    "Price relative to its own rolling average. A simple, widely used rule — not a statistical test, so it is weighted lower than the fitted models.",
  macro_dislocation:
    "The gap between the actual return and what the macro regression predicted. A large gap means the asset is moving against its usual drivers.",
  breakout:
    "Price versus its recent high/low range. Flags a new extreme, or a squeeze where the range has narrowed without resolving yet.",
  relative_performance:
    "How this asset is doing against the rest of the scanned universe today.",
  vol_mispricing:
    "Compares the volatility the option market is charging for with the volatility the asset has actually realised. It says premium is expensive or cheap — not which way price is going.",
};

/** Which tab owns each detector, for drill-down. Price rules have no tab. */
export const SOURCE_TAB = {
  garch: "garch",
  macro: "macro",
  pairs: "pairs",
  options: "options",
  price: null,
};

export const SOURCE_LABEL = {
  garch: "GARCH",
  macro: "Macro",
  pairs: "Pairs",
  options: "Options",
  price: "Price rule",
};

export const prettyType = (t) => t.replace(/_/g, " ");
