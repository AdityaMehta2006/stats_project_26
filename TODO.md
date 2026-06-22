# QuantAnomalies — Roadmap / TODO

Forward-looking plan. Items tagged **P0** (next), **P1** (soon), **P2** (later).
Done items are at the bottom.

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

## 1. Recommendation / Anomaly–Opportunity Engine (headline) — P0

### 1a. Detectors (rules over existing pillar outputs — deterministic, free)
New module `backend/analysis/recommender.py`. Each detector emits a structured
signal `{type, asset, direction, severity 0–1, evidence:{metric:value}, asof}`:
- [ ] **Volatility regime** — current GARCH conditional σ vs its trailing
      percentile → "elevated / compressed vol". Flag vol-of-vol spikes.
- [ ] **Tail event** — latest return's size in GARCH-σ units (|z|) combined with
      high excess kurtosis → "outsized move / fat-tail day".
- [ ] **Pairs opportunity** — cointegrated pair (p<0.05) with |z|>2 → actionable
      mean-reversion entry; z crossing back through ±2 → exit. Rank by |z| and
      short half-life.
- [ ] **Macro dislocation** — large OLS residual: asset moving against what macro
      factors predict; flag any factor at an extreme historical percentile.
- [ ] **Relative / cross-section** — across the toggled assets, rank who is most
      extreme today (vol, |residual|, momentum) → relative opportunity.
- [ ] **Trend / breakout** (simple, new) — price vs rolling mean, new N-day high/low.
- [ ] Rank all signals by severity; produce an overall 0–1 confidence from how
      many detectors agree.

### 1b. LLM explainer (local model — Gemma 4 / Qwen3-4B)
- [ ] Send the ranked detections JSON to the model; ask for: a one-line market
      read, then per-opportunity a 1–2 sentence explanation + recommendation
      (watch / consider long / consider short / reduce risk), citing the evidence.
- [ ] **Provider-agnostic client**: config via env `LLM_BASE_URL`, `LLM_MODEL`,
      `LLM_API_KEY` (optional). Default to the local llama.cpp server (§2);
      Anthropic Claude (`claude-opus-4-8`) is a drop-in alternative by changing
      the base URL/key.
- [ ] Guardrails: instruct the model to use only provided numbers; validate the
      response references real metrics before display. Rules-based summary is the
      fallback when the LLM is unavailable.

### 1c. API + Frontend
- [ ] Endpoint `GET /api/recommendations?tickers=&pairs=` returning ranked signals
      + (optional) LLM narrative.
- [ ] New **"Opportunities"** tab: ranked cards (severity meter, direction badge,
      cited evidence, LLM explanation), with a rules-vs-LLM toggle and a
      per-pillar drill-down link.

---

## 2. Local LLM runtime setup — P0 (prerequisite for 1b)

Environment is ready: the Anaconda backend env already has `llama_cpp_python`,
GGUF models exist at `E:\odysseus\data\models`, GPU is an RTX 4050 (6 GB).
- [ ] Run as an **OpenAI-compatible sidecar** (decoupled, restartable):
      `python -m llama_cpp.server --model "E:\odysseus\data\models\gemma-4-E2B-it-Q4_K_M.gguf" --n_gpu_layers -1 --n_ctx 4096 --port 8080`
- [ ] Backend calls `http://localhost:8080/v1/chat/completions` (httpx/openai client).
- [ ] Try both models: **Gemma 4 E2B** (fast) and **Qwen3-4B-Instruct** (usually
      better at JSON/structured analysis) — make the model swappable via `LLM_MODEL`.
- [ ] Confirm the installed `llama_cpp_python` is a CUDA build (GPU offload); if
      CPU-only it still works for short notes (~5–15 tok/s) but rebuild for speed.
- [ ] A tiny "is the LLM up?" health probe so the UI can fall back to rules cleanly.

---

## 3. Proper scaling & normalization (makes signals meaningful) — P0

