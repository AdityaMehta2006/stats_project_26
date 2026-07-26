# QuantAnomalies — Roadmap / TODO

Forward-looking plan. Items tagged **P0** (next), **P1** (soon), **P2** (later).
Done items are at the bottom.

> **Status as of 26 July 2026.** Sections 1a–1c, 2, 3 and most of 4–5 have
> shipped and are checked off below; §1 was superseded in scope by the unified
> decision engine (`backend/engine.py`), which fuses the detectors rather than
> just ranking them. The narrative record of what landed is in
> `DOCUMENTATION.md`. What remains open is concentrated in **§8 statistical
> rigor** — see "Still open (next)" at the very bottom.

The headline direction: evolve the static three-pillar dashboard into a
**Recommendation Engine that surfaces market anomalies & opportunities**,
explained in plain English by a **local LLM**. The existing pillars (macro
regression, GARCH, pairs) become the *signal sources*; a new engine *detects*
anomalies with rules/stats and the LLM *explains and prioritises* them.

Design principle: **stats detect, LLM explains.** The LLM never computes or
invents numbers — it is handed structured detections as JSON and writes the
narrative + recommendation, citing only those numbers. This keeps it grounded
and lets us run a small local model.

---

## 1. Recommendation / Anomaly–Opportunity Engine (headline) — ✅ DONE

Shipped, and then superseded in scope: the detectors below all exist in
`backend/analysis/recommender.py`, but ranking and confidence now live in
`backend/engine.py`, which normalises polarity and *fuses* the signals instead
of just counting them.

### 1a. Detectors (rules over existing pillar outputs — deterministic, free)
Module `backend/analysis/recommender.py`. Each detector emits a structured
signal `{type, asset, direction, severity 0–1, evidence:{metric:value}, asof}`:
- [x] **Volatility regime** — current GARCH conditional σ vs its trailing
      percentile → "elevated / compressed vol".
- [x] **Tail event** — latest return's size in GARCH-σ units (|z|) combined with
      high excess kurtosis → "outsized move / fat-tail day".
- [x] **Pairs opportunity** — cointegrated pair (p<0.05) with |z|>2 → actionable
      mean-reversion entry; z crossing back through ±2 → exit.
- [x] **Macro dislocation** — large OLS residual: asset moving against what macro
      factors predict.
- [x] **Relative / cross-section** — ranks the scanned universe by how extreme
      each asset is today.
- [x] **Trend / breakout** — price vs rolling mean, new N-day high/low, squeeze.
- [x] Rank all signals and produce an overall confidence. *Delivered as fusion,
      not a count:* weight = severity × reliability, plus `tilt`, `agreement`,
      saturating evidence `mass`, a separate `risk` axis, and explicit dissent.

### 1b. LLM explainer (local model — Gemma 4 / Qwen3-4B)
- [x] Send the ranked detections JSON to the model and get back a labelled
      stance plus a 3–5 sentence explanation citing the evidence. Streams via
      SSE, stance-first, so the opinion lands in ~10 tokens.
- [x] **Provider-agnostic client** (`llm_client.py`): config via env
      `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`. Defaults to the local
      llama.cpp server (§2); any OpenAI-compatible endpoint is a drop-in swap.
- [x] Guardrails: the prompt forbids invented figures, and
      `engine.unverified_numbers()` checks the narrative against the supplied
      evidence and surfaces mismatches in the UI. Rules-only summary is the
      fallback when no model is up.

### 1c. API + Frontend
- [x] Endpoints — delivered as `/api/engine/{feed,asset,narrate,status}`.
      (`/api/recommendations` was the v1 route and is now unused; see the
      cleanup note at the bottom.)
- [x] **"Opportunities"** tab: verdict strip (stance / conviction / tilt gauge /
      risk meter), a hairline signal list with severity bars and evidence chips,
      a visible dissent group, per-pillar drill-down from each source badge, and
      on-demand streaming LLM narration beside the computed stance.

