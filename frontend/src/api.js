/**
 * api.js
 * ------
 * Centralized API client for the FastAPI backend.
 * All analysis endpoints accept dynamic ticker/pair parameters.
 */

const API_BASE = "http://localhost:8000/api";

async function fetchJSON(endpoint) {
  const res = await fetch(`${API_BASE}${endpoint}`);
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

// Health
export const checkHealth = () => fetchJSON("/health");

// Ticker search & validation
export const searchTickers = (query) =>
  fetchJSON(`/search?q=${encodeURIComponent(query)}`);
export const validateTicker = (ticker) =>
  fetchJSON(`/validate?ticker=${encodeURIComponent(ticker)}`);
export const getAvailableForex = () => fetchJSON("/forex/available");

// Pillar 1: Macro Regression — accepts any equity ticker
export const getMacroOLS = (ticker = "^GSPC", maxLag = 3) =>
  fetchJSON(`/macro-regression/ols?ticker=${encodeURIComponent(ticker)}&max_lag=${maxLag}`);
export const getMacroGranger = (ticker = "^GSPC", maxLag = 4) =>
  fetchJSON(`/macro-regression/granger?ticker=${encodeURIComponent(ticker)}&max_lag=${maxLag}`);
export const getMacroHeatmap = (ticker = "^GSPC", maxLag = 3) =>
  fetchJSON(`/macro-regression/heatmap?ticker=${encodeURIComponent(ticker)}&max_lag=${maxLag}`);
export const getMacroTimeSeries = (ticker = "^GSPC") =>
  fetchJSON(`/macro-regression/timeseries?ticker=${encodeURIComponent(ticker)}`);

// Pillar 2: GARCH — accepts any ticker
export const getGarchFit = (ticker = "^GSPC", dist = "t") =>
  fetchJSON(`/garch/fit?ticker=${encodeURIComponent(ticker)}&dist=${dist}`);
export const getGarchClustering = (ticker = "^GSPC") =>
  fetchJSON(`/garch/clustering?ticker=${encodeURIComponent(ticker)}`);
export const getGarchDistribution = (ticker = "^GSPC") =>
  fetchJSON(`/garch/distribution?ticker=${encodeURIComponent(ticker)}`);
export const getGarchCompare = (ticker = "^GSPC") =>
  fetchJSON(`/garch/compare?ticker=${encodeURIComponent(ticker)}`);

// Pillar 3: Pair Trading — accepts custom forex pair list
export const getPairsCointegration = (pairs = null) => {
  const q = pairs ? `?pairs=${encodeURIComponent(pairs.join(","))}` : "";
  return fetchJSON(`/pairs/cointegration${q}`);
};
export const getPairsBest = (pairs = null) => {
  const q = pairs ? `?pairs=${encodeURIComponent(pairs.join(","))}` : "";
  return fetchJSON(`/pairs/best${q}`);
};
export const getPairsCorrelation = (pairs = null) => {
  const q = pairs ? `?pairs=${encodeURIComponent(pairs.join(","))}` : "";
  return fetchJSON(`/pairs/correlation${q}`);
};

// Recommendation / Anomaly–Opportunity engine
export const getLlmInfo = () => fetchJSON("/llm/info");
export const getRecommendations = (ticker = "^GSPC", useLlm = false, pairs = null) => {
  const p = pairs ? `&pairs=${encodeURIComponent(pairs.join(","))}` : "";
  return fetchJSON(`/recommendations?ticker=${encodeURIComponent(ticker)}&use_llm=${useLlm}${p}`);
};
