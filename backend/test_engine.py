"""
test_engine.py
--------------
Covers the two pieces of engine.py that are pure logic and easy to get subtly
wrong: the polarity map (which collapses 8 detector vocabularies onto one
bull/bear axis), the fusion maths (which replaces the old confidence score), and
the vol-mispricing detector's dead band.

Run:  pytest test_engine.py        or        python test_engine.py
"""

from engine import (
    POLARITY, polarity, fuse, rank, Signal,
    _parse_stance, unverified_numbers, _reliability,
)


def sig(stype="trend", direction="uptrend", severity=0.5, reliability=1.0, asset="TEST"):
    """Terse Signal builder — only the fields fusion actually reads."""
    return Signal(
        id=f"{stype}:{asset}:2026-01-01",
        type=stype,
        source="test",
        asset=asset,
        polarity=polarity(stype, direction),
        direction=direction,
        severity=severity,
        reliability=reliability,
        label="",
        note="",
        recommendation="",
        evidence={},
        asof="2026-01-01",
    )


# --------------------------------------------------------------------------
# Polarity map
# --------------------------------------------------------------------------

# Every (type, direction) pair the detectors in recommender.py can emit.
ALL_DIRECTIONS = [
    ("volatility_regime", "elevated"),
    ("volatility_regime", "compressed"),
    ("tail_event", "up"),
    ("tail_event", "down"),
    ("pairs_opportunity", "long spread"),
    ("pairs_opportunity", "short spread"),
    ("pairs_opportunity", "building"),
    ("trend", "uptrend"),
    ("trend", "downtrend"),
    ("macro_dislocation", "above_model"),
    ("macro_dislocation", "below_model"),
    ("breakout", "up"),
    ("breakout", "down"),
    ("breakout", "neutral"),
    ("relative_performance", "outperforming"),
    ("relative_performance", "underperforming"),
    ("options_mispricing", "rich"),
    ("options_mispricing", "cheap"),
]


def test_every_detector_direction_is_mapped():
    for stype, direction in ALL_DIRECTIONS:
        assert (stype, direction) in POLARITY, f"unmapped: {stype}/{direction}"
        assert polarity(stype, direction) in (-1, 0, 1)


def test_volatility_regime_is_never_directional():
    # Vol is a risk signal, not a bull/bear call — it must not tilt the verdict.
    assert polarity("volatility_regime", "elevated") == 0
    assert polarity("volatility_regime", "compressed") == 0


def test_directional_pairs_are_opposites():
    for stype, up, down in [
        ("tail_event", "up", "down"),
        ("trend", "uptrend", "downtrend"),
        ("breakout", "up", "down"),
        ("relative_performance", "outperforming", "underperforming"),
        ("macro_dislocation", "below_model", "above_model"),
        ("pairs_opportunity", "long spread", "short spread"),
    ]:
        assert polarity(stype, up) == 1
        assert polarity(stype, down) == -1


def test_unknown_direction_is_neutral_not_a_crash():
    # A new detector shipping an unmapped string must degrade, not explode.
    assert polarity("trend", "sideways-ish") == 0
    assert polarity("brand_new_detector", "whatever") == 0


# --------------------------------------------------------------------------
# Fusion
# --------------------------------------------------------------------------

def test_no_signals_scores_zero():
    # The old formula returned 0.2 for an empty list.
    f = fuse([])
    assert f["conviction"] == 0.0
    assert f["tilt"] == 0.0
    assert f["stance"] == "neutral"


def test_conviction_stays_in_range():
    for n in (1, 3, 6, 20):
        f = fuse([sig(severity=1.0) for _ in range(n)])
        assert 0.0 <= f["conviction"] <= 1.0


def test_one_strong_signal_beats_six_weak_ones():
    # This is the exact bug in the old score: it was count-dominated, so six
    # pieces of noise (0.15*6) outranked one decisive reading.
    strong = fuse([sig(severity=0.95, reliability=0.95)])
    weak = fuse([sig(severity=0.12, reliability=0.3) for _ in range(6)])
    assert strong["conviction"] > weak["conviction"]


def test_many_weak_signals_do_not_saturate():
    # Old formula hit the 1.0 clamp at >=6 signals regardless of quality.
    f = fuse([sig(severity=0.1, reliability=0.2) for _ in range(12)])
    assert f["conviction"] < 0.9


