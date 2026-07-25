"""
engine.py
---------
The decision engine. The analysis modules (macro regression, GARCH, pairs)
stay exactly as they are and remain independently callable — this layer sits
above them, normalises what their detectors emit, and fuses it into one view.

Two jobs live here:

  1. **Normalisation.** The seven detectors in recommender.py speak seven
     different direction vocabularies ("uptrend", "above_model", "long
     spread", "compressed"...). POLARITY collapses all of them onto a single
     bull/bear/neutral axis so they can be compared and netted at all.

  2. **Fusion.** A weighted score that replaces the old confidence line
     (`0.2 + 0.15*len(signals) + 0.3*top_severity`), which was dominated by
     signal *count* and clamped to 1.0 once six of anything showed up.

Design rule inherited from TODO.md: stats detect, the LLM explains. Nothing
in this file calls a model, and the model never feeds back into these numbers.
"""

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from functools import lru_cache
from math import exp


# ---------------------------------------------------------------------------
# Signal contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Signal:
    """
    One detection, normalised. Adds what the old dicts lacked: a stable id, the
    originating module, a bull/bear polarity, a statistical-trust weight, and
    the `asof` timestamp specified in TODO.md but never implemented.
    """
    id: str            # f"{type}:{asset}:{asof}" — stable keys, reproducible sort
    type: str
    source: str        # "garch" | "macro" | "pairs" | "price" — drives drill-down
    asset: str
    polarity: int      # -1 bearish | 0 neutral | +1 bullish
    direction: str     # the detector's original wording, preserved for display
    severity: float    # 0..1  how extreme the reading is
    reliability: float # 0..1  how much the statistics justify trusting it
    label: str
    note: str
    recommendation: str
    evidence: dict
    asof: str

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Polarity: seven vocabularies onto one axis
# ---------------------------------------------------------------------------

POLARITY = {
    # Volatility is a *risk* reading, not a directional call. It feeds the
    # separate `risk` axis so a vol spike never fakes a bull/bear verdict.
    ("volatility_regime", "elevated"): 0,
    ("volatility_regime", "compressed"): 0,

    ("tail_event", "up"): +1,
    ("tail_event", "down"): -1,

    # For a pair the spread *is* the asset: long spread = bullish the spread.
    ("pairs_opportunity", "long spread"): +1,
    ("pairs_opportunity", "short spread"): -1,
    ("pairs_opportunity", "building"): 0,   # not yet actionable

    ("trend", "uptrend"): +1,
    ("trend", "downtrend"): -1,

    # Trading rich to what macro predicts implies reversion *down*, and vice
    # versa — so the sign is deliberately inverted relative to the wording.
    ("macro_dislocation", "above_model"): -1,
    ("macro_dislocation", "below_model"): +1,

    ("breakout", "up"): +1,
    ("breakout", "down"): -1,
    ("breakout", "neutral"): 0,             # squeeze, no resolution yet

    ("relative_performance", "outperforming"): +1,
    ("relative_performance", "underperforming"): -1,
}

# Types that describe risk rather than direction.
RISK_TYPES = ("volatility_regime", "tail_event")

# Which module produced each detector — powers "drill into the source" links.
SOURCE = {
    "volatility_regime": "garch",
    "tail_event": "garch",
    "macro_dislocation": "macro",
    "pairs_opportunity": "pairs",
    "trend": "price",
    "breakout": "price",
    "relative_performance": "price",
}


def polarity(signal_type: str, direction: str) -> int:
    """Map a detector's direction string onto -1/0/+1. Unknown => neutral."""
    return POLARITY.get((signal_type, direction), 0)


# ---------------------------------------------------------------------------
# Fusion
# ---------------------------------------------------------------------------

# Evidence-mass scale. Total weight of ~2.0 lands near 0.63 conviction, ~4.0
# near 0.86 — strong readings converge without any single one pinning to 1.0.
K = 2.0


def _stance(tilt: float, conviction: float) -> str:
    """Human label for the computed verdict (distinct from the LLM's opinion)."""
    if conviction < 0.15 or abs(tilt) < 0.15:
        return "neutral"
    decisive = conviction >= 0.5 and abs(tilt) >= 0.5
    if tilt > 0:
        return "bullish" if decisive else "cautiously bullish"
    return "bearish" if decisive else "cautiously bearish"


