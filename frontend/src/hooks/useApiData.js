/**
 * useApiData.js
 * -------------
 * Fetching with loading/error state, a stale-response guard, and a small
 * session cache.
 *
 * The cache is what stops tab switching feeling janky. Without it every panel
 * refetched from scratch on mount, so moving between tabs blanked the screen
 * and rebuilt it — even though the backend had the answer cached and returned
 * in milliseconds. Now a revisit paints the previous answer immediately and
 * revalidates behind it (stale-while-revalidate).
 *
 * `key` must be unique per endpoint. Deps alone are not enough: the macro and
 * GARCH panels both key on [ticker] and would otherwise collide.
 */

import { useState, useEffect, useCallback, useRef } from "react";

const cache = new Map();

export default function useApiData(fetcher, deps = [], key) {
  const cacheKey = key ? `${key}:${JSON.stringify(deps)}` : null;
  const cached = cacheKey ? cache.get(cacheKey) : undefined;

  const [data, setData] = useState(cached ?? null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const acRef = useRef(null);

  const load = useCallback(async () => {
    acRef.current?.abort();
    const ac = new AbortController();
    acRef.current = ac;

    // Paint what we already have; the request below refreshes it in place.
    const hit = cacheKey ? cache.get(cacheKey) : undefined;
    if (hit !== undefined) setData(hit);

    setLoading(true);
    setError(null);
    try {
      // fetcher may ignore the signal — the aborted checks below still hold.
      const result = await fetcher(ac.signal);
      if (ac.signal.aborted) return;
      if (cacheKey) cache.set(cacheKey, result);
      setData(result);
    } catch (err) {
      if (!ac.signal.aborted && err.name !== "AbortError") {
        setError(err.message || "Failed to load data");
      }
    } finally {
      if (!ac.signal.aborted) setLoading(false);
    }
  // `deps` is supplied by the caller, so it cannot be an array literal here.
  // The lint rule is reporting its own inability to verify statically, not a
  // defect: `fetcher` is deliberately excluded because callers pass a fresh
  // arrow on every render, and including it would refetch in an endless loop.
  // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/use-memo
  }, deps);

  useEffect(() => {
    load();
    return () => acRef.current?.abort();
  }, [load]);

  return { data, loading, error, reload: load };
}
