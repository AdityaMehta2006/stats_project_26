/**
 * useTheme.js
 * -----------
 * Three states, not two: light, dark, or follow the OS.
 *
 * "System" is the default and stays the default — a classroom projector and a
 * 6am monitor want opposite things, and the OS already knows which one you are
 * on. The explicit choices exist for when it doesn't.
 *
 * Writes `data-theme` on <html>; index.css does the rest.
 */

import { useState, useEffect, useCallback } from "react";

const KEY = "qa-theme";
const ORDER = ["system", "light", "dark"];

export default function useTheme() {
  const [theme, setTheme] = useState(() => localStorage.getItem(KEY) || "system");

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    localStorage.setItem(KEY, theme);
  }, [theme]);

  const cycle = useCallback(
    () => setTheme((t) => ORDER[(ORDER.indexOf(t) + 1) % ORDER.length]),
    []
  );

  return { theme, setTheme, cycle };
}
