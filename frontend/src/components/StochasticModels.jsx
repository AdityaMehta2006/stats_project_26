/**
 * StochasticModels.jsx
 * --------------------
 * Pillar 5: Stochastic processes — the mathematical substrate under the whole project.
 *
 * The tab is deliberately ordered as an argument rather than a feature list:
 *   1. Brownian motion, and the identity dW² = dt that makes stochastic calculus
 *      different from ordinary calculus.
 *   2. GBM, and the Itô correction −σ²/2 that most derivations drop.
 *   3. Ornstein-Uhlenbeck — the process the pair-trading pillar actually assumes,
 *      fitted to the live spread so the half-life on the Pairs tab is derived
 *      rather than asserted.
 *   4. CIR and Heston, showing why the discretisation scheme matters.
 *   5. Numerical method quality: Euler vs Milstein, and variance reduction.
 */

import { useState, useMemo, useCallback } from "react";
import { motion } from "framer-motion";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Legend, ReferenceLine, BarChart, Bar, Cell,
} from "recharts";
import useApiData from "../hooks/useApiData";
import {
  getStochasticPaths, getSchemeConvergence, getVarianceReduction, getOuFit,
} from "../api";
import { LoadingState, ErrorState } from "./common/StatusStates";
import ParamControls from "./common/ParamControls";
import Icon from "./common/Icon";
import { InfoTip, LabelWithTip } from "./common/Tooltip";
import { CHART, SERIES, tooltipStyle, tooltipLabelStyle, tooltipItemStyle } from "../theme";
import { fmtNum } from "../utils/format";

const container = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const item = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

const PROCESSES = [
  {
    id: "wiener", label: "Brownian Motion", icon: "activity",
    title: "Wiener Process — the noise that drives everything",
    sde: "dW ~ Normal(0, dt)",
    blurb: (
      <>
        Standard Brownian motion is the raw randomness every other model is built from.
        Increments are independent and normal with variance equal to the elapsed time, so
        the path is continuous but <strong>nowhere differentiable</strong> — you cannot
        speak of its velocity. That is precisely why ordinary calculus fails and
        Itô's lemma is needed. The key diagnostic below is{" "}
        <strong>quadratic variation</strong>: the sum of squared increments converges to
        T, which is the identity <strong>dW² = dt</strong>, the engine of all stochastic
        calculus.
      </>
    ),
  },
  {
    id: "gbm", label: "GBM", icon: "trendingUp",
    title: "Geometric Brownian Motion — the Black-Scholes underlying",
    sde: "dS = μ S dt + σ S dW",
    blurb: (
      <>
        Returns, not prices, are modelled as random — so prices stay positive and move
        proportionally. Applying Itô's lemma to ln S gives the exact solution{" "}
        <strong>S_t = S₀ exp((μ − σ²/2)t + σW_t)</strong>. Note the{" "}
        <strong>−σ²/2</strong>: this is the Itô correction, and it is the single most
        commonly dropped term in student derivations. It is why the{" "}
        <strong>median</strong> of the terminal price sits below its <strong>mean</strong>,
        and the gap widens with volatility.
      </>
    ),
  },
  {
    id: "ou", label: "Ornstein-Uhlenbeck", icon: "exchange",
    title: "Ornstein-Uhlenbeck — the mathematics of pair trading",
    sde: "dX = κ(θ − X) dt + σ dW",
    blurb: (
      <>
        Read the drift literally: whenever X is above θ the drift is negative and pulls it
        back down. <strong>κ</strong> is the strength of that pull, and{" "}
        <strong>half-life = ln(2)/κ</strong>. This is exactly the process the Pairs tab
        assumes for its spread. Crucially, OU has a <strong>stationary distribution</strong>{" "}
        with finite variance σ²/(2κ) — which is what makes a spread z-score meaningful at
        all. A random walk has no such anchor, so standardising it would be meaningless.
      </>
    ),
  },
  {
    id: "cir", label: "CIR", icon: "layers",
    title: "Cox-Ingersoll-Ross — the variance process inside Heston",
    sde: "dv = κ(θ − v) dt + ξ√v dW",
    blurb: (
      <>
        Mean-reverting like OU, but the <strong>√v</strong> diffusion shrinks the noise as
        v approaches zero, which keeps variance non-negative — provided the{" "}
        <strong>Feller condition 2κθ ≥ ξ²</strong> holds. Discretisation is the whole
        difficulty: naive Euler can step v below zero, and then √v is undefined. We use{" "}
        <strong>full truncation</strong> (Lord et al. 2010), the lowest-bias standard fix.
      </>
    ),
  },
  {
    id: "merton", label: "Jump-Diffusion", icon: "alert",
    title: "Merton Jump-Diffusion — modelling crashes",
    sde: "dS/S = (μ − λk) dt + σ dW + (Y−1) dN",
    blurb: (
      <>
        Adds a Poisson jump process on top of the diffusion: rare, large,
        discontinuous moves. The <strong>−λk compensator</strong> keeps the expected
        return unchanged, so jumps alter the <em>shape</em> of the distribution without
        moving its mean. With a negative mean jump size this generates the negative skew
        and excess kurtosis the GARCH tab measures empirically (about 16 on the S&amp;P
        500) — which pure GBM cannot produce at <em>any</em> volatility.
      </>
    ),
  },
  {
    id: "heston", label: "Heston", icon: "options",
    title: "Heston — stochastic volatility",
    sde: "dS = rS dt + √v S dW₁ ,  dv = κ(θ−v) dt + ξ√v dW₂",
    blurb: (
      <>
        Two coupled SDEs: volatility is itself a random (CIR) process rather than a
        constant. That is what produces a <strong>volatility smile</strong>, which
        Black-Scholes structurally cannot. The correlation{" "}
        <strong>ρ ≈ −0.7</strong> encodes the <strong>leverage effect</strong> — prices
        down, volatility up — and it is what tilts the smile into the downward skew seen
        in real index options.
      </>
    ),
  },
];

