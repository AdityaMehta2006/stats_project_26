"""
decision.py
-----------
The **rule-based decision layer**: turns a ranked list of detected signals into
one auditable, actionable decision.

Why this is a separate layer from `recommender.py`
-------------------------------------------------
`recommender.py` *detects*. Each detector answers a narrow question ("is
volatility unusual?", "is the spread stretched?") and emits a signal with a
severity. But a pile of signals is not a decision, and the gap between them is
where most naive systems fail:

  * Signals **disagree**. A confirmed uptrend and an elevated-volatility warning
    point in opposite directions. Averaging them produces mush; you need to
    recognise the conflict and say so.
  * Signals **overlap**. A 50-day breakout and a confirmed uptrend are largely
    the same information counted twice. Treating them as independent
    confirmations badly overstates confidence.
  * Signals differ in **reliability**. A cointegration test with p < 0.01 is a
    stronger basis for action than an RSI reading, and the weights should say so.
  * A decision needs a **size**, not just a direction. "Buy" without a position
    size is not a decision.

This module handles all four, deterministically. No LLM, no learned parameters,
no hidden state — the same inputs always produce the same output, and every
number is traceable to the rule that produced it. That auditability is the point:
it is what makes the system defensible, and what the LLM layer explicitly does
*not* provide (the LLM only narrates what this module decides).

The pipeline
------------
    signals
      -> classify each as bullish / bearish / risk-off / neutral   (direction map)
      -> weight by category reliability x signal severity          (evidence weight)
      -> discount overlapping families so correlated signals       (redundancy)
         do not double-count
      -> net the bullish and bearish evidence                      (net score)
      -> measure disagreement                                      (conflict ratio)
      -> map score + conflict + volatility regime to a stance      (stance)
      -> convert stance to a position size via inverse-volatility  (sizing)
         scaling and a Kelly-style cap

Every threshold below is a stated, arguable choice rather than a fitted one, and
each is annotated with its reasoning. That is deliberate: with a few hundred
observations and no out-of-sample test, fitting these numbers would overfit far
more convincingly than it would inform.
"""

import numpy as np
from typing import Dict, Any, List, Optional

# ---------------------------------------------------------------------------
# 1. SIGNAL TAXONOMY
# ---------------------------------------------------------------------------

# How each detector's `direction` field maps onto a market stance.
#   bullish  — argues for long exposure
#   bearish  — argues for short / reduced exposure
#   risk_off — argues for smaller size regardless of direction
#   neutral  — informational; affects confidence but not direction
DIRECTION_MAP: Dict[str, Dict[str, str]] = {
    "trend":                 {"uptrend": "bullish", "downtrend": "bearish"},
    "breakout":              {"up": "bullish", "down": "bearish", "neutral": "neutral"},
    "relative_performance":  {"outperforming": "bullish", "underperforming": "bearish"},
    "momentum":              {"positive": "bullish", "negative": "bearish"},
    "mean_reversion":        {"oversold": "bullish", "overbought": "bearish"},
    "volatility_regime":     {"elevated": "risk_off", "compressed": "neutral"},
    "tail_event":            {"down": "risk_off", "up": "risk_off"},
    "macro_dislocation":     {"above_model": "bearish", "below_model": "bullish"},
    "options_mispricing":    {"rich": "neutral", "cheap": "neutral"},
    "volume_anomaly":        {"accumulation": "bullish", "distribution": "bearish",
                              "spike": "neutral"},
    "seasonality":           {"favorable": "bullish", "unfavorable": "bearish"},
    "correlation_regime":    {"decoupling": "neutral", "converging": "neutral"},
    "pairs_opportunity":     {"long spread": "neutral", "short spread": "neutral",
                              "building": "neutral"},
}