### 1d. Future detectors — opportunity engine v2
Each is another *lens* for spotting opportunity (stats detect, AI explains):
- [ ] **Valuation / "is it bloated?"** — fundamental ratios (P/E, P/B, P/S, PEG,
      EV/EBITDA from `yfinance` `Ticker.info`) vs the stock's own history and peers,
      plus a technical stretch check (% above 200-DMA, RSI). Flags "priced for
      perfection" (avoid/short) vs "on sale" (value buy).
- [ ] **Options vol-mispricing** — implied vol (Black–Scholes, §7) vs GARCH forecast → options rich/cheap.
- [ ] **Momentum & relative strength** — rank a universe by risk-adjusted 12–1 month momentum.
- [ ] **Oversold bounce** — distance from 52-week high + RSI → mean-reversion candidates.
- [ ] **Volatility squeeze** — Bollinger/Keltner compression → breakout setup.
- [ ] **Correlation-regime shift** — usually-correlated assets decoupling.
- [ ] **Seasonality / calendar effects** — turn-of-month, "sell in May", day-of-week.
- [ ] **Alpha vs beta** — separate market-driven moves from stock-specific mispricing.
- [ ] **Unusual volume** — accumulation/distribution vs average.
- [ ] **Risk budgeting** — convert the detected regime into a suggested position size.

### 1e. Decision-engine modes — rules vs LLM
Current design is a hybrid with a UI toggle: **rules detect, LLM explains**.
- Rules-based: deterministic, transparent, instant, exact numbers, offline — but rigid.
- LLM-based: flexible, natural-language synthesis — but slower and needs guardrails.
- [ ] Add an optional **LLM decision-maker** mode (the model also weighs/ranks
      signals, not just explains), kept honest by rule-based guardrails + number
      validation. Keep pure-rules as the safe default.

---

## 2. Local LLM runtime setup — ✅ DONE

- [x] Runs as an **OpenAI-compatible sidecar** — the bundled Vulkan
      `llama-server.exe -ngl 99 -c 4096 --port 8080`, decoupled and restartable.
- [x] Backend calls `http://localhost:8080/v1/chat/completions`, streaming.
- [x] Model swappable via `LLM_MODEL`. **Qwen3-4B** won on structured analysis
      and is the default.
- [x] The installed `llama_cpp_python` turned out to be **CPU-only**; rather
      than rebuild for CUDA we route GPU work through the Vulkan llama.cpp
      server (~28 tok/s) and keep the in-process CPU path as fallback.
- [x] Health probe — `/api/llm/info` and `/api/engine/status`, so the UI shows
      live / warming / offline and degrades to rules cleanly.

---

## 3. Proper scaling & normalization — ✅ DONE

- [x] **Macro factors z-score standardized before OLS** → coefficients are now
      comparable standardized betas (effect per 1-SD move), which is what the
      macro-dislocation detector and the "Top Return Drivers" ranking read.
- [x] **Forex prices log-transformed before spread + hedge ratio** — the hedge
      ratio no longer collapses (USDCHF/USDJPY now −0.339, was ~−0.002) and
      z-scores are comparable across pairs. `spread_type` records which was used.
- [x] **VIX as log-change** for stationarity; documented in the module header
      and in the API's `note` field.
- [x] **Consistent display units** via `frontend/src/utils/format.js`
      (`fmtPct`, `fmtPctRaw`, `fmtNum`, p-value formatting).

---

## 4. Charts: time filter, scaling, asset toggle, news-on-click — P1

- [x] **Time-range filter** on every chart (1M / 3M / 6M / 1Y / 5Y / All) with the
      y-axis **autoscaling** to the visible window (`common/TimeRangeFilter.jsx`).
- [x] **Shared ticker selection across all tabs** via context (`ticker.js` +
      `TickerContext.jsx`) — panels used to hold a private `useState("^GSPC")`.
- [ ] **Compare mode** — overlay 2–3 assets at once. *(Not built; the shared
      ticker covers the switching half of this item.)*