const DEFAULTS = {
  s0: 100, mu: 0.05, sigma: 0.2, kappa: 2.0, theta: 0,
  rho: -0.7, t_years: 1.0, steps: 252, paths: 6,
};

function fieldsFor(processId) {
  const common = [
    { key: "t_years", label: "Horizon T", min: 0.02, max: 20, step: 0.25, hint: "years",
      tip: "Length of the simulated time interval." },
    { key: "steps", label: "Steps", min: 10, max: 2000, step: 10,
      tip: "Number of discrete time steps. Finer steps resolve the path better; for exactly-solvable processes it does not change accuracy, only resolution." },
    { key: "paths", label: "Paths", min: 1, max: 40, step: 1,
      tip: "How many independent sample paths to draw." },
  ];
  if (processId === "wiener") return common;

  if (processId === "ou") {
    return [
      { key: "s0", label: "Start X₀", step: 0.5,
        tip: "Initial value of the process." },
      { key: "theta", label: "Mean θ", step: 0.5,
        tip: "The long-run level the process is pulled toward." },
      { key: "kappa", label: "Speed κ", min: 0.01, max: 30, step: 0.1,
        tip: "Mean-reversion speed. Half-life = ln(2)/κ, so larger κ means faster snap-back." },
      { key: "sigma", label: "Noise σ", min: 0.001, max: 5, step: 0.05,
        tip: "Diffusion size. Together with κ it sets the stationary variance σ²/(2κ)." },
      ...common,
    ];
  }
  if (processId === "cir") {
    return [
      { key: "sigma", label: "Vol-of-vol ξ", min: 0.01, max: 2, step: 0.02,
        tip: "Volatility of the variance process. Raise it far enough and the Feller condition breaks, letting variance reach zero." },
      { key: "theta", label: "Long-run θ", min: 0.0001, max: 1, step: 0.005,
        tip: "Long-run variance level. 0.04 corresponds to 20% annualised volatility." },
      { key: "kappa", label: "Speed κ", min: 0.01, max: 30, step: 0.1,
        tip: "How fast variance reverts to θ." },
      ...common,
    ];
  }
  if (processId === "heston") {
    return [
      { key: "s0", label: "Spot S₀", min: 0.01, step: 1, tip: "Initial asset price." },
      { key: "mu", label: "Rate r", min: -0.1, max: 1, step: 0.005,
        tip: "Risk-free drift under the pricing measure." },
      { key: "sigma", label: "Init vol σ", min: 0.01, max: 3, step: 0.01,
        tip: "Initial volatility; v₀ = σ². Vol-of-vol is derived from this." },
      { key: "theta", label: "Long-run θ", min: 0, max: 1, step: 0.005,
        tip: "Long-run variance. Leave at 0 to reuse v₀." },
      { key: "kappa", label: "Speed κ", min: 0.01, max: 30, step: 0.1,
        tip: "Variance mean-reversion speed." },
      { key: "rho", label: "Corr ρ", min: -0.99, max: 0.99, step: 0.05,
        tip: "Correlation between price and volatility shocks. Negative is the leverage effect." },
      ...common,
    ];
  }
  // gbm, merton
  return [
    { key: "s0", label: "Spot S₀", min: 0.01, step: 1, tip: "Initial asset price." },
    { key: "mu", label: "Drift μ", min: -1, max: 1, step: 0.01,
      tip: "Expected continuously-compounded return per year." },
    { key: "sigma", label: "Vol σ", min: 0.001, max: 3, step: 0.01,
      tip: "Annualised volatility of the diffusion component." },
    ...common,
  ];
}