def fuse(signals: list) -> dict:
    """
    Combine signals into a verdict.

        w_i        = severity × reliability
        bull/bear  = Σ w_i by polarity
        tilt       = (bull − bear) / (bull + bear)      directional read, −1..+1
        agreement  = 1 − min/max                        how one-sided, 0..1
        mass       = 1 − exp(−total / K)                saturating evidence weight
        conviction = mass × (0.4 + 0.6 × agreement)

    Strength beats count, nothing pins to 1.0 on noise, and signals pointing
    the other way actively reduce conviction instead of inflating it.
    """
    risk = max(
        [s.severity for s in signals if s.type in RISK_TYPES],
        default=0.0,
    )

    bull = sum(s.severity * s.reliability for s in signals if s.polarity > 0)
    bear = sum(s.severity * s.reliability for s in signals if s.polarity < 0)
    total = bull + bear

    if total <= 0:
        # No directional evidence — empty, or only neutral readings (a pure
        # vol regime or an unresolved squeeze). Risk can still be non-zero.
        return {
            "conviction": 0.0, "tilt": 0.0, "agreement": 0.0,
            "stance": "neutral", "risk": round(risk, 3),
            "bull": 0.0, "bear": 0.0,
            "consensus": [], "dissent": [],
        }

    tilt = (bull - bear) / total
    agreement = 1.0 - (min(bull, bear) / max(bull, bear))
    mass = 1.0 - exp(-total / K)
    conviction = mass * (0.4 + 0.6 * agreement)

    side = 1 if tilt > 0 else -1 if tilt < 0 else 0
    return {
        "conviction": round(conviction, 3),
        "tilt": round(tilt, 3),
        "agreement": round(agreement, 3),
        "stance": _stance(tilt, conviction),
        "risk": round(risk, 3),
        "bull": round(bull, 3),
        "bear": round(bear, 3),
        "consensus": [s.id for s in signals if side and s.polarity == side],
        "dissent": [s.id for s in signals if side and s.polarity == -side],
    }


def rank(signals: list) -> list:
    """
    Order by evidence weight, tie-broken on id so the ordering is reproducible
    across runs (the old code sorted on severity alone, leaving ties unstable).
    """
    return sorted(signals, key=lambda s: (-(s.severity * s.reliability), s.id))


# ---------------------------------------------------------------------------
# Adapting the existing detectors
# ---------------------------------------------------------------------------

def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _reliability(d: dict) -> float:
    """
    How far the statistics justify trusting a detection, 0..1. Derived from
    each detector's own evidence — never invented, never model-supplied.
    """
    ev = d.get("evidence") or {}
    t = d.get("type")

    if t == "pairs_opportunity":
        # The cointegration p-value is already a confidence measure.
        p = ev.get("coint_pvalue")
        return _clamp(1.0 - float(p)) if p is not None else 0.5

    if t == "macro_dislocation":
        # A large residual only means something if the model explains anything
        # at all; floor it so a weak-but-real model isn't zeroed out.
        r2 = ev.get("macro_r2")
        return _clamp(0.35 + 0.65 * float(r2)) if r2 is not None else 0.5

    if t in RISK_TYPES:
        # GARCH fits on ~2700 daily observations — well identified.
        return 0.85

    # Price rules (trend, breakout, relative performance): sound, widely used
    # heuristics, but not inferential tests. Trusted less than a fitted model.
    return 0.65


def to_signal(d: dict, asof: str) -> Signal:
    """Normalise one raw detector dict into a Signal."""
    stype = d["type"]
    asset = d["asset"]
    return Signal(
        id=f"{stype}:{asset}:{asof}",
        type=stype,
        source=SOURCE.get(stype, "price"),
        asset=asset,
        polarity=polarity(stype, d.get("direction", "")),
        direction=d.get("direction", ""),
        severity=_clamp(float(d.get("severity", 0.0))),
        reliability=_reliability(d),
        label=d.get("label", ""),
        note=d.get("note", ""),
        recommendation=d.get("recommendation", ""),
        evidence=d.get("evidence", {}),
        asof=asof,
    )


# ---------------------------------------------------------------------------
# Tiered scan
# ---------------------------------------------------------------------------

# Scanned by default. Anything outside this list still works — it just runs
# on demand (and then caches) instead of being pre-warmed.
UNIVERSE = [
    "^GSPC", "^IXIC", "^DJI", "AAPL", "MSFT", "NVDA",
    "AMZN", "GOOGL", "META", "TSLA", "JPM", "GLD",
]

_scan_lock = threading.Lock()


def _data_date(ticker: str) -> str:
    """Last bar date — the natural cache key for anything fitted on the data."""
    from data_loader import get_equity_data
    return get_equity_data(ticker).index[-1].date().isoformat()