- [ ] **News on chart click** — clicking a point opens that date's headlines for
      the ticker; the LLM can then correlate the move with the news ("the −4% day
      coincided with …"). Data source options (no/low cost): **GDELT Doc API**
      (free, historical, no key — best fit), Yahoo Finance news (recent only),
      or NewsAPI/Marketaux (key, limited free tier). Cache responses.

---

## 5. UI polish — mostly done

- [x] Loading **skeletons** per card, layout-matched, dim-in-place on refetch.
      The centred spinner is gone.
- [x] Axis **unit labels** and tick formatting (`minTickGap`, `tickMargin`,
      explicit label height) across every chart.
- [x] Empty / partial states — `common/StatusStates.jsx` covers skipped factor,
      no signals, LLM offline, and a readable 404 for an unknown ticker.
- [x] **Light mode** — light is now the *default* (survives a projector), dark
      follows the OS, three-state toggle in the header, all 30 token pairings
      verified ≥4.5:1 in both schemes.
- [x] `asof` date threads through the engine and renders on the verdict.
- [ ] Manual **refresh data** button that busts the CSV cache for the current
      ticker. *(The backend helper exists; no UI control yet.)*
- [ ] Mobile pass on tables and heatmaps. *(Bento grids tile at every
      breakpoint; the dense tables and the heatmap still need a pass.)*

---

## 6. Data & robustness — partly done

- [x] **Cross-seeding root cause fixed** — it was not a cache bug: `yfinance`
      is **not thread-safe**, and concurrent `yf.download()` calls silently
      return one ticker's data under another's name. Downloads are now
      serialized behind a lock; cached reads stay parallel.
- [x] **Staleness handling** — `END` was hardcoded to `2025-12-31` and caches
      never expired (the dashboard was reasoning over 7-month-old data). Now a
      rolling end date plus an mtime age check, falling back to the stale copy
      if a refresh fails.
- [ ] **Metadata sidecar** per cache (ticker, fetch date, row count).
- [ ] Timeout-wrap the `pandas_datareader` FRED fallback (it can hang).
- [~] Tests — `backend/test_engine.py` (25 cases) exists. Still missing:
      `data_loader` unit tests and a pytest smoke suite over every endpoint.
- [ ] README: pin deps; document the Anaconda interpreter requirement (`python`
      on this machine is the broken Store stub) and the local-LLM sidecar.

---

## 7. Options pricing — Black–Scholes — mostly done

Adds an options layer that ties directly into the volatility pillar and feeds the recommender.
- [x] New module `backend/analysis/black_scholes.py`:
  - Black–Scholes–Merton price for European calls/puts:
    `C = S·N(d1) − K·e^(−rT)·N(d2)`,  `P = K·e^(−rT)·N(−d2) − S·N(−d1)`,
    with `d1 = [ln(S/K) + (r + σ²/2)T] / (σ√T)` and `d2 = d1 − σ√T`.
  - Greeks: delta, gamma, vega, theta, rho.
  - Implied-volatility solver (Newton / bisection) from a market option price.
- [x] Inputs: spot from the ticker, `r` from the 10Y, `σ` from the GARCH forecast
      or user input (`_risk_free_rate()`, `_model_vol()`, `analyze_option()`).
- [x] Endpoint `GET /api/options/black-scholes?ticker=&strike=&expiry=`.
- [ ] **Vol-mispricing detector** for the engine: `analyze_option` already
      computes a `vol_verdict` (implied vs GARCH-forecast vol) — nothing
      consumes it yet.
- [ ] UI card (price, Greeks, implied-vol-vs-GARCH gauge) — no frontend
      surface for the options endpoint at all right now.

---

## 8. Analysis depth & statistical rigor — **P0 (now the biggest gap)**

The detectors are built and the plumbing is solid; what is unvalidated is the
inference underneath. Detail in "Still open (next)" at the bottom.
- [ ] Rolling / out-of-sample regression (does macro sensitivity drift over time?).
- [ ] GARCH variants (EGARCH / GJR for the leverage effect) in the comparison.
- [ ] **Backtest** the pair-trading + recommendation signals (PnL, Sharpe,
      drawdown) instead of only listing them — turns "opportunities" into evidence.
- [ ] Multiple-testing correction for the cointegration matrix (many pairs → false
      positives).
- [ ] Let users choose the macro factor set and lag depth from the UI.

---

## Done (for context)
- Fixed broken FRED downloads (User-Agent) + added DBnomics fallback.
- 10Y yield sourced from Yahoo `^TNX` (skips flaky FRED DGS10).
- Added Gold + US Dollar Index factors; made `build_macro_dataset` fault-tolerant.
- Cleaned corrupted equity caches (VIX/oil were cross-seeded) and restored EURGBP.
- Frontend redesign: "quant terminal" theme, SVG icon set, hover info-tooltips,
  explanatory copy, stealth SVG background.
- Cleaned up git: ignore data caches + `.env`; untracked committed CSVs.
- Confirmed local LLM is runnable (llama-cpp-python + GGUF models + RTX 4050).
- **Recommendation engine v1 shipped** (§1): `recommender.py` with 4 detectors
  (volatility regime, tail event, trend, forex mean-reversion), ranked by severity
  with a confidence score; `GET /api/recommendations` + `GET /api/llm/info`.
- **Local LLM wired** (§2): provider-agnostic `llm_client.py` running Qwen3-4B
  in-process (default), with rules-only fallback. Note: the installed
  llama-cpp-python is a **CPU build** (~9 tok/s) — GPU offload needs a CUDA rebuild.
- **"Opportunities" tab** (§1c): ranked signal cards (severity meters, evidence
  chips, recommendations) + on-demand local-LLM analyst note.

- **GPU inference enabled** (§2): the LLM now runs on the **RTX 4050 via the bundled
  Vulkan llama.cpp server** (`E:\odysseus\binaries\llama_server\llama-server.exe`,
  `-ngl 99`). `llm_client.py` auto-prefers the GPU server (~28 tok/s) and falls back
  to in-process CPU if it's not running. LLM recommendation latency: 25s → ~4s.
- **Chart time filters + framer-motion pass** (§4): animated segmented range control
  (1M–All) on GARCH, Pairs, and Macro charts with y-axis autoscaling; AnimatePresence
  tab transitions; sliding shared-layout indicators on nav + range pills; animated
  confidence/severity bars.

- **Unified decision engine shipped** (`backend/engine.py`): the three pillars are
  now scored signal sources behind one verdict, while every per-module endpoint
  stays untouched for drill-down.
  - **Signal contract** — stable `id`, `source`, `asof`, plus `polarity` (the 7
    detector vocabularies collapsed onto one bull/bear axis) and `reliability`
    (derived from each detector's own statistics: cointegration p-value, macro R²,
    GARCH sample size).
  - **Fusion** replaces the old `0.2 + 0.15·n + 0.3·top` confidence, which was
    count-dominated and clamped to 1.0 at ≥6 signals. Now weight = severity ×
    reliability, with `tilt`, `agreement`, a saturating evidence `mass`, a
    separate `risk` axis, and an explicit `dissent` list.
  - **Tiered scan** — price detectors run broad and cheap; the macro factor set is
    built once per sweep and shared; GARCH is cached on `(ticker, last_data_date)`
    so it refits once a day; one cointegration sweep serves the whole FX basket.
  - **Streaming narration** — `llm_client.chat_stream()` (OpenAI SSE + in-process),
    stance-first prompt so the model's labelled opinion lands before the prose,
    and a number guardrail checking the narrative against supplied evidence.
  - Endpoints: `/api/engine/{feed,asset,narrate,status}`. Measured warm: feed 11 ms,
    per-asset 4.5 ms, off-universe cold 0.9 s (was 3.0 s via `/api/recommendations`).
- **Data freshness fixed** (§6): `END` was hardcoded to `2025-12-31` and caches never
  expired — the dashboard was reasoning over 7-month-old data. Now a rolling end date
  plus an mtime staleness check, with a failed refresh falling back to the stale copy.
- **Cross-seeding root cause found** (§6): `yfinance` is **not thread-safe** — concurrent
  `yf.download()` calls silently return one ticker's data for another. A threaded scan
  reproduced it instantly (META/TSLA, JPM/GLD, ^IXIC/^DJI came back byte-identical).
  Downloads are now serialized behind a lock; cached reads stay parallel.
- **`run_granger_causality` was silently dead**: it passed a `verbose` kwarg removed in
  statsmodels 0.14, and a bare `except` swallowed the `TypeError`, so it always returned
  zero results. Fixed — now returns 32 results (6 significant) on `^GSPC`.
- First tests in the repo: `backend/test_engine.py`, 25 cases over the polarity map,
  fusion invariants, ranking, reliability, stance parsing, and the guardrail.

- **UI now consumes the engine.** The Opportunities tab runs on `/api/engine/*` and
  shows what the engine actually computes instead of a single opaque confidence bar.
  - **Two-tier readout** — every metric gives a plain-English word in the primary
    slot, the exact figure beside it, and the mechanism in the existing `InfoTip`.
    One element serves a beginner and a trader; nothing needed to read the screen
    is hidden behind a click. Plain-English layer lives in `frontend/src/verdict.js`.
  - **Verdict strip** — stance + conviction / direction / risk, replacing the
    retired `0.2 + 0.15·n + 0.3·top` confidence line.
  - **Dissent is visible** — signals opposing the verdict render under "Pushing the
    other way" rather than being averaged into the ranked list.
  - **Drill-down** — a signal's source badge jumps to the pillar tab that produced it.
  - **Explainable narration** — `useNarration.js` over native `EventSource`. The
    model's own stance renders *beside* the computed one (it is allowed to disagree,
    and now that shows), text streams instead of blocking ~20 s, and the
    `unverified_numbers` guardrail surfaces as a grounding badge — "stats detect,
    LLM explains" made visible rather than asserted.
  - **Shared ticker/pairs via Context** (`ticker.js` + `TickerContext.jsx`) — panels
    each held a private `useState("^GSPC")`, so switching tabs reset the asset.
  - **`AbortController` + stale-response guard** in `useApiData` — one fix covering
    all five panels.
  - **Status strip** reads `/api/engine/status`: live / warming / offline. The dot was
    hardcoded green, including when the backend was down.
  - **No new dependencies.** `framer-motion` and `recharts` were already installed and
    `EventSource` is native, so Tailwind v4 / shadcn / bklit / kokonut / anime.js were
    all skipped and the audited `index.css` design system stayed intact.