# Reliability weight per detector family, in [0, 1]. These encode how much
# statistical backing each signal type has — not how loud it is.
#
# Rationale for the ordering:
#   1.00 pairs_opportunity     — backed by a formal hypothesis test (Engle-Granger
#                                p-value) plus an estimated half-life. The only
#                                detector with a real significance level attached.
#   0.95 volatility_regime     — GARCH is a fitted model with significant params
#                                and a percentile computed from its own history.
#   0.90 macro_dislocation     — OLS residual z from an 8-factor model; genuine
#                                statistical content, but monthly and low-N.
#   0.85 options_mispricing    — market-implied vs forecast vol; clean economics,
#                                but depends on chain liquidity.
#   0.80 tail_event            — an unambiguous measurement, though a single
#                                observation says little about what comes next.
#   0.75 trend / relative      — robust, widely documented (momentum is one of
#                                the most replicated anomalies), but crude.
#   0.65 breakout / volume     — technical, prone to false positives.
#   0.55 mean_reversion (RSI)  — popular but weak evidence in isolation.
#   0.40 seasonality           — real effects exist but are small and heavily
#                                data-mined in the literature. Deliberately low.
#   0.50 correlation_regime    — informative context, rarely actionable alone.
RELIABILITY: Dict[str, float] = {
    "pairs_opportunity": 1.00,
    "volatility_regime": 0.95,
    "macro_dislocation": 0.90,
    "options_mispricing": 0.85,
    "tail_event": 0.80,
    "trend": 0.75,
    "relative_performance": 0.75,
    "momentum": 0.75,
    "breakout": 0.65,
    "volume_anomaly": 0.65,
    "mean_reversion": 0.55,
    "correlation_regime": 0.50,
    "seasonality": 0.40,
}

# Detectors drawing on essentially the same underlying information. Within a
# family, only the strongest signal counts at full weight; the rest are
# discounted, because three views of one price trend is one piece of evidence,
# not three.
REDUNDANCY_FAMILIES: Dict[str, List[str]] = {
    "price_trend": ["trend", "breakout", "momentum", "relative_performance"],
    "volatility": ["volatility_regime", "tail_event", "options_mispricing"],
    "valuation": ["macro_dislocation", "mean_reversion"],
    "flow": ["volume_anomaly"],
    "calendar": ["seasonality"],
    "cross_asset": ["pairs_opportunity", "correlation_regime"],
}

# Weight applied to the 2nd, 3rd, ... signal within one family. Geometric decay:
# the second view of the same story is worth 45% of the first, the third 20%.
REDUNDANCY_DECAY = 0.45


def _family_of(signal_type: str) -> str:
    for family, members in REDUNDANCY_FAMILIES.items():
        if signal_type in members:
            return family
    return "other"


def classify_signal(sig: Dict[str, Any]) -> str:
    """Map one signal onto bullish / bearish / risk_off / neutral."""
    stype = sig.get("type", "")
    direction = str(sig.get("direction", "")).lower()
    return DIRECTION_MAP.get(stype, {}).get(direction, "neutral")


# ---------------------------------------------------------------------------
# 2. EVIDENCE WEIGHTING AND REDUNDANCY DISCOUNTING
# ---------------------------------------------------------------------------