def test_disagreement_is_penalised():
    # Same total evidence mass, but split against itself, must score lower.
    aligned = fuse([sig(direction="uptrend", severity=0.8) for _ in range(4)])
    split = fuse(
        [sig(direction="uptrend", severity=0.8) for _ in range(2)]
        + [sig(direction="downtrend", severity=0.8) for _ in range(2)]
    )
    assert split["conviction"] < aligned["conviction"]
    assert split["agreement"] < aligned["agreement"]


def test_dissent_is_reported_not_hidden():
    f = fuse(
        [sig(direction="uptrend", severity=0.9) for _ in range(3)]
        + [sig(stype="breakout", direction="down", severity=0.4)]
    )
    assert len(f["consensus"]) == 3
    assert len(f["dissent"]) == 1
    assert f["tilt"] > 0


def test_tilt_direction_and_bounds():
    assert fuse([sig(direction="uptrend")])["tilt"] == 1.0
    assert fuse([sig(direction="downtrend")])["tilt"] == -1.0
    balanced = fuse([sig(direction="uptrend"), sig(direction="downtrend")])
    assert abs(balanced["tilt"]) < 1e-9


def test_reliability_discounts_weak_evidence():
    # Same severity, worse statistics => less conviction.
    trusted = fuse([sig(severity=0.8, reliability=0.95)])
    shaky = fuse([sig(severity=0.8, reliability=0.15)])
    assert trusted["conviction"] > shaky["conviction"]


def test_neutral_signals_carry_no_direction():
    # A pure vol/squeeze reading shouldn't create a tilt out of nothing.
    f = fuse([sig(stype="volatility_regime", direction="elevated", severity=0.9)])
    assert f["tilt"] == 0.0
    assert f["risk"] == 0.9


def test_risk_axis_tracks_worst_vol_or_tail_signal():
    f = fuse([
        sig(stype="volatility_regime", direction="elevated", severity=0.55),
        sig(stype="tail_event", direction="down", severity=0.82),
        sig(stype="trend", direction="uptrend", severity=0.99),  # not a risk signal
    ])
    assert f["risk"] == 0.82


def test_stance_label_follows_tilt_and_conviction():
    bull = fuse([sig(direction="uptrend", severity=0.9, reliability=0.9) for _ in range(3)])
    bear = fuse([sig(direction="downtrend", severity=0.9, reliability=0.9) for _ in range(3)])
    assert "bull" in bull["stance"]
    assert "bear" in bear["stance"]


# --------------------------------------------------------------------------
# Ranking, reliability, narration helpers
# --------------------------------------------------------------------------

def test_rank_is_stable_on_ties():
    # Equal weight must not reorder run to run — the old sort left ties loose.
    a = sig(stype="trend", asset="AAA", severity=0.5)
    b = sig(stype="trend", asset="BBB", severity=0.5)
    assert [s.id for s in rank([a, b])] == [s.id for s in rank([b, a])]


def test_rank_orders_by_weight_not_severity_alone():
    strong_but_shaky = sig(asset="A", severity=0.9, reliability=0.2)   # w=0.18
    milder_but_solid = sig(asset="B", severity=0.5, reliability=0.95)  # w=0.475
    assert rank([strong_but_shaky, milder_but_solid])[0].asset == "B"


def test_reliability_tracks_cointegration_pvalue():
    strong = _reliability({"type": "pairs_opportunity", "evidence": {"coint_pvalue": 0.001}})
    weak = _reliability({"type": "pairs_opportunity", "evidence": {"coint_pvalue": 0.9}})
    assert strong > weak
    assert 0.0 <= weak <= strong <= 1.0


def test_reliability_survives_missing_evidence():
    # A detector that omits its evidence key must not crash the scan.
    for t in ("pairs_opportunity", "macro_dislocation", "trend", "volatility_regime"):
        r = _reliability({"type": t, "evidence": {}})
        assert 0.0 <= r <= 1.0


def test_stance_parsing_prefers_the_longer_match():
    # "cautiously bullish" contains "bullish" — the qualifier must win.
    assert _parse_stance("STANCE: cautiously bullish") == "cautiously bullish"
    assert _parse_stance("STANCE: bullish") == "bullish"
    assert _parse_stance("STANCE: cautiously bearish") == "cautiously bearish"


def test_stance_parsing_tolerates_model_noise():
    assert _parse_stance("**STANCE:** Bearish.") == "bearish"
    assert _parse_stance("stance:   NEUTRAL  ") == "neutral"
    assert _parse_stance("waffle with no stance at all") == "neutral"


