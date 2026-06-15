/**
 * ForexPairSelector.jsx
 * ---------------------
 * Multi-select component for choosing forex pairs from the available list.
 */

import { useState, useEffect } from "react";
import { getAvailableForex } from "../../api";

const DEFAULT_SELECTED = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "EURGBP"];

export default function ForexPairSelector({ selectedPairs, onPairsChange }) {
  const [available, setAvailable] = useState([]);
  const [filter, setFilter] = useState("");
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    getAvailableForex()
      .then((data) => setAvailable(data.pairs || []))
      .catch(() => {
        // Fallback if API not available
        setAvailable(DEFAULT_SELECTED.map((l) => ({ label: l, ticker: `${l}=X` })));
      });
  }, []);

  const filtered = available.filter((p) =>
    p.label.toLowerCase().includes(filter.toLowerCase())
  );

  const togglePair = (label) => {
    if (selectedPairs.includes(label)) {
      if (selectedPairs.length <= 2) return; // Need at least 2
      onPairsChange(selectedPairs.filter((p) => p !== label));
    } else {
      onPairsChange([...selectedPairs, label]);
    }
  };

  const selected = selectedPairs || DEFAULT_SELECTED;

  return (
    <div style={{ position: "relative" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span style={{
          fontSize: "0.78rem",
          color: "var(--text-muted)",
          fontWeight: 500,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          whiteSpace: "nowrap",
        }}>
          Pairs:
        </span>
        {selected.map((p) => (
          <span
            key={p}
            onClick={() => togglePair(p)}
            style={{
              padding: "3px 10px",
              borderRadius: 999,
              fontSize: "0.72rem",
              fontWeight: 600,
              fontFamily: "var(--font-mono)",
              background: "rgba(167,139,250,0.14)",
              color: "#A78BFA",
              border: "1px solid rgba(167,139,250,0.32)",
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
          >
            {p} ×
          </span>
        ))}
        <button
          onClick={() => setIsOpen(!isOpen)}
          style={{
            padding: "4px 12px",
            borderRadius: 999,
            fontSize: "0.72rem",
            fontWeight: 600,
            background: "rgba(255,255,255,0.04)",
            color: "var(--text-muted)",
            border: "1px solid var(--border-subtle)",
            cursor: "pointer",
            fontFamily: "var(--font-main)",
            transition: "all 0.2s ease",
          }}
        >
          + Add
        </button>
      </div>

      {isOpen && (
        <div style={{
          position: "absolute",
          top: "calc(100% + 8px)",
          left: 0,
          width: 300,
          background: "var(--bg-surface)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-md)",
          boxShadow: "var(--shadow-lg)",
          zIndex: 1000,
          padding: 8,
        }}>
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter pairs…"
            style={{
              width: "100%",
              background: "rgba(255,255,255,0.04)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-sm)",
              padding: "6px 10px",
              color: "var(--text-primary)",
              fontSize: "0.82rem",
              fontFamily: "var(--font-mono)",
              outline: "none",
              marginBottom: 6,
            }}
          />
          <div style={{ maxHeight: 240, overflowY: "auto" }}>
            {filtered.map((p) => {
              const isSelected = selected.includes(p.label);
              return (
                <div
                  key={p.label}
                  onClick={() => togglePair(p.label)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "6px 10px",
                    borderRadius: "var(--radius-sm)",
                    cursor: "pointer",
                    background: isSelected ? "rgba(167,139,250,0.1)" : "transparent",
                    transition: "background 0.15s ease",
                  }}
                  onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = "rgba(255,255,255,0.03)"; }}
                  onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.background = "transparent"; }}
                >
                  <span style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "0.8rem",
                    fontWeight: isSelected ? 600 : 400,
                    color: isSelected ? "#A78BFA" : "var(--text-secondary)",
                  }}>
                    {p.label}
                  </span>
                  {isSelected && (
                    <span style={{ color: "#A78BFA", fontSize: "0.85rem" }}>✓</span>
                  )}
                </div>
              );
            })}
          </div>
          <button
            onClick={() => setIsOpen(false)}
            style={{
              width: "100%",
              marginTop: 6,
              padding: "6px",
              background: "var(--accent-primary)",
              color: "white",
              border: "none",
              borderRadius: "var(--radius-sm)",
              fontSize: "0.78rem",
              fontWeight: 500,
              cursor: "pointer",
              fontFamily: "var(--font-main)",
            }}
          >
            Done
          </button>
        </div>
      )}
    </div>
  );
}
