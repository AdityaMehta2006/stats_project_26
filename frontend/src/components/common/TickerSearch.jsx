/**
 * TickerSearch.jsx
 * ----------------
 * A search-as-you-type ticker selector with debounced API calls.
 * Displays results in a dropdown and calls onSelect(ticker) when chosen.
 */

import { useState, useRef, useEffect, useCallback } from "react";
import { searchTickers } from "../../api";
import Icon from "./Icon";

const POPULAR_TICKERS = [
  { ticker: "^GSPC", name: "S&P 500", type: "INDEX" },
  { ticker: "^DJI", name: "Dow Jones Industrial", type: "INDEX" },
  { ticker: "^IXIC", name: "NASDAQ Composite", type: "INDEX" },
  { ticker: "^RUT", name: "Russell 2000", type: "INDEX" },
  { ticker: "AAPL", name: "Apple Inc.", type: "EQUITY" },
  { ticker: "MSFT", name: "Microsoft Corp.", type: "EQUITY" },
  { ticker: "GOOGL", name: "Alphabet Inc.", type: "EQUITY" },
  { ticker: "AMZN", name: "Amazon.com Inc.", type: "EQUITY" },
  { ticker: "TSLA", name: "Tesla Inc.", type: "EQUITY" },
  { ticker: "NVDA", name: "NVIDIA Corp.", type: "EQUITY" },
  { ticker: "META", name: "Meta Platforms", type: "EQUITY" },
  { ticker: "JPM", name: "JPMorgan Chase", type: "EQUITY" },
  { ticker: "^NSEI", name: "Nifty 50", type: "INDEX" },
  { ticker: "^BSESN", name: "BSE Sensex", type: "INDEX" },
  { ticker: "^FTSE", name: "FTSE 100", type: "INDEX" },
  { ticker: "^N225", name: "Nikkei 225", type: "INDEX" },
  { ticker: "GC=F", name: "Gold Futures", type: "FUTURE" },
  { ticker: "BTC-USD", name: "Bitcoin USD", type: "CRYPTOCURRENCY" },
  { ticker: "ETH-USD", name: "Ethereum USD", type: "CRYPTOCURRENCY" },
];

