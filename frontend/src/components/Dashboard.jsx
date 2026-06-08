/**
 * Dashboard.jsx
 * -------------
 * Overview landing page with pillar cards and project description.
 */

import { motion } from "framer-motion";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.12 } },
};
const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" } },
};

const PILLARS = [
  {
    id: "macro",
    icon: "📈",
    iconClass: "macro",
    title: "Macro Factor & Lag Regression",
    description:
      "Analyze how macroeconomic variables (Fed Funds Rate, CPI, VIX, Oil) explain equity returns using OLS regression with time lags and Granger causality tests.",
    tags: ["OLS Regression", "Granger Causality", "Lagged Correlation", "VAR"],
  },
  {
    id: "garch",
    icon: "🌊",
    iconClass: "garch",
    title: "GARCH & Volatility Clustering",
    description:
      "Model time-varying volatility using GARCH(1,1), detect fat tails with QQ plots, and confirm volatility clustering via autocorrelation of squared returns.",
    tags: ["GARCH(1,1)", "Volatility Clustering", "Fat Tails", "Ljung-Box Test"],
  },
  {
    id: "pairs",
    icon: "💱",
    iconClass: "pairs",
    title: "Forex Pair Trading",
    description:
      "Identify cointegrated forex pairs using Engle-Granger tests, construct mean-reverting spreads, and generate z-score based trading signals.",
    tags: ["Cointegration", "Z-Score", "Mean Reversion", "Half-Life"],
  },
];

export default function Dashboard({ onNavigate }) {
  return (
    <motion.div variants={container} initial="hidden" animate="show">
      <motion.div className="dashboard-hero" variants={item}>
        <h1>Quantitative Anomalies in Financial Markets</h1>
        <p>
          A statistical analysis of volatility, factor risk, and lagged transmission
          across equity and forex markets — powered by Python and React.
        </p>
      </motion.div>

      <motion.div className="pillar-cards" variants={item}>
        {PILLARS.map((pillar) => (
          <motion.div
            key={pillar.id}
            className="pillar-card"
            variants={item}
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            onClick={() => onNavigate(pillar.id)}
          >
            <div className={`pillar-icon ${pillar.iconClass}`}>{pillar.icon}</div>
            <h3>{pillar.title}</h3>
            <p>{pillar.description}</p>
            <div className="pillar-tags">
              {pillar.tags.map((tag) => (
                <span key={tag} className="pillar-tag">{tag}</span>
              ))}
            </div>
          </motion.div>
        ))}
      </motion.div>

      <motion.div variants={item} style={{ marginTop: "3rem", textAlign: "center" }}>
        <div style={{
          display: "inline-flex",
          flexWrap: "wrap",
          gap: "1.5rem",
          justifyContent: "center",
          padding: "1.5rem 2rem",
          background: "var(--bg-card)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-lg)",
        }}>
          {[
            { label: "Any Ticker", icon: "🔍", desc: "Search any stock, index, crypto" },
            { label: "Real-Time Data", icon: "📊", desc: "Yahoo Finance + FRED" },
            { label: "10Y History", icon: "📅", desc: "2015 – 2025 daily data" },
            { label: "Dynamic Forex", icon: "💹", desc: "40+ currency pairs" },
          ].map((f) => (
            <div key={f.label} style={{ textAlign: "center", minWidth: 120 }}>
              <div style={{ fontSize: "1.5rem", marginBottom: 4 }}>{f.icon}</div>
              <div style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--text-primary)" }}>{f.label}</div>
              <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>{f.desc}</div>
            </div>
          ))}
        </div>
      </motion.div>
    </motion.div>
  );
}