@lru_cache(maxsize=64)
def _garch_tier(ticker: str, data_date: str):
    """
    T3. The expensive tier: a GARCH MLE over ~2700 observations. Keyed on the
    data's last date rather than wall-clock, so daily bars mean one fit a day
    no matter how many requests arrive.
    """
    from analysis.garch import fit_garch, get_return_distribution
    return fit_garch(ticker), get_return_distribution(ticker)


@lru_cache(maxsize=8)
def _pairs_tier(pairs: tuple, data_date: str):
    """
    Shared tier. One cointegration sweep for the whole FX basket, reused by
    every asset in a scan instead of being re-run per asset.
    """
    from analysis.pairs import get_best_pair_analysis
    return get_best_pair_analysis(list(pairs) if pairs else None)


def scan_asset(ticker: str, pairs=None, heavy: bool = True) -> dict:
    """
    Run every detector for one asset, normalise, and fuse.

    heavy=False skips the GARCH tier — the fast path for a broad sweep where
    the price and macro tiers already say enough to rank an opportunity.

    Keyed on the data's last date, so the whole scan is recomputed exactly
    once per asset per trading day however many requests arrive. The result is
    shared and must be treated as read-only.
    """
    return _scan_asset_cached(
        ticker, tuple(pairs) if pairs else None, heavy, _data_date(ticker)
    )


@lru_cache(maxsize=64)
def _scan_asset_cached(ticker: str, pairs: tuple, heavy: bool, asof: str) -> dict:
    """
    Individual detector failures are recorded, never raised: one dead factor
    should cost a single signal, not the whole verdict.
    """
    from analysis import recommender as rec

    raw, diagnostics = [], {}

    garch = dist = best = None
    if heavy:
        try:
            garch, dist = _garch_tier(ticker, asof)
        except Exception as e:  # noqa: BLE001
            diagnostics["garch"] = str(e)
    try:
        best = _pairs_tier(pairs, asof)
    except Exception as e:  # noqa: BLE001
        diagnostics["pairs"] = str(e)

    calls = [
        (rec.detect_volatility_regime, (ticker, garch)) if garch else None,
        (rec.detect_tail_event, (ticker, dist)) if dist else None,
        (rec.detect_pairs_opportunity, (pairs, best)) if best else None,
        (rec.detect_trend, (ticker,)),
        (rec.detect_macro_dislocation, (ticker,)),
        (rec.detect_breakout, (ticker,)),
        (rec.detect_relative_performance, (ticker,)),
    ]
    for entry in calls:
        if entry is None:
            continue
        fn, args = entry
        try:
            d = fn(*args)
            if d:
                raw.append(d)
        except Exception as e:  # noqa: BLE001
            diagnostics[fn.__name__] = str(e)

    signals = rank([to_signal(d, asof) for d in raw])
    return {
        "asset": ticker,
        "asof": asof,
        "verdict": fuse(signals),
        "signals": [s.to_dict() for s in signals],
        "diagnostics": diagnostics,   # always present, so "no signal" is
                                      # distinguishable from "detector failed"
    }


def scan_universe(pairs=None, limit: int = 12) -> dict:
    """
    Scan the whole universe and build the cross-asset feed.

    Held under a lock so a burst of requests during a cold warm collapses into
    one sweep instead of stampeding the same GARCH fits.
    """
    with _scan_lock:
        with ThreadPoolExecutor(max_workers=6) as pool:
            # pandas/numpy/statsmodels/arch release the GIL in their hot loops,
            # so threads genuinely overlap here.
            assets = list(pool.map(lambda t: scan_asset(t, pairs), UNIVERSE))

    feed = []
    for a in assets:
        for s in a["signals"]:
            feed.append({**s, "conviction": a["verdict"]["conviction"]})
    feed.sort(key=lambda s: (-(s["severity"] * s["reliability"]), s["id"]))

    return {
        "asof": max((a["asof"] for a in assets), default=""),
        "universe": UNIVERSE,
        "feed": feed[:limit],
        "assets": [
            {"asset": a["asset"], "verdict": a["verdict"], "n_signals": len(a["signals"])}
            for a in assets
        ],
    }


def warm():
    """Pre-compute the universe so the first request isn't the slow one."""
    try:
        scan_universe()
        print(f"[engine] warm complete — {len(UNIVERSE)} assets")
    except Exception as e:  # noqa: BLE001 — warming must never break startup
        print(f"[engine] warm failed: {e}")


# ---------------------------------------------------------------------------
# Narration — the model explains, and offers a labelled opinion
# ---------------------------------------------------------------------------

STANCES = ("bullish", "cautiously bullish", "neutral", "cautiously bearish", "bearish")

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _parse_stance(line: str) -> str:
    """Pull the stance out of the model's first line. Unrecognised => neutral."""
    text = line.replace("STANCE:", "").strip().lower().strip(".*_ ")
    # Longest first, so "cautiously bullish" wins over "bullish".
    for s in sorted(STANCES, key=len, reverse=True):
        if s in text:
            return s
    return "neutral"