def test_guardrail_accepts_cited_numbers():
    scan = {"signals": [{"severity": 0.72, "evidence": {"z_sigma": 2.41}}], "verdict": {}}
    assert unverified_numbers("z reached 2.41 with severity 0.72", scan) == []


def test_guardrail_ignores_sign_and_percent_rendering():
    # Real false positives seen from the model: evidence holds -16.8 and 0.86,
    # the note says "fell 16.8%" and "86th percentile". Neither is invented.
    scan = {
        "signals": [{"severity": 0.5, "evidence": {"ret_3m_pct": -16.8, "vol_percentile": 0.86}}],
        "verdict": {},
    }
    assert unverified_numbers("fell 16.8% and sits at the 86th percentile", scan) == []


def test_guardrail_allows_numbers_from_evidence_keys():
    # "ma50" in the evidence licenses the model saying "50-day average".
    scan = {"signals": [{"severity": 0.5, "evidence": {"ma50": 402.56, "ma200": 414.71}}],
            "verdict": {}}
    assert unverified_numbers("below its 50-day and 200-day averages", scan) == []


def test_guardrail_flags_invented_numbers():
    scan = {"signals": [{"severity": 0.72, "evidence": {"z_sigma": 2.41}}], "verdict": {}}
    flagged = unverified_numbers("the price target is 4821.55", scan)
    assert "4821.55" in flagged


# --------------------------------------------------------------------------
# Vol-mispricing detector
# --------------------------------------------------------------------------

def _detect_with_vols(iv, garch_vol, available=True):
    """
    Run the detector against a stubbed option chain. The detector imports from
    analysis.market_options *inside* the function, so patching the module
    attributes here takes effect at call time.

    Patched by hand rather than with the monkeypatch fixture, because the
    __main__ runner below calls every test with no arguments.
    """
    from analysis import recommender as rec
    from analysis import market_options as mo

    ratio = (iv / garch_vol) if garch_vol else None
    stubs = {
        "get_spot": lambda t: 100.0,
        "get_risk_free_rate": lambda: {"rate_cc": 0.04},
        "get_dividend_yield": lambda t: {"q": 0.0},
        "garch_vol_term_structure": lambda t, horizon_days=30: {"sigma_garch": garch_vol},
        "_compare_to_chain": lambda *a, **k: {
            "available": available,
            "market_implied_vol_pct": iv * 100,
            "model_forecast_vol_pct": garch_vol * 100,
            "variance_risk_premium_pct": (iv - garch_vol) * 100,
            "iv_to_model_ratio": ratio,
            "days_to_expiry": 30,
            "expiry_used": "2026-08-21",
            "nearest_strike": 100.0,
        },
    }
    real = {k: getattr(mo, k) for k in stubs}
    for k, v in stubs.items():
        setattr(mo, k, v)
    try:
        return rec.detect_options_mispricing("TEST")
    finally:
        for k, v in real.items():
            setattr(mo, k, v)


def test_options_mispricing_is_silent_inside_the_dead_band():
    # Implied within ±15% of the GARCH forecast is not worth a signal.
    assert _detect_with_vols(0.25, 0.24) is None
    assert _detect_with_vols(0.24, 0.25) is None


def test_options_mispricing_reads_rich_and_cheap():
    rich = _detect_with_vols(0.40, 0.20)
    assert rich["direction"] == "rich"
    assert rich["type"] == "options_mispricing"
    assert 0.0 <= rich["severity"] <= 1.0
    assert rich["evidence"]["iv_to_model_ratio"] == 2.0

    cheap = _detect_with_vols(0.10, 0.20)
    assert cheap["direction"] == "cheap"
    assert cheap["evidence"]["iv_to_model_ratio"] == 0.5


def test_options_mispricing_needs_a_chain():
    # No chain, or a zero forecast, must be silence rather than a divide by zero.
    assert _detect_with_vols(0.40, 0.20, available=False) is None
    assert _detect_with_vols(0.24, 0.0) is None


def test_options_mispricing_never_moves_the_verdict():
    # Premium being expensive is not a directional call. It must leave tilt and
    # the risk axis alone, or the gauge starts lying.
    signals = [sig("options_mispricing", "rich", severity=1.0)]
    v = fuse(signals)
    assert v["tilt"] == 0.0
    assert v["risk"] == 0.0
    assert v["stance"] == "neutral"


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                passed += 1
            except AssertionError as e:
                failed += 1
                print(f"FAIL {name}: {e}")
    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
