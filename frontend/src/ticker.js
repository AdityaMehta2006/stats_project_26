/**
 * ticker.js
 * ---------
 * The shared ticker/pairs context and its hook. Split from the provider
 * component so fast refresh keeps working (react-refresh/only-export-components).
 */

import { createContext, useContext } from "react";

export const TickerCtx = createContext(null);

export const DEFAULT_PAIRS = [
  "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "EURGBP",
];

export function useTicker() {
  const ctx = useContext(TickerCtx);
  if (!ctx) throw new Error("useTicker must be used inside <TickerProvider>");
  return ctx;
}