- **Macro R² resolved** — the ~0.99 readings were an artefact of the corrupted cache.
  Clean data gives `^GSPC` R² ≈ 0.69, META ≈ 0.31. `reliability` is reading sane values.

- **Visual redesign — "measured, not decorated".** The navy/teal identity was
  replaced outright, driven by one rule: *colour means direction; nothing else
  gets to use it.* Bull/bear are the only hues; severity is bar length, source is
  a label, risk is a segmented meter.
  - **Dual theme** — light default (survives a projector), dark follows the OS,
    three-state toggle in the header. All 30 token pairings verified ≥4.5:1 in
    both schemes.
  - **Type** — Archivo (variable, width axis carries the display voice) +
    JetBrains Mono. Five sizes replacing 32 ad-hoc values; two radii.
  - **Tilt gauge** (`common/TiltGauge.jsx`) — one instrument replacing four
    readouts. Marker = balance of evidence, band width = inverse conviction, so
    it reads as a confidence interval.
  - **Signals are a hairline list**, not a card grid — agreeing and dissenting
    rows now share one width and one left axis (they didn't before).
  - **Bento grids** for the Overview and the chart areas, with spans that tile
    exactly at every breakpoint.
  - **Skeletons everywhere** — layout-matched shapes on first load, dim-in-place
    on refetch. The centred spinner is gone.
  - **Tab switching no longer janks**: `useApiData` gained a session cache
    (stale-while-revalidate), and `AnimatePresence mode="wait"` was removed — it
    was forcing a ~240ms empty gap before the incoming panel could mount.
  - **Chart axes** got `minTickGap`/`tickMargin`/explicit label height, and the
    charts grid went from 3-up auto-fit to 2-up bento, which is what the dense
    date and quantile axes actually needed.
  - Zero new dependencies. kokonut/bklit informed the hairline and bento
    discipline; framer-motion and recharts already covered motion and charts.
  - impeccable detector: 8 findings → **0**.
- **Wrap-up bug sweep.**
  - `python main.py` was broken — `uvicorn.run()` got the app object while
    `reload=True` demands an import string, so it exited immediately. Two places
    in the UI told users to run exactly that command; both now match reality.
  - An unknown ticker returned **500** quoting an internal cache key
    (`Download returned empty data for 'equity_ZZZNOTREAL'`). `data_loader` now
    raises `NoDataError` and the API answers **404** with a readable message —
    one handler covers every endpoint, since all data access routes through
    `_load_or_download`. `api.js` reads the server's message instead of
    discarding it for "API error 404: Not Found".
  - "Top Return Drivers" coloured positive betas with a *neutral ink* step while
    negatives got bear red, so the sign was only half-encoded. Both sides now use
    the direction pair.
  - The QQ scatter and its reference diagonal were adjacent ramp steps — the line
    the points are meant to deviate from was hard to pick out.
  - `npm run lint` had been failing before this work; now clean. The one error
    was the rule reporting its own inability to verify a generic hook's deps,
    documented in place rather than restructured around.
  - Dead CSS (`.chart-full`, `.chart-third`, `.bento-cell.full`) removed.
- **`.gitignore` hardened.** Two classes of tooling state were ignored only by
  *machine-local* files that never get committed — so they worked for one
  developer and would have shown up as untracked for anyone else cloning:
  - `.claude/` — covered only by a global gitignore
  - `.impeccable/` and `frontend/.impeccable/` (design-hook caches) — covered
    only by `.git/info/exclude`
  Both now live in the repo's own `.gitignore`, alongside `.remember/` and the
  other AI/editor tool dirs. Also added `.playwright-mcp/`, root-anchored
  screenshot patterns (so `src/assets/hero.png` survives), model weights, and
  `backend/data/raw/*` with a `.gitkeep` exception so the folder still exists.
  Verified: **62 files would be committed, all project code/docs**, and nothing
  already tracked became ignored.

### Still open (next)
- **Statistical rigor — the biggest remaining gap.** The detectors are built but their
  inferential claims are unvalidated:
  - `pairs.py` runs C(n,2) cointegration tests (990 for 45 pairs), counts `p<0.05` as
    cointegrated, and reports the *minimum* p-value across all of them as if it were a
    single test. ~50 false positives are expected by chance. Needs BH-FDR
    (`statsmodels.stats.multitest.multipletests`) — one import, and it feeds
    `engine._reliability`, which currently trusts that selection-biased p-value.
  - `macro_regression.py` needs HAC/Newey-West errors (`.fit(cov_type="HAC",
    cov_kwds={"maxlags": 4})`) — monthly residuals are autocorrelated and lags 0–3 of
    the same factor are collinear, so the p-values are overstated.
  - `data_loader.build_macro_dataset` feeds `Treasury10Y`, `FedFunds` and
    `Unemployment` in as **levels** against a stationary return target — `.diff()` them.
  - GARCH is described (AIC/BIC/persistence) but never forecast. A rolling 1-step-ahead
    99% VaR + Kupiec test would validate it.
  - `pairs.get_best_pair_analysis` fits the hedge ratio and rolling z on the full
    sample, then generates signals over that same sample — look-ahead bias.
  When these land, q-values and VaR-breach rates display through the existing
  `LabelWithTip` next to the current p-value readouts.
- Wire `black_scholes.analyze_option` into the engine as a vol-mispricing detector
  (its `vol_verdict` is computed but nothing consumes it).
- `/api/recommendations` is now unused by the UI — safe to delete from `main.py`.
- To start the GPU server: run llama-server.exe with `-ngl 99 --port 8080` (see
  `llm_client.py` header). Currently falling back to the in-process CPU path
  (~5.7 s per narration vs an expected ~2 s on GPU).