export default function StochasticModels() {
  const [processId, setProcessId] = useState("gbm");
  const [params, setParams] = useState(DEFAULTS);
  const [seed, setSeed] = useState(42);

  const proc = PROCESSES.find((p) => p.id === processId);
  const fields = useMemo(() => fieldsFor(processId), [processId]);

  const key = JSON.stringify({ processId, params, seed });
  const paths = useApiData(() => getStochasticPaths(processId, { ...params, seed }), [key]);
  const ou = useApiData(() => getOuFit(), []);

  const reset = useCallback(() => setParams(DEFAULTS), []);

  return (
    <motion.div variants={container} initial="hidden" animate="show">
      <motion.div className="section-header" variants={item}>
        <div className="section-ico stochastic"><Icon name="stochastic" size={23} /></div>
        <div>
          <h2>Stochastic Processes</h2>
          <p>The differential equations underneath every model in this project</p>
        </div>
      </motion.div>

      <motion.div className="section-intro" variants={item}>
        <span className="intro-ico"><Icon name="info" size={18} /></span>
        <span>
          Every model here is a <strong>stochastic differential equation</strong>:
          a predictable <strong>drift</strong> plus random <strong>diffusion</strong> driven
          by Brownian motion. Because Brownian paths are nowhere differentiable, ordinary
          calculus does not apply — you need <strong>Itô's lemma</strong>, whose whole content
          is that <strong>dW² = dt</strong> rather than zero. These processes are not
          decoration: GBM is what Black-Scholes assumes, and{" "}
          <strong>Ornstein-Uhlenbeck</strong> is what the pair-trading strategy assumes.
        </span>
      </motion.div>

      {/* Process selector */}
      <motion.div variants={item} className="toolbar-card" style={{ flexDirection: "column", alignItems: "stretch" }}>
        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
          {PROCESSES.map((p) => (
            <button
              key={p.id}
              className="param-reset"
              onClick={() => setProcessId(p.id)}
              style={
                processId === p.id
                  ? { background: "var(--accent-primary-dim)", borderColor: "var(--accent-primary)", color: "var(--accent-primary)" }
                  : undefined
              }
            >
              <Icon name={p.icon} size={13} /> {p.label}
            </button>
          ))}
        </div>
      </motion.div>

      {/* Explanation of the selected process */}
      <motion.div className="card" variants={item} style={{ marginBottom: "1.25rem" }}>
        <div className="card-header">
          <div>
            <div className="card-title">{proc.title}</div>
            <div className="card-subtitle mono" style={{ fontFamily: "var(--font-mono)", color: "var(--accent-primary)" }}>
              {proc.sde}
            </div>
          </div>
        </div>
        <div style={{ fontSize: "0.88rem", lineHeight: 1.7, color: "var(--text-secondary)" }}>
          {proc.blurb}
        </div>
      </motion.div>

      {/* Parameters */}
      <motion.div className="card" variants={item} style={{ marginBottom: "1.25rem" }}>
        <div className="card-header">
          <div>
            <div className="card-title">
              Parameters
              <InfoTip text="Hover any label to learn what the parameter controls. The seed makes a run reproducible — same seed, same paths." />
            </div>
            <div className="card-subtitle">Press Enter or click away to apply</div>
          </div>
          <button className="param-reset" onClick={() => setSeed((s) => s + 1)}>
            <Icon name="refresh" size={13} /> New random draw
          </button>
        </div>
        <ParamControls fields={fields} values={params} onChange={setParams} onReset={reset} />
      </motion.div>

      {paths.loading && <LoadingState message={`Simulating ${proc.label}…`} subtext="Generating sample paths" />}
      {paths.error && !paths.loading && <ErrorState message={paths.error} onRetry={paths.reload} />}

      {!paths.loading && !paths.error && paths.data && (
        <div className="charts-grid">
          <motion.div className="card" variants={item} style={{ gridColumn: "1 / -1" }}>
            <div className="card-header">
              <div>
                <div className="card-title">
                  Sample Paths
                  <InfoTip text="Independent realisations of the same SDE. The spread between them is the model's uncertainty; the shape of that spread is what distinguishes one process from another." />
                </div>
                <div className="card-subtitle">
                  {params.paths} paths · {params.steps} steps · T = {params.t_years}y · seed {seed}
                </div>
              </div>
            </div>
            <PathChart data={paths.data} processId={processId} theta={params.theta} />
          </motion.div>

          {/* Theory vs empirical */}
          <motion.div className="card" variants={item}>
            <div className="card-header">
              <div>
                <div className="card-title">
                  Theory vs Simulation
                  <InfoTip text="Closed-form moments of the process next to the ones measured from the simulated paths. Close agreement means the simulator is implementing the mathematics correctly — this is the module's self-test." />
                </div>
                <div className="card-subtitle">Analytical results checked against the sample</div>
              </div>
            </div>
            <TheoryTable theory={paths.data.theory} />
            {paths.data.note && (
              <div className="card-note" style={{ marginTop: "0.7rem" }}>{paths.data.note}</div>
            )}
          </motion.div>

          {/* Volatility paths for Heston/CIR */}
          {paths.data.vol_paths && (
            <motion.div className="card" variants={item}>
              <div className="card-header">
                <div>
                  <div className="card-title">
                    Volatility Paths
                    <InfoTip text="The volatility process itself, plotted separately. In Black-Scholes this would be a flat horizontal line — the fact that it wanders is exactly what generates the volatility smile." />
                  </div>
                  <div className="card-subtitle">Annualised volatility %, mean-reverting</div>
                </div>
              </div>
              <VolPathChart data={paths.data} />
            </motion.div>
          )}

          {/* OU fitted to the live spread — the bridge to Pillar 3 */}
          {processId === "ou" && (
            <motion.div className="card" variants={item} style={{ gridColumn: "1 / -1" }}>
              <div className="card-header">
                <div>
                  <div className="card-title">
                    Fitted to the Live Pair-Trading Spread
                    <InfoTip text="This is the bridge between the maths and Pillar 3. Discretising the OU SDE produces exactly the AR(1) regression the pairs module runs, so the half-life reported on the Pairs tab is this κ in disguise. Fitting it independently here confirms the two derivations agree." />
                  </div>
                  <div className="card-subtitle">
                    The pairs strategy assumes the spread is Ornstein-Uhlenbeck — here is the estimate
                  </div>
                </div>
              </div>
              {ou.loading && <LoadingState message="Fitting OU to the spread…" subtext="Cointegration then AR(1) estimation" />}
              {ou.error && !ou.loading && <ErrorState message={ou.error} onRetry={ou.reload} />}
              {ou.data?.ou_fit && <OuFitPanel data={ou.data} />}
            </motion.div>
          )}

          <NumericalMethods />
        </div>
      )}
    </motion.div>
  );
}

