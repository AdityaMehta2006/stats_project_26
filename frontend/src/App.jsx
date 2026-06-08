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

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "macro", label: "Macro Regression" },
  { id: "garch", label: "GARCH Volatility" },
  { id: "pairs", label: "Pair Trading" },
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
      {/* Header */}
      <header className="header">
        <div className="header-inner">
          <div className="header-brand">
            <div className="header-logo">QA</div>
            <div>
              <div className="header-title">QuantAnomalies</div>
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
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className="main-content">{renderPanel()}</main>
    </div>
  );
}
