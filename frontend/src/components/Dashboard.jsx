import { motion } from "framer-motion";
import Icon from "./common/Icon";

/**
 * Overview as one bento grid: the five pillars, the scale of the data, and what
 * the app can be pointed at, all on a single set of hairlines. Cells vary in
 * span so the grid carries hierarchy on its own — no floating cards, no
 * nesting, no shadows.
 */

const PILLARS = [
  {
    id: "macro",
    icon: "trendingUp",
    title: "Macro Factor & Lag Regression",
    description:
      "How macroeconomic forces — rates, inflation, the VIX, oil, gold, the dollar — move equity returns, and with what delay. OLS with lags, plus Granger causality.",
    tags: ["OLS", "Granger", "Lagged correlation"],
  },
  {
    id: "garch",
    icon: "activity",
    title: "GARCH & Volatility Clustering",
    description:
      "How risk itself changes over time. A GARCH(1,1) fit captures calm and turbulent regimes, and tests whether returns carry the fat tails a normal distribution misses.",
    tags: ["GARCH(1,1)", "Clustering", "Fat tails"],
  },
  {
    id: "pairs",
    icon: "exchange",
    title: "Forex Pair Trading",
    description:
      "Currency pairs whose prices stay tethered over the long run. Builds the mean-reverting spread and generates z-score entries — statistical arbitrage in miniature.",
    tags: ["Cointegration", "Z-score", "Mean reversion"],
  },
  {
    id: "options",
    icon: "options",
    iconClass: "options",
    title: "Options Pricing & Volatility Surface",
    description:
      "Prices options with Black-Scholes, Merton jump-diffusion and Heston stochastic volatility. The Options tab reads a live chain for Greeks and implied-versus-realised vol; the Pricing tab drives the same models on parameters you set, showing why Black-Scholes implies a flat volatility curve while real markets are skewed.",
    tags: ["Black-Scholes", "Greeks", "Volatility Smile", "Implied Vol"],
    nav: "options",
  },
  {
    id: "stochastic",
    icon: "stochastic",
    iconClass: "stochastic",
    title: "Stochastic Processes",
    description:
      "The differential equations underneath everything else: Brownian motion, geometric Brownian motion, Ornstein-Uhlenbeck (the process pair trading assumes), CIR and Heston — with numerical schemes and variance reduction compared against exact solutions.",
    tags: ["Itô's Lemma", "SDEs", "Monte Carlo", "Euler vs Milstein"],
    nav: "stochastic",
  },
];

const SCALE = [
  { value: "5", label: "Analysis pillars" },
  { value: "13", label: "Detectors" },
  { value: "40+", label: "FX pairs" },
  { value: "10Y", label: "Daily history" },
];

const SOURCES = [
  { label: "Any ticker", icon: "search", desc: "Stocks, indices, crypto, futures" },
  { label: "Live data", icon: "database", desc: "Yahoo Finance + FRED" },
  { label: "Local model", icon: "sparkles", desc: "Explains, never computes" },
];

export default function Dashboard({ onNavigate }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
    >
      <header className="panel-head">
        <h1>Quantitative anomalies in financial markets</h1>
        <p>
          Five classic effects that break the assumptions of textbook finance —
          modelled live in Python, fused into one read, and explained in plain
          English by a local model.
        </p>
      </header>

      <div className="bento">
        {PILLARS.map((p) => (
          <button
            key={p.id}
            className="bento-cell pillar interactive"
            onClick={() => onNavigate(p.id)}
          >
            <span className="bento-ico">
              <Icon name={p.icon} size={18} strokeWidth={1.7} />
            </span>
            <h2 className="bento-title">
              {p.title}
              <Icon name="arrowRight" size={15} className="go-arrow" />
            </h2>
            <p className="bento-text">{p.description}</p>
            <span className="bento-tags">
              {p.tags.map((t) => (
                <span key={t} className="evidence-chip">{t}</span>
              ))}
            </span>
          </button>
        ))}

        {SCALE.map((s) => (
          <div key={s.label} className="bento-cell metric">
            <span className="bento-figure">{s.value}</span>
            <span className="micro-label">{s.label}</span>
          </div>
        ))}

        {SOURCES.map((f) => (
          <div key={f.label} className="bento-cell source">
            <span className="bento-ico">
              <Icon name={f.icon} size={16} />
            </span>
            <span className="bento-label">{f.label}</span>
            <span className="micro-label">{f.desc}</span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
