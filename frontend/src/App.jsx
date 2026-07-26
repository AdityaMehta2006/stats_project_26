import { useState } from "react";
import { motion } from "framer-motion";
import "./index.css";
import Dashboard from "./components/Dashboard";
import MacroRegression from "./components/MacroRegression";
import GarchVolatility from "./components/GarchVolatility";
import PairTrading from "./components/PairTrading";
import Options from "./components/Options";
import Recommendations from "./components/Recommendations";
import Icon from "./components/common/Icon";
import BgPattern from "./components/common/BgPattern";
import { InfoTip } from "./components/common/Tooltip";
import { TickerProvider } from "./TickerContext";
import useApiData from "./hooks/useApiData";
import useTheme from "./hooks/useTheme";
import { getEngineStatus } from "./api";

const THEME_ICON = { system: "auto", light: "sun", dark: "moon" };
const THEME_NEXT = { system: "light", light: "dark", dark: "system" };

function ThemeToggle() {
  const { theme, cycle } = useTheme();
  return (
    <button
      className="theme-toggle"
      onClick={cycle}
      title={`Theme: ${theme}. Switch to ${THEME_NEXT[theme]}.`}
      aria-label={`Theme: ${theme}. Switch to ${THEME_NEXT[theme]}.`}
    >
      <Icon name={THEME_ICON[theme]} size={15} />
    </button>
  );
}

const TABS = [
  { id: "overview",      label: "Overview",        icon: "layers" },
  { id: "opportunities", label: "Opportunities",   icon: "target" },
  { id: "macro",         label: "Macro",           icon: "trendingUp" },
  { id: "garch",         label: "GARCH",           icon: "activity" },
  { id: "pairs",         label: "Pairs",           icon: "exchange" },
  { id: "options",       label: "Options",         icon: "contract" },
];

/**
 * Real backend state. The dot used to be hardcoded green — it stayed green
 * with the server down, which is the one moment it needed to say otherwise.
 */
function StatusStrip({ status }) {
  const s = status.data;

  const state = status.loading
    ? { cls: "warm", text: "Connecting", tip: "Checking the backend." }
    : status.error
    ? { cls: "down", text: "Offline", tip: "The analysis backend is not responding. Start it from the backend folder with: python main.py" }
    : !s.warm
    ? {
        cls: "warm",
        text: "Warming",
        tip: `Pre-computing the scan universe (${s.warm_assets}/${s.universe.length} assets ready). Everything still works — the first request for a cold asset just takes longer.`,
      }
    : {
        cls: "live",
        text: "Live",
        tip: `All ${s.universe.length} universe assets pre-computed. Market data runs to ${s.data_asof}. AI analyst: ${s.llm?.available ? s.llm.model || "ready" : "unavailable"}.`,
      };

  return (
    <div className={`header-live ${state.cls}`}>
      <span className="live-dot" />
      {state.text}
      {s?.data_asof && state.cls !== "down" && (
        <span className="live-asof mono-dim">{s.data_asof}</span>
      )}
      <InfoTip text={state.tip} />
    </div>
  );
}

function Shell() {
  const [activeTab, setActiveTab] = useState("overview");
  const status = useApiData((signal) => getEngineStatus(signal), [], "engine-status");
  const llmAvailable = Boolean(status.data?.llm?.available);

  const renderPanel = () => {
    switch (activeTab) {
      case "opportunities":
        return (
          <Recommendations
            onNavigate={setActiveTab}
            llmAvailable={llmAvailable}
            status={status.data}
          />
        );
      case "macro":  return <MacroRegression />;
      case "garch":  return <GarchVolatility />;
      case "pairs":  return <PairTrading />;
      case "options": return <Options />;
      default:       return <Dashboard onNavigate={setActiveTab} />;
    }
  };

  return (
    <div className="app">
      <BgPattern />
      <header className="header">
        <div className="header-inner">
          <div className="header-brand">
            <div className="header-logo">
              <Icon name="logo" size={20} strokeWidth={1.7} />
            </div>
            <div className="header-brand-text">
              <div className="header-title">
                Quant<span className="accent">Anomalies</span>
              </div>
              <div className="header-subtitle">Financial Markets Analysis</div>
            </div>
          </div>

          <nav className="nav-tabs">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                className={`nav-tab ${activeTab === tab.id ? "active" : ""}`}
                onClick={() => setActiveTab(tab.id)}
              >
                {activeTab === tab.id && (
                  <motion.span
                    layoutId="nav-active"
                    className="nav-active-bg"
                    transition={{ type: "spring", stiffness: 440, damping: 36 }}
                  />
                )}
                <span className="nav-tab-inner">
                  <Icon name={tab.icon} size={15} />
                  <span className="tab-label">{tab.label}</span>
                </span>
              </button>
            ))}
          </nav>

          <div className="header-right">
            <ThemeToggle />
            <StatusStrip status={status} />
          </div>
        </div>
      </header>

      <main className="main-content">
        {/* No AnimatePresence mode="wait" here. It held the incoming panel back
            until the outgoing one had finished leaving, so every tab switch had
            a ~240ms empty gap and a vertical jump before content appeared. The
            new panel now mounts immediately and crossfades — with the request
            cache underneath, a revisited tab paints instantly. */}
        <motion.div
          key={activeTab}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] }}
        >
          {renderPanel()}
        </motion.div>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <TickerProvider>
      <Shell />
    </TickerProvider>
  );
}
