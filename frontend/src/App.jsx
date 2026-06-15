/**
 * App.jsx
 * -------
 * Root application component with header navigation and tab routing.
 */

import { useState } from "react";
import "./index.css";
import Dashboard from "./components/Dashboard";
import MacroRegression from "./components/MacroRegression";
import GarchVolatility from "./components/GarchVolatility";
import PairTrading from "./components/PairTrading";
import Icon from "./components/common/Icon";
import BgPattern from "./components/common/BgPattern";

const TABS = [
  { id: "overview", label: "Overview", icon: "layers" },
  { id: "macro", label: "Macro Regression", icon: "trendingUp" },
  { id: "garch", label: "GARCH Volatility", icon: "activity" },
  { id: "pairs", label: "Pair Trading", icon: "exchange" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("overview");

  const renderPanel = () => {
    switch (activeTab) {
      case "macro":
        return <MacroRegression />;
      case "garch":
        return <GarchVolatility />;
      case "pairs":
        return <PairTrading />;
      default:
        return <Dashboard onNavigate={setActiveTab} />;
    }
  };

  return (
    <div className="app">
      <BgPattern />
      <header className="header">
        <div className="header-inner">
          <div className="header-brand">
            <div className="header-logo">
              <Icon name="logo" size={22} strokeWidth={1.8} />
            </div>
            <div>
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
                <Icon name={tab.icon} size={16} />
                <span className="tab-label">{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="main-content">{renderPanel()}</main>
    </div>
  );
}