def _cited_numbers(scan: dict) -> set:
    """
    Every figure the model could legitimately quote back, normalised for
    comparison. Sign is dropped (a note may say "fell 16.8%" where the
    evidence holds -16.8) and 0..1 ratios are also allowed in percent form
    (0.86 cited as "86"). Numbers baked into the labels and evidence *keys*
    we supplied count too — "ma50" licenses "the 50-day average".
    """
    out = set()

    def add(v):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            f = abs(float(v))
            out.add(round(f, 2))
            out.add(round(f * 100, 2))

    def add_text(text: str):
        for token in _NUMBER.findall(text or ""):
            out.add(round(abs(float(token)), 2))

    for s in scan.get("signals", []):
        add(s.get("severity"))
        for k, v in (s.get("evidence") or {}).items():
            add(v)
            add_text(k)
        add_text(f"{s.get('label', '')} {s.get('note', '')}")
    for v in (scan.get("verdict") or {}).values():
        add(v)
    return out


def unverified_numbers(text: str, scan: dict) -> list:
    """
    Figures in the narrative that don't match anything we supplied.

    Advisory, not a hard gate — incidental integers ("3 signals", "50-day")
    will show up here too. It exists to catch a model inventing a price or a
    statistic, which is the failure mode that actually matters.
    """
    allowed = _cited_numbers(scan)
    flagged = []
    for token in _NUMBER.findall(text):
        n = round(abs(float(token)), 2)
        if not any(abs(n - a) <= 0.05 for a in allowed):
            flagged.append(token)
    return flagged


def _narrative_prompt(scan: dict) -> tuple:
    v = scan["verdict"]
    # Compact JSON and a top-6 cap: the old prompt sent indent=2 over every
    # signal, which is pure token cost on a 4k-context local model.
    payload = [
        {k: s[k] for k in ("type", "asset", "direction", "label", "severity", "evidence")}
        for s in scan["signals"][:6]
    ]
    system = (
        "You are a precise quant analyst explaining a computed market read.\n"
        "Reply in EXACTLY this shape:\n"
        "STANCE: <one of: bullish, cautiously bullish, neutral, "
        "cautiously bearish, bearish>\n"
        "\n"
        "<3-5 sentences of explanation>\n"
        "\n"
        "The STANCE line is your own read. It may differ from the computed "
        "stance if the evidence warrants — say so if it does. "
        "Use ONLY the numbers given to you: never invent a figure, price or "
        "date. Explain what the signals mean and what is driving them, then "
        "end with one cautious 'what to watch'. "
        "No preamble, no disclaimers, no bullet lists."
    )
    user = (
        f"Asset: {scan['asset']}\n"
        f"Computed verdict: stance={v['stance']}, conviction={v['conviction']}, "
        f"tilt={v['tilt']}, risk={v['risk']}, "
        f"{len(v['consensus'])} signals agree / {len(v['dissent'])} dissent\n"
        f"Signals: {json.dumps(payload, separators=(',', ':'), default=str)}\n\n"
        "Write the stance line and the note."
    )
    return system, user


def narrate_stream(scan: dict):
    """
    Yield (event, data) pairs describing the model's reading of a scan:

        ("stance", "cautiously bearish")   once the first line resolves
        ("token",  "…text…")               repeatedly, as generated
        ("done",   {"unverified_numbers": [...]})

    The stance arrives after roughly ten tokens, so the UI can label the
    model's opinion almost immediately and stream the reasoning beneath it.
    """
    import llm_client

    if not scan.get("signals"):
        yield "done", {"skipped": "no signals to explain"}
        return
    if not llm_client.available():
        yield "done", {"skipped": "LLM unavailable"}
        return

    system, user = _narrative_prompt(scan)
    full, head_buf, stance_sent = "", "", False

    for piece in llm_client.chat_stream(system, user, max_tokens=220, temperature=0.3):
        full += piece
        if stance_sent:
            yield "token", piece
            continue
        head_buf += piece
        if "\n" in head_buf:
            head, _, rest = head_buf.partition("\n")
            yield "stance", _parse_stance(head)
            stance_sent = True
            if rest:
                yield "token", rest

    if not stance_sent:
        # Model answered without a line break — salvage what it did say.
        head, _, rest = head_buf.partition("\n")
        yield "stance", _parse_stance(head)
        if rest:
            yield "token", rest

    yield "done", {"unverified_numbers": unverified_numbers(full, scan)}
