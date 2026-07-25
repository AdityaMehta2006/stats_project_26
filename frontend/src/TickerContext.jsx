/**
 * TickerContext.jsx
 * -----------------
 * One ticker and one forex-pair selection shared across every tab.
 *
 * Each panel used to hold its own useState("^GSPC"), so switching tabs silently
 * reset what you were looking at — and drilling from a signal into the pillar
 * that produced it was impossible.
 */

import { useState, useMemo } from "react";
import { TickerCtx, DEFAULT_PAIRS } from "./ticker";

export function TickerProvider({ children }) {
  const [ticker, setTicker] = useState("^GSPC");
  // Shared with the engine, so the basket picked on the Pairs tab is the one
  // the pairs detector reasons over.
  const [pairs, setPairs] = useState(DEFAULT_PAIRS);

  const value = useMemo(
    () => ({ ticker, setTicker, pairs, setPairs }),
    [ticker, pairs]
  );

  return <TickerCtx.Provider value={value}>{children}</TickerCtx.Provider>;
}
