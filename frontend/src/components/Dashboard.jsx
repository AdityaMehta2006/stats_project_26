/**
 * Dashboard.jsx
 * -------------
 * Overview landing page with pillar cards and project description.
 */

import { motion } from "framer-motion";
import Icon from "./common/Icon";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.1 } },
};
const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" } },
};

const PILLARS = [
  {
    id: "macro",
    icon: "trendingUp",
    iconClass: "macro",
    title: "Macro Factor & Lag Regression",
    description:
      "Measures how macroeconomic forces — interest rates, inflation, the VIX, oil, gold and the dollar — move equity returns, and crucially with what time delay. Uses OLS regression with lags and Granger-causality tests.",
    tags: ["OLS Regression", "Granger Causality", "Lagged Correlation"],
  },
  {
    id: "garch",
    icon: "activity",
    iconClass: "garch",
    title: "GARCH & Volatility Clustering",
    description:
      "Models how risk itself changes over time. Fits a GARCH(1,1) model to capture volatility clustering (calm and turbulent regimes) and tests whether returns have the fat tails that a normal distribution misses.",
    tags: ["GARCH(1,1)", "Volatility Clustering", "Fat Tails"],
  },
  {
    id: "pairs",
    icon: "exchange",
    iconClass: "pairs",
    title: "Forex Pair Trading",
    description:
      "Finds currency pairs whose prices move together long-term (cointegration), builds a mean-reverting spread, and generates z-score entry/exit signals — the basis of a statistical-arbitrage strategy.",
    tags: ["Cointegration", "Z-Score", "Mean Reversion"],
  },
];

const FEATURES = [
  { label: "Any Ticker", icon: "search", desc: "Stocks, indices, crypto" },
  { label: "Live Data", icon: "database", desc: "Yahoo Finance + FRED" },
  { label: "10Y History", icon: "calendar", desc: "2015 – 2025 daily" },
  { label: "40+ FX Pairs", icon: "globe", desc: "Pick any combination" },
];

export default function Dashboard({ onNavigate }) {
  return (
    <motion.div variants={container} initial="hidden" animate="show">
      <motion.div className="dashboard-hero" variants={item}>
        <div className="hero-eyebrow">
          <Icon name="activity" size={13} /> Quantitative Research Dashboard
        </div>
        <h1>
          Quantitative Anomalies in <span className="accent">Financial Markets</span>
        </h1>
        <p>
          A statistical study of volatility, factor risk, and lagged transmission across
          equity and forex markets — three classic effects that break the assumptions of
          textbook finance, modelled live with Python and visualised in React.
        </p>
      </motion.div>

      <motion.div className="pillar-cards" variants={item}>
        {PILLARS.map((pillar) => (
          <motion.div
            key={pillar.id}
            className="pillar-card"
            variants={item}
            whileHover={{ scale: 1.005 }}
            whileTap={{ scale: 0.99 }}
            onClick={() => onNavigate(pillar.id)}
          >
            <div className={`pillar-icon ${pillar.iconClass}`}>
              <Icon name={pillar.icon} size={24} />
            </div>
            <h3>
              {pillar.title}
              <Icon name="arrowRight" size={18} className="go-arrow" />
            </h3>
            <p>{pillar.description}</p>
            <div className="pillar-tags">
              {pillar.tags.map((tag) => (
                <span key={tag} className="pillar-tag">{tag}</span>
              ))}
            </div>
          </motion.div>
        ))}
      </motion.div>

      <motion.div className="feature-strip" variants={item}>
        {FEATURES.map((f) => (
          <div key={f.label} className="feature-item">
            <div className="feature-ico"><Icon name={f.icon} size={18} /></div>
            <div>
              <div className="feature-label">{f.label}</div>
              <div className="feature-desc">{f.desc}</div>
            </div>
          </div>
        ))}
      </motion.div>
    </motion.div>
  );
}