export default function TickerSearch({ value, onSelect, label = "Ticker" }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const wrapperRef = useRef(null);
  const debounceRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Debounced search
  const doSearch = useCallback(async (q) => {
    if (!q || q.length < 1) {
      setResults(POPULAR_TICKERS);
      setIsSearching(false);
      return;
    }
    setIsSearching(true);
    try {
      const data = await searchTickers(q);
      if (data.results && data.results.length > 0) {
        setResults(data.results);
      } else {
        // Filter popular tickers as fallback
        const filtered = POPULAR_TICKERS.filter(
          (t) =>
            t.ticker.toLowerCase().includes(q.toLowerCase()) ||
            t.name.toLowerCase().includes(q.toLowerCase())
        );
        setResults(filtered.length > 0 ? filtered : []);
      }
    } catch {
      const filtered = POPULAR_TICKERS.filter(
        (t) =>
          t.ticker.toLowerCase().includes(q.toLowerCase()) ||
          t.name.toLowerCase().includes(q.toLowerCase())
      );
      setResults(filtered);
    } finally {
      setIsSearching(false);
    }
  }, []);

  const handleInputChange = (e) => {
    const val = e.target.value;
    setQuery(val);
    setIsOpen(true);

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(val), 300);
  };

  const handleFocus = () => {
    setIsOpen(true);
    if (results.length === 0) {
      setResults(POPULAR_TICKERS);
    }
  };

  const handleSelect = (ticker) => {
    onSelect(ticker);
    setQuery("");
    setIsOpen(false);
  };

  const typeColors = {
    EQUITY: "#34D399",
    INDEX: "#2DD4BF",
    ETF: "#38BDF8",
    FUTURE: "#FBBF24",
    CRYPTOCURRENCY: "#A78BFA",
    CURRENCY: "#F472B6",
  };

  return (
    <div ref={wrapperRef} style={{ position: "relative", minWidth: 280 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{
          fontSize: "0.78rem",
          color: "var(--text-muted)",
          fontWeight: 500,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          whiteSpace: "nowrap",
        }}>
          {label}:
        </span>
        <div style={{
          display: "flex",
          alignItems: "center",
          background: "rgba(255,255,255,0.04)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-sm)",
          padding: "0 12px",
          flex: 1,
          transition: "border-color 0.2s ease",
          borderColor: isOpen ? "var(--border-active)" : "var(--border-subtle)",
        }}>
          <span style={{ color: "var(--text-muted)", display: "inline-flex", marginRight: 8 }}>
            <Icon name="search" size={15} />
          </span>
          {value && !isOpen && (
            <span style={{
              padding: "4px 10px",
              background: "rgba(45,212,191,0.14)",
              border: "1px solid rgba(45,212,191,0.32)",
              borderRadius: 999,
              fontSize: "0.78rem",
              fontWeight: 600,
              color: "var(--accent-primary)",
              fontFamily: "var(--font-mono)",
              marginRight: 6,
              cursor: "pointer",
            }} onClick={() => { setIsOpen(true); setResults(POPULAR_TICKERS); }}>
              {value}
            </span>
          )}
          <input
            type="text"
            value={isOpen ? query : ""}
            onChange={handleInputChange}
            onFocus={handleFocus}
            placeholder={isOpen ? "Search any ticker (e.g. AAPL, ^NSEI, BTC-USD)…" : value ? "Click to change" : "Search…"}
            style={{
              background: "transparent",
              border: "none",
              outline: "none",
              color: "var(--text-primary)",
              fontSize: "0.85rem",
              fontFamily: "var(--font-main)",
              padding: "8px 0",
              flex: 1,
              minWidth: 0,
            }}
          />
          {isSearching && (
            <div style={{
              width: 14, height: 14,
              border: "2px solid var(--border-subtle)",
              borderTopColor: "var(--accent-primary)",
              borderRadius: "50%",
              animation: "spin 0.6s linear infinite",
            }} />
          )}
        </div>
      </div>

      {/* Dropdown */}
      {isOpen && results.length > 0 && (
        <div style={{
          position: "absolute",
          top: "calc(100% + 4px)",
          left: 0,
          right: 0,
          background: "var(--bg-surface)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-md)",
          boxShadow: "var(--shadow-lg)",
          maxHeight: 320,
          overflowY: "auto",
          zIndex: 1000,
        }}>
          {!query && (
            <div style={{
              padding: "8px 14px 4px",
              fontSize: "0.68rem",
              color: "var(--text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              fontWeight: 600,
            }}>
              Popular Tickers
            </div>
          )}
          {results.map((r, i) => (
            <div
              key={`${r.ticker}-${i}`}
              onClick={() => handleSelect(r.ticker)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px 14px",
                cursor: "pointer",
                transition: "background 0.15s ease",
                borderBottom: i < results.length - 1 ? "1px solid var(--border-subtle)" : "none",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.04)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                <span style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.82rem",
                  fontWeight: 600,
                  color: "var(--text-primary)",
                  whiteSpace: "nowrap",
                }}>
                  {r.ticker}
                </span>
                <span style={{
                  fontSize: "0.78rem",
                  color: "var(--text-muted)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}>
                  {r.name}
                </span>
              </div>
              {r.type && (
                <span style={{
                  fontSize: "0.65rem",
                  fontWeight: 600,
                  padding: "2px 8px",
                  borderRadius: 999,
                  background: `${typeColors[r.type] || "#5E6B7E"}18`,
                  color: typeColors[r.type] || "#5E6B7E",
                  border: `1px solid ${typeColors[r.type] || "#5E6B7E"}30`,
                  whiteSpace: "nowrap",
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                }}>
                  {r.type}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
