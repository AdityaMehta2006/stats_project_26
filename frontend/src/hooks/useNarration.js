/**
 * useNarration.js
 * ---------------
 * Streams the AI analyst note from /api/engine/narrate.
 *
 * That endpoint is a plain GET emitting server-sent events, so EventSource —
 * the native API built for exactly this — handles it with no library.
 *
 * Three server events (see backend/engine.py: narrate_stream):
 *   stance  the model's OWN read, ~10 tokens in, before any prose
 *   token   text, appended as generated
 *   done    {unverified_numbers} — the grounding check, or {skipped}
 */

import { useState, useRef, useCallback, useEffect } from "react";
import { narrateURL } from "../api";

export default function useNarration(ticker, pairs) {
  const [stance, setStance] = useState(null);
  const [text, setText] = useState("");
  const [unverified, setUnverified] = useState(null);
  const [skipped, setSkipped] = useState(null);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState(null);
  const srcRef = useRef(null);

  const close = useCallback(() => {
    srcRef.current?.close();
    srcRef.current = null;
  }, []);

  const reset = useCallback(() => {
    close();
    setStance(null);
    setText("");
    setUnverified(null);
    setSkipped(null);
    setError(null);
    setStreaming(false);
  }, [close]);

  const start = useCallback(() => {
    reset();
    setStreaming(true);

    const src = new EventSource(narrateURL(ticker, pairs));
    srcRef.current = src;

    src.addEventListener("stance", (e) => setStance(JSON.parse(e.data)));
    src.addEventListener("token", (e) => setText((t) => t + JSON.parse(e.data)));
    src.addEventListener("done", (e) => {
      const d = JSON.parse(e.data);
      if (d.error) setError(d.error);
      if (d.skipped) setSkipped(d.skipped);
      setUnverified(d.unverified_numbers ?? null);
      setStreaming(false);
      close();
    });
    // EventSource retries forever by default; one failure is enough here.
    src.onerror = () => {
      setError("Lost connection to the analyst stream");
      setStreaming(false);
      close();
    };
  }, [ticker, pairs, reset, close]);

  // Cleanup as the effect body: runs when the asset changes (the old note no
  // longer describes what's on screen) and on unmount (closes the stream).
  useEffect(() => reset, [ticker, pairs, reset]);

  return { stance, text, unverified, skipped, streaming, error, start, reset };
}