def weigh_signals(signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convert raw signals into redundancy-discounted directional evidence.

    Each signal's base weight is `reliability x severity`: how trustworthy the
    detector is, times how strongly it fired. Signals in the same family are then
    sorted by weight and discounted geometrically, so correlated evidence cannot
    masquerade as independent confirmation.
    """
    enriched = []
    for sig in signals:
        stype = sig.get("type", "unknown")
        severity = float(sig.get("severity", 0.0))
        reliability = RELIABILITY.get(stype, 0.5)
        stance = classify_signal(sig)
        enriched.append({
            "type": stype,
            "asset": sig.get("asset"),
            "label": sig.get("label"),
            "direction": sig.get("direction"),
            "stance": stance,
            "severity": round(severity, 4),
            "reliability": reliability,
            "family": _family_of(stype),
            "base_weight": round(reliability * severity, 5),
        })

    # Discount within families.
    by_family: Dict[str, List[Dict[str, Any]]] = {}
    for e in enriched:
        by_family.setdefault(e["family"], []).append(e)

    for family, members in by_family.items():
        members.sort(key=lambda m: -m["base_weight"])
        for rank, m in enumerate(members):
            factor = REDUNDANCY_DECAY ** rank
            m["redundancy_rank"] = rank
            m["redundancy_factor"] = round(factor, 4)
            m["effective_weight"] = round(m["base_weight"] * factor, 5)

    totals = {"bullish": 0.0, "bearish": 0.0, "risk_off": 0.0, "neutral": 0.0}
    for e in enriched:
        totals[e["stance"]] += e["effective_weight"]

    return {
        "weighted_signals": sorted(enriched, key=lambda e: -e["effective_weight"]),
        "totals": {k: round(v, 5) for k, v in totals.items()},
        "families_present": sorted(by_family.keys()),
    }


# ---------------------------------------------------------------------------
# 3. NETTING, CONFLICT, AND STANCE
# ---------------------------------------------------------------------------

# Stance thresholds on the net directional score (bullish - bearish evidence,
# normalised). Chosen so that a single strong signal alone reaches "lean" but not
# "conviction" — conviction should require agreement across families.
STANCE_THRESHOLDS = {
    "strong_bullish": 0.45,
    "lean_bullish": 0.15,
    "lean_bearish": -0.15,
    "strong_bearish": -0.45,
}

# Above this share of opposing evidence, the signals are treated as genuinely
# contradictory and conviction is cut. 0.35 means: if more than about a third of
# the directional evidence points the other way, we do not pretend to know.
CONFLICT_THRESHOLD = 0.35

# Reference evidence level for the tanh saturation in `decide`. Total directional
# weight equal to this value maps to ~0.76 strength. Set to 1.2 so that roughly
# two high-reliability detectors firing hard are required for a strong stance,
# and a single moderate signal cannot reach one on its own.
EVIDENCE_SCALE = 1.2


def decide(signals: List[Dict[str, Any]], ticker: str = "",
           vol_percentile: Optional[float] = None) -> Dict[str, Any]:
    """
    Produce the final decision from a list of detected signals.

    Steps, each visible in the returned payload so the reasoning can be audited:

    1. **Weight and discount** — `weigh_signals` above.
    2. **Net score** = (bullish - bearish) / (bullish + bearish + risk_off).
       Dividing by total evidence keeps the score in [-1, 1] and means adding
       more *agreeing* signals raises confidence rather than the score itself.
    3. **Conflict ratio** = min(bullish, bearish) / (bullish + bearish). Zero when
       all directional signals agree, 0.5 when perfectly split.
    4. **Stance** from the thresholds, then demoted one step if conflict is high
       — the honest response to contradictory evidence is less conviction, not a
       confident average.
    5. **Risk overlay** — risk_off evidence and a high volatility percentile cut
       the position size without changing the direction. Direction and size are
       genuinely separate questions and conflating them is a common error.
    6. **Position size** by inverse-volatility scaling, capped.

    Returns a decision, a numeric breakdown, and a plain-English audit trail.
    """
    if not signals:
        # Same key set as the full path below — consumers (and the frontend)
        # should never have to special-case the empty result.
        return {
            "ticker": ticker,
            "stance": "no_position",
            "action": "stand aside",
            "conviction": 0.0,
            "position_size_pct": 0.0,
            "net_score": 0.0,
            "conflict_ratio": 0.0,
            "conflict_flagged": False,
            "stance_demoted_for_conflict": False,
            "risk_multiplier": 1.0,
            "independent_families": 0,
            "rationale": ["No detector fired, so there is no evidence to act on."],
            "breakdown": {
                "totals": {"bullish": 0.0, "bearish": 0.0, "risk_off": 0.0, "neutral": 0.0},
                "weighted_signals": [],
                "families_present": [],
            },
            "parameters": {
                "reliability_weights": RELIABILITY,
                "redundancy_decay": REDUNDANCY_DECAY,
                "stance_thresholds": STANCE_THRESHOLDS,
                "conflict_threshold": CONFLICT_THRESHOLD,
                "evidence_scale": EVIDENCE_SCALE,
                "max_position_pct": 25.0,
            },
            "engine": "rules",
            "disclaimer": (
                "Deterministic output of stated rules over statistical detections. "
                "Educational coursework, not investment advice."
            ),
        }

    weighed = weigh_signals(signals)
    t = weighed["totals"]
    bull, bear, risk_off, neutral = t["bullish"], t["bearish"], t["risk_off"], t["neutral"]

    directional = bull + bear
    total_evidence = directional + risk_off + neutral

    # The net score must capture two independent things, and conflating them is a
    # real trap: a lone weak bullish signal with nothing opposing it has perfect
    # *agreement* but almost no *strength*. Dividing (bull - bear) by total
    # directional evidence alone would score it +1.0 — maximum conviction from
    # one mild signal. So we factor the two apart:
    #
    #   agreement = (bull - bear) / (bull + bear)      in [-1, 1]: which way
    #   strength  = tanh(directional / EVIDENCE_SCALE) in [0, 1):  how much
    #   net_score = agreement * strength
    #
    # tanh saturates, so evidence beyond a few strong signals stops adding score
    # (there is no such thing as 300% sure), while sparse evidence is properly
    # penalised. EVIDENCE_SCALE = 1.2 means roughly two high-reliability signals
    # firing hard are needed to reach ~0.66 strength.
    agreement = ((bull - bear) / directional) if directional > 0 else 0.0
    strength = float(np.tanh(directional / EVIDENCE_SCALE))
    net_score = agreement * strength
    conflict_ratio = (min(bull, bear) / directional) if directional > 0 else 0.0

    # --- Stance
    if net_score >= STANCE_THRESHOLDS["strong_bullish"]:
        stance, action = "strong_bullish", "consider long exposure"
    elif net_score >= STANCE_THRESHOLDS["lean_bullish"]:
        stance, action = "lean_bullish", "modest long bias"
    elif net_score <= STANCE_THRESHOLDS["strong_bearish"]:
        stance, action = "strong_bearish", "consider short exposure or exit longs"
    elif net_score <= STANCE_THRESHOLDS["lean_bearish"]:
        stance, action = "lean_bearish", "modest short bias / trim longs"
    else:
        stance, action = "neutral", "no directional edge — monitor"

    rationale: List[str] = []
    demoted = False
    if conflict_ratio > CONFLICT_THRESHOLD and stance != "neutral":
        demotion = {
            "strong_bullish": ("lean_bullish", "modest long bias"),
            "lean_bullish": ("neutral", "conflicting evidence — no directional edge"),
            "strong_bearish": ("lean_bearish", "modest short bias / trim longs"),
            "lean_bearish": ("neutral", "conflicting evidence — no directional edge"),
        }
        stance, action = demotion[stance]
        demoted = True
        rationale.append(
            f"Signals disagree ({conflict_ratio*100:.0f}% of directional evidence points the "
            f"other way, above the {CONFLICT_THRESHOLD*100:.0f}% threshold), so conviction is "
            f"demoted one step rather than averaged away."
        )

    # --- Conviction: strength of the directional case, plus a bonus for
    # corroboration across *independent* families (two unrelated lines of
    # evidence agreeing is worth more than two correlated ones), minus a penalty
    # for internal disagreement.
    n_families = len({s["family"] for s in weighed["weighted_signals"]
                      if s["stance"] in ("bullish", "bearish")})
    breadth_bonus = min(n_families * 0.08, 0.24)
    conviction = float(np.clip(
        abs(net_score) * 0.75 + breadth_bonus - conflict_ratio * 0.5,
        0.0, 1.0,
    ))

    # --- Risk overlay: size, not direction.
    risk_share = risk_off / total_evidence if total_evidence > 0 else 0.0
    vol_penalty = 0.0
    if vol_percentile is not None:
        # Above the 80th percentile of its own volatility history, scale down
        # linearly to a 60% cut at the 100th percentile.
        if vol_percentile > 0.80:
            vol_penalty = (vol_percentile - 0.80) / 0.20 * 0.60
    risk_multiplier = float(np.clip(1.0 - risk_share * 0.5 - vol_penalty, 0.15, 1.0))

    # --- Position sizing.
    # Base allocation by stance, then scaled by conviction and the risk overlay.
    # This is a *fraction of a notional risk budget*, not investment advice —
    # a deliberately conservative Kelly-style cap at 25%.
    base_size = {
        "strong_bullish": 0.25, "lean_bullish": 0.12,
        "neutral": 0.0, "no_position": 0.0,
        "lean_bearish": 0.12, "strong_bearish": 0.25,
    }.get(stance, 0.0)
    position_size = base_size * conviction * risk_multiplier

    # --- Audit trail.
    # Report the strongest *directional* signal, since that is what drove the
    # stance. Quoting a neutral signal here (a cointegrated pair, say) would be
    # misleading: it carries weight in the evidence total but contributes no
    # direction, so it cannot be the reason for a bullish or bearish call.
    directional_sigs = [s for s in weighed["weighted_signals"]
                        if s["stance"] in ("bullish", "bearish")]
    top = directional_sigs[0] if directional_sigs else None
    if top:
        rationale.insert(0, (
            f"Strongest directional evidence: {top['label']} "
            f"({top['type'].replace('_', ' ')}, {top['stance']}), severity "
            f"{top['severity']:.2f} x reliability {top['reliability']:.2f} = weight "
            f"{top['effective_weight']:.3f}."
        ))
    rationale.append(
        f"Net score {net_score:+.3f} = agreement {agreement:+.2f} x evidence strength "
        f"{strength:.2f}, from {bull:.3f} bullish vs {bear:.3f} bearish weight across "
        f"{n_families} independent famil{'y' if n_families == 1 else 'ies'}."
    )
    neutral_sigs = [s for s in weighed["weighted_signals"] if s["stance"] == "neutral"]
    if neutral_sigs:
        rationale.append(
            "Informational only (no direction): "
            + ", ".join(f"{s['type'].replace('_',' ')}" for s in neutral_sigs)
            + " — these affect context and confidence but not the directional call."
        )
    discounted = [s for s in weighed["weighted_signals"] if s.get("redundancy_rank", 0) > 0]
    if discounted:
        rationale.append(
            "Redundancy discount applied to "
            + ", ".join(f"{s['type'].replace('_',' ')} (x{s['redundancy_factor']:.2f})"
                        for s in discounted)
            + " — these overlap with a stronger signal in the same family, so they are not "
              "counted as independent confirmation."
        )
    if risk_off > 0:
        rationale.append(
            f"Risk-off evidence {risk_off:.3f} ({risk_share*100:.0f}% of total) reduces "
            f"position size without changing direction."
        )
    if vol_penalty > 0:
        rationale.append(
            f"Volatility sits in the {vol_percentile*100:.0f}th percentile of its own history, "
            f"cutting size by a further {vol_penalty*100:.0f}%."
        )
    rationale.append(
        f"Final: {stance.replace('_',' ')} at {conviction*100:.0f}% conviction, "
        f"sized {position_size*100:.1f}% of the risk budget "
        f"(base {base_size*100:.0f}% x conviction x risk multiplier {risk_multiplier:.2f})."
    )

    return {
        "ticker": ticker,
        "stance": stance,
        "action": action,
        "conviction": round(conviction, 4),
        "position_size_pct": round(position_size * 100, 2),
        "net_score": round(net_score, 4),
        "conflict_ratio": round(conflict_ratio, 4),
        "conflict_flagged": bool(conflict_ratio > CONFLICT_THRESHOLD),
        "stance_demoted_for_conflict": demoted,
        "risk_multiplier": round(risk_multiplier, 4),
        "independent_families": n_families,
        "rationale": rationale,
        "breakdown": {
            "totals": weighed["totals"],
            "weighted_signals": weighed["weighted_signals"],
            "families_present": weighed["families_present"],
        },
        "parameters": {
            "reliability_weights": RELIABILITY,
            "redundancy_decay": REDUNDANCY_DECAY,
            "stance_thresholds": STANCE_THRESHOLDS,
            "conflict_threshold": CONFLICT_THRESHOLD,
            "evidence_scale": EVIDENCE_SCALE,
            "max_position_pct": 25.0,
            "_note": (
                "All thresholds are stated judgement calls, not fitted values. With a few "
                "hundred monthly observations and no out-of-sample test, fitting them would "
                "overfit more convincingly than it would inform."
            ),
        },
        "engine": "rules",
        "disclaimer": (
            "Deterministic output of stated rules over statistical detections. Educational "
            "coursework, not investment advice."
        ),
    }