Prerequisite for trustworthy anomaly detection — comparable units matter.
- [ ] **Standardize macro factors (z-score) before OLS** → comparable
      standardized betas; the dominant driver feeds detector 1a (macro dislocation).
- [ ] **Normalize forex prices (log / index-to-100) before spread + hedge ratio**
      so the hedge ratio stops collapsing to ~−0.002 and z-scores are comparable
      across pairs (feeds the pairs detector).
- [ ] **VIX as change/log-level** for stationarity in the regression; document it.
- [ ] **Consistent display units** (%, scientific-notation tiny p-values, fixed
      decimals) via a shared `formatNumber` helper.

---

## 4. Charts: time filter, scaling, asset toggle, news-on-click — P1
*(includes your three new requests)*

- [ ] **Time-range filter** on every chart (1M / 3M / 6M / 1Y / 5Y / All) with the
      y-axis **autoscaling** to the visible window so moves are readable.
- [ ] **Toggle between assets** — shared ticker selection across all tabs, plus a
      compare mode to overlay/compare 2–3 assets at once.
- [ ] **News on chart click** — clicking a point opens that date's headlines for
      the ticker; the LLM can then correlate the move with the news ("the −4% day
      coincided with …"). Data source options (no/low cost): **GDELT Doc API**
      (free, historical, no key — best fit), Yahoo Finance news (recent only),
      or NewsAPI/Marketaux (key, limited free tier). Cache responses.

---

## 5. UI polish — P1

- [ ] Loading **skeletons** per card instead of one full-panel spinner.
- [ ] Axis **unit labels** and better tick formatting everywhere.
- [ ] Empty / partial states (skipped factor, no signals, LLM offline).
- [ ] "Data as of <date>" freshness indicator + manual **refresh data** button
      that busts the CSV cache for the current ticker.
- [ ] Light-mode variant reusing the `theme.js` tokens.
- [ ] Mobile pass on tables and heatmaps.

---

## 6. Data & robustness — P1

- [ ] **Cache integrity guard** — the originals were cross-seeded (VIX held S&P,
      oil held VIX). Sanity-check a cached series' range/ticker on load and
      auto-refetch on mismatch.
- [ ] **Metadata sidecar** per cache (ticker, fetch date, row count) for staleness.
- [ ] Timeout-wrap the `pandas_datareader` FRED fallback (it can hang).
- [ ] Unit tests for `data_loader` + a pytest smoke suite over every endpoint.
- [ ] README: pin deps; document the Anaconda interpreter requirement (`python`
      on this machine is the broken Store stub) and the local-LLM sidecar.

---

## 7. Options pricing — Black–Scholes — P1

Adds an options layer that ties directly into the volatility pillar and feeds the recommender.
- [ ] New module `backend/analysis/black_scholes.py`:
  - Black–Scholes–Merton price for European calls/puts:
    `C = S·N(d1) − K·e^(−rT)·N(d2)`,  `P = K·e^(−rT)·N(−d2) − S·N(−d1)`,
    with `d1 = [ln(S/K) + (r + σ²/2)T] / (σ√T)` and `d2 = d1 − σ√T`.
  - Greeks: delta, gamma, vega, theta, rho.
  - Implied-volatility solver (Newton / bisection) from a market option price.
- [ ] Inputs: spot from the ticker, `r` from the 10Y (or Fed Funds), `σ` from the
      GARCH forecast or user input; live option chains via yfinance `Ticker.option_chain`.
- [ ] **Vol-mispricing detector** for the recommender (§1a): market implied vol vs
      GARCH-forecast vol → "options rich / cheap vs model" opportunity signal.
- [ ] Endpoint `GET /api/options/black-scholes?ticker=&strike=&expiry=` + a UI card
      (price, Greeks, implied-vol-vs-GARCH gauge).

---

## 8. Analysis depth — P2

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

### Still open from §1/§2 (next)
- Detectors: macro dislocation (needs standardized betas, §3), relative cross-section, breakout.
- To start the GPU server: run llama-server.exe with `-ngl 99 --port 8080` (see `llm_client.py` header).