/* ==========================================================================
   Charts
   ========================================================================== */

function PathChart({ data, processId, theta }) {
  const rows = useMemo(() => {
    const times = data.times || [];
    const paths = data.paths || [];
    // Downsample long series so Recharts stays responsive.
    const stride = Math.max(1, Math.floor(times.length / 400));
    const out = [];
    for (let i = 0; i < times.length; i += stride) {
      const row = { t: times[i] };
      paths.forEach((p, j) => { row[`p${j}`] = p[i]; });
      out.push(row);
    }
    return out;
  }, [data]);

  const n = (data.paths || []).length;
  const isOu = processId === "ou";
  const isCir = processId === "cir";

  return (
    <div className="chart-container tall">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
          <XAxis dataKey="t" stroke={CHART.axis} tick={{ fontSize: 11 }}
            tickFormatter={(v) => Number(v).toFixed(2)}
            label={{ value: "time (years)", position: "insideBottom", offset: -4, fill: CHART.axis, fontSize: 10 }} />
          <YAxis stroke={CHART.axis} tick={{ fontSize: 11 }}
            tickFormatter={(v) => (Math.abs(v) < 0.01 && v !== 0 ? v.toExponential(1) : Number(v).toFixed(2))} />
          <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle}
            labelFormatter={(v) => `t = ${Number(v).toFixed(3)}y`} />
          {isOu && (
            <ReferenceLine y={theta ?? 0} stroke={CHART.gold} strokeDasharray="5 5"
              label={{ value: "θ (mean)", fill: CHART.gold, fontSize: 10, position: "right" }} />
          )}
          {isCir && (
            <ReferenceLine y={0} stroke={CHART.down} strokeDasharray="5 5"
              label={{ value: "zero floor", fill: CHART.down, fontSize: 10, position: "right" }} />
          )}
          {Array.from({ length: n }).map((_, j) => (
            <Line key={j} type="monotone" dataKey={`p${j}`} stroke={SERIES[j % SERIES.length]}
              strokeWidth={1.3} dot={false} name={`path ${j + 1}`} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function VolPathChart({ data }) {
  const rows = useMemo(() => {
    const times = data.times || [];
    const vp = data.vol_paths || [];
    const stride = Math.max(1, Math.floor(times.length / 300));
    const out = [];
    for (let i = 0; i < times.length; i += stride) {
      const row = { t: times[i] };
      vp.forEach((p, j) => { row[`v${j}`] = p[i]; });
      out.push(row);
    }
    return out;
  }, [data]);

  const n = (data.vol_paths || []).length;
  const longRun = data.theory?.long_run_vol_pct;

  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
          <XAxis dataKey="t" stroke={CHART.axis} tick={{ fontSize: 11 }}
            tickFormatter={(v) => Number(v).toFixed(2)} />
          <YAxis stroke={CHART.axis} tick={{ fontSize: 11 }}
            label={{ value: "vol %", angle: -90, position: "insideLeft", fill: CHART.axis, fontSize: 10 }} />
          <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle}
            formatter={(v) => [`${Number(v).toFixed(2)}%`, "vol"]}
            labelFormatter={(v) => `t = ${Number(v).toFixed(3)}y`} />
          {longRun && (
            <ReferenceLine y={longRun} stroke={CHART.gold} strokeDasharray="5 5"
              label={{ value: "√θ long-run", fill: CHART.gold, fontSize: 10, position: "right" }} />
          )}
          {Array.from({ length: n }).map((_, j) => (
            <Line key={j} type="monotone" dataKey={`v${j}`} stroke={SERIES[j % SERIES.length]}
              strokeWidth={1.3} dot={false} isAnimationActive={false} name={`path ${j + 1}`} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

const THEORY_LABELS = {
  solution: "Exact solution",
  ito_correction: "Itô correction (−σ²/2)",
  sde: "SDE",
  mean_theoretical: "Mean (theory)",
  variance_theoretical_at_T: "Var at T (theory)",
  variance_empirical_at_T: "Var at T (simulated)",
  quadratic_variation_theoretical: "Quadratic variation (theory = T)",
  quadratic_variation_empirical: "Quadratic variation (simulated)",
  mean_theoretical_at_T: "Mean at T (theory)",
  mean_empirical_at_T: "Mean at T (simulated)",
  median_theoretical_at_T: "Median at T (theory)",
  std_theoretical_at_T: "Std at T (theory)",
  std_empirical_at_T: "Std at T (simulated)",
  half_life_time_units: "Half-life = ln(2)/κ",
  stationary_mean: "Stationary mean",
  stationary_variance: "Stationary variance σ²/(2κ)",
  stationary_std: "Stationary std",
  empirical_terminal_mean: "Terminal mean (simulated)",
  empirical_terminal_std: "Terminal std (simulated)",
  feller_condition: "Feller condition",
  feller_lhs: "2κθ",
  feller_rhs: "ξ²",
  feller_satisfied: "Feller satisfied",
  negative_excursions: "Negative variance steps",
  expected_jump_size_k: "Expected jump size k",
  compensator_drift_adjustment: "Compensator (−λk)",
  expected_num_jumps: "Expected jumps (λT)",
  log_return_skew: "Log-return skew",
  log_return_excess_kurtosis: "Log-return excess kurtosis",
  correlation_rho: "Correlation ρ",
  leverage_effect: "Leverage effect",
  long_run_vol_pct: "Long-run vol %",
  initial_vol_pct: "Initial vol %",
  vol_half_life: "Vol half-life",
  scheme: "Discretisation scheme",
  asset_sde: "Asset SDE",
  variance_sde: "Variance SDE",
  kappa: "κ", theta: "θ",
};

const THEORY_TIPS = {
  ito_correction: "The −σ²/2 term in the exponent. Ordinary calculus would omit it; Itô's lemma requires it because ln is concave and dW² = dt is not negligible.",
  quadratic_variation_empirical: "Sum of squared Brownian increments. It converges to T, which IS the identity dW² = dt — the foundation of stochastic calculus.",
  median_theoretical_at_T: "Always below the mean for GBM. The gap is the Itô correction, and it widens with volatility.",
  stationary_variance: "σ²/(2κ). A finite stationary variance is exactly what makes a spread z-score meaningful — a random walk has none.",
  half_life_time_units: "Time for a deviation to decay halfway back to the mean. This is the number the Pairs tab reports.",
  feller_condition: "2κθ ≥ ξ². When satisfied the variance process never reaches zero in continuous time.",
  log_return_excess_kurtosis: "Fat tails. GBM gives exactly 0; jumps and stochastic volatility produce positive values, matching what GARCH measures on real returns.",
  log_return_skew: "Asymmetry. Negative jump means and negative ρ both produce negative skew, as observed in equity markets.",
  compensator_drift_adjustment: "−λk. Keeps E[S_T] unchanged when jumps are added, so jumps alter distribution shape without shifting the mean.",
};

function TheoryTable({ theory }) {
  if (!theory) return null;
  const entries = Object.entries(theory).filter(([, v]) => v !== null && v !== undefined);
  return (
    <div className="model-rows">
      {entries.map(([k, v]) => {
        const label = THEORY_LABELS[k] || k.replace(/_/g, " ");
        const tip = THEORY_TIPS[k];
        const isBool = typeof v === "boolean";
        const isLong = typeof v === "string" && v.length > 26;
        return (
          <div className="model-row" key={k}
            style={isLong ? { gridTemplateColumns: "1fr" } : undefined}>
            <div>
              <div className="model-row-name">
                {tip ? <LabelWithTip tip={tip}>{label}</LabelWithTip> : label}
              </div>
              {isLong && (
                <div className="model-row-sub" style={{ marginTop: 4, whiteSpace: "normal", lineHeight: 1.5 }}>
                  {v}
                </div>
              )}
            </div>
            {!isLong && (
              <>
                <div className="model-row-value"
                  style={isBool ? { color: v ? "var(--accent-success)" : "var(--accent-danger)" } : undefined}>
                  {isBool ? (v ? "yes" : "no") : typeof v === "number" ? fmtNum(v, 6).replace(/0+$/, "").replace(/\.$/, "") : v}
                </div>
                <div className="model-row-err" />
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}

function OuFitPanel({ data }) {
  const f = data.ou_fit;
  if (f.error) return <div style={{ color: "var(--text-muted)" }}>{f.error}</div>;
  if (!f.mean_reverting) {
    return (
      <div style={{ padding: "1rem 0.5rem" }}>
        <div className="check-row fail">
          <span className="check-ico"><Icon name="alert" size={15} /></span>
          Spread is not mean-reverting
          <span className="check-detail">AR(1) slope {f.ar1_slope}</span>
        </div>
        <div className="card-note" style={{ marginTop: "0.7rem" }}>{f.note}</div>
      </div>
    );
  }
  return (
    <>
      <div className="stats-grid">
        <StatBox value={data.pair} label="Pair" highlight
          tip="The most cointegrated pair in the selection — the one the strategy trades." />
        <StatBox value={f.kappa} label="κ (speed)"
          tip="Mean-reversion speed, estimated as −ln(b)/dt where b is the AR(1) slope." />
        <StatBox value={fmtNum(f.theta, 5)} label="θ (mean)"
          tip="Long-run level of the spread, estimated as a/(1−b)." />
        <StatBox value={f.half_life} label="OU Half-Life (d)" highlight
          tip="ln(2)/κ, in days. Directly comparable with the figure on the Pairs tab." />
        <StatBox value={data.pairs_module_half_life_days} label="Pairs Tab Half-Life"
          tip="Computed independently by the pairs module from an AR(1) regression in differences. The two should agree." />
        <StatBox value={f.ar1_slope} label="AR(1) Slope b"
          tip="Must lie strictly between 0 and 1 for mean reversion. b ≥ 1 means a random walk and no finite half-life." />
      </div>
      <div style={{ marginTop: "0.9rem" }}>
        <CheckRow ok={f.mean_reverting} label="Spread is mean-reverting (0 < b < 1)"
          detail={`b = ${f.ar1_slope}`}
          tip="The necessary condition for the whole pair-trading strategy to make sense." />
        <CheckRow ok={data.coint_pvalue != null && data.coint_pvalue < 0.05}
          label="Cointegrated (Engle-Granger p < 0.05)"
          detail={`p = ${data.coint_pvalue}`}
          tip="Confirms a stable long-run relationship, which is what justifies expecting the spread to revert." />
      </div>
      <div className="card-note" style={{ marginTop: "0.7rem" }}>{data.note}</div>
    </>
  );
}

/* ==========================================================================
   Numerical methods — scheme convergence and variance reduction
   ========================================================================== */

function NumericalMethods() {
  const scheme = useApiData(() => getSchemeConvergence(), []);
  const vr = useApiData(() => getVarianceReduction(), []);

  return (
    <>
      <motion.div className="card" variants={item} style={{ gridColumn: "1 / -1" }}>
        <div className="card-header">
          <div>
            <div className="card-title">
              Discretisation Schemes — Euler vs Milstein
              <InfoTip text="Most SDEs have no exact solution, so they must be stepped numerically, and the scheme determines the error. Milstein adds the Itô-Taylor term 0.5·b·b'·(dW² − dt), lifting strong convergence from order 0.5 to order 1.0. Both are compared against GBM's exact solution on identical random draws, so what you see is discretisation error, not Monte Carlo noise." />
            </div>
            <div className="card-subtitle">
              Error against the exact GBM solution as the step size shrinks
            </div>
          </div>
        </div>
        {scheme.loading && <LoadingState message="Running convergence study…" subtext="Multiple step counts, shared random draws" />}
        {scheme.error && !scheme.loading && <ErrorState message={scheme.error} onRetry={scheme.reload} />}
        {scheme.data?.convergence && (
          <>
            <div className="chart-container">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={scheme.data.convergence}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
                  <XAxis dataKey="num_steps" scale="log" domain={["auto", "auto"]}
                    stroke={CHART.axis} tick={{ fontSize: 11 }}
                    label={{ value: "steps (log)", position: "insideBottom", offset: -4, fill: CHART.axis, fontSize: 10 }} />
                  <YAxis scale="log" domain={["auto", "auto"]} stroke={CHART.axis} tick={{ fontSize: 11 }}
                    label={{ value: "abs error (log)", angle: -90, position: "insideLeft", fill: CHART.axis, fontSize: 10 }} />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} />
                  <Legend />
                  <Line type="monotone" dataKey="euler_error" stroke={CHART.down} strokeWidth={2}
                    dot={{ r: 3 }} name="Euler-Maruyama (order 0.5)" />
                  <Line type="monotone" dataKey="milstein_error" stroke={CHART.up} strokeWidth={2}
                    dot={{ r: 3 }} name="Milstein (order 1.0)" />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div style={{ overflowX: "auto", marginTop: "0.9rem" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Steps</th><th>dt</th><th>Exact Mean</th>
                    <th>Euler</th><th>Euler Error</th>
                    <th>Milstein</th><th>Milstein Error</th>
                  </tr>
                </thead>
                <tbody>
                  {scheme.data.convergence.map((r) => (
                    <tr key={r.num_steps}>
                      <td>{r.num_steps}</td>
                      <td>{r.dt}</td>
                      <td>{r.exact_mean}</td>
                      <td>{r.euler_mean}</td>
                      <td className="not-significant">{r.euler_error}</td>
                      <td>{r.milstein_mean}</td>
                      <td className="significant">{r.milstein_error}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="card-note" style={{ marginTop: "0.7rem" }}>
              {scheme.data.interpretation}
            </div>
          </>
        )}
      </motion.div>

      <motion.div className="card" variants={item} style={{ gridColumn: "1 / -1" }}>
        <div className="card-header">
          <div>
            <div className="card-title">
              Variance Reduction — Better Estimators Beat More Paths
              <InfoTip text="Monte Carlo error falls as 1/√N, so halving it by brute force costs four times the paths. Antithetic variates pair each draw Z with −Z; a control variate exploits a correlated quantity whose expectation is known exactly (here the discounted terminal spot). Both are free, and all four estimates must agree with the closed-form price — which also validates the analytic code." />
            </div>
            <div className="card-subtitle">
              Same option, same path count, four estimators
            </div>
          </div>
        </div>
        {vr.loading && <LoadingState message="Comparing estimators…" subtext="Plain, antithetic, control variate, both" />}
        {vr.error && !vr.loading && <ErrorState message={vr.error} onRetry={vr.reload} />}
        {vr.data?.methods && (
          <>
            <div className="chart-container">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={vr.data.methods}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
                  <XAxis dataKey="method" stroke={CHART.axis} tick={{ fontSize: 10 }}
                    tickFormatter={(v) => v.replace(/_/g, " ").replace("monte carlo", "MC")} />
                  <YAxis stroke={CHART.axis} tick={{ fontSize: 11 }}
                    label={{ value: "standard error", angle: -90, position: "insideLeft", fill: CHART.axis, fontSize: 10 }} />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle}
                    formatter={(v, n) => [v, n === "std_error" ? "standard error" : n]} />
                  <Bar dataKey="std_error" name="standard error" radius={[4, 4, 0, 0]}>
                    {vr.data.methods.map((_, i) => (
                      <Cell key={i} fill={SERIES[i % SERIES.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div style={{ overflowX: "auto", marginTop: "0.9rem" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Method</th><th>Price</th><th>Std Error</th>
                    <th>
                      <LabelWithTip tip="How many times more paths plain Monte Carlo would need to reach the same standard error. This is the efficiency gain, obtained for free.">
                        Equivalent Path Saving
                      </LabelWithTip>
                    </th>
                    <th>Error vs Analytic</th><th>Within 2 SE</th>
                  </tr>
                </thead>
                <tbody>
                  {vr.data.methods.map((m) => (
                    <tr key={m.method}>
                      <td style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                        {m.method.replace(/_/g, " ")}
                      </td>
                      <td>{m.price}</td>
                      <td>{m.std_error}</td>
                      <td className={m.variance_reduction_factor > 1.5 ? "significant" : ""}>
                        {m.variance_reduction_factor}×
                      </td>
                      <td>{m.abs_error_vs_analytic}</td>
                      <td>
                        <span className={`badge ${m.within_2_se ? "success" : "warning"}`}>
                          {m.within_2_se ? "PASS" : "CHECK"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="stats-grid" style={{ marginTop: "0.9rem" }}>
              <StatBox value={vr.data.analytic_black_scholes} label="Analytic Black-Scholes" highlight
                tip="The exact price every estimator is aiming at." />
              <StatBox value={vr.data.control_variate_beta} label="Control Variate β"
                tip="Cov(payoff, control)/Var(control) — the variance-minimising coefficient, estimated from the sample." />
            </div>
            <div className="card-note" style={{ marginTop: "0.7rem" }}>
              {vr.data.interpretation}
            </div>
          </>
        )}
      </motion.div>
    </>
  );
}

function StatBox({ value, label, tip, highlight, cls }) {
  const klass = cls || (highlight ? "highlight" : "neutral");
  return (
    <div className="stat-box">
      <div className={`stat-value ${klass}`}>{value ?? "—"}</div>
      <div className="stat-label">
        {tip ? <LabelWithTip tip={tip}>{label}</LabelWithTip> : label}
      </div>
    </div>
  );
}

function CheckRow({ ok, label, detail, tip }) {
  return (
    <div className={`check-row ${ok ? "pass" : "fail"}`}>
      <span className="check-ico"><Icon name={ok ? "check" : "alert"} size={15} /></span>
      {tip ? <LabelWithTip tip={tip}>{label}</LabelWithTip> : label}
      <span className="check-detail">{detail}</span>
    </div>
  );
}
