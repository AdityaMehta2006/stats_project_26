/**
 * Icon.jsx
 * --------
 * Lightweight inline SVG icon set (stroke-based, 24x24 viewbox, currentColor).
 * Usage: <Icon name="search" size={16} />
 */

const PATHS = {
  // Brand mark — stylized candlestick / signal
  logo: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="5" />
      <path d="M8 15.5V9M8 7.5v0M8 17v0" />
      <path d="M12 17V7M12 5.5v0M12 18.5v0" />
      <path d="M16 13.5v-3M16 8.5v0M16 15.5v0" />
    </>
  ),
  // Pillar: macro factor / regression — trending line
  trendingUp: (
    <>
      <path d="M3 17l6-6 4 4 8-8" />
      <path d="M17 7h4v4" />
    </>
  ),
  // Pillar: GARCH / volatility — waveform
  activity: <path d="M3 12h3l3 8 4-16 3 8h5" />,
  // Theme control: light / dark / follow the OS
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </>
  ),
  moon: <path d="M20 14.5A8.5 8.5 0 019.5 4a8.5 8.5 0 1010.5 10.5z" />,
  auto: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 3.5v17a8.5 8.5 0 000-17z" fill="currentColor" stroke="none" />
    </>
  ),
  // Pillar: options pricing — payoff hockey-stick with strike marker
  options: (
    <>
      <path d="M3 16h7l8-9" />
      <path d="M10 16v4" />
      <circle cx="18" cy="7" r="2" />
      <path d="M3 20h18" />
    </>
  ),
  // Pillar: stochastic processes — random walk with a mean-reversion band
  stochastic: (
    <>
      <path d="M3 12l3-5 3 8 3-9 3 7 3-4 3 3" />
      <path d="M3 5h18" strokeDasharray="2 3" />
      <path d="M3 19h18" strokeDasharray="2 3" />
    </>
  ),
  // Pillar: pair trading — exchange / mean reversion
  exchange: (
    <>
      <path d="M7 7h13" />
      <path d="M17 4l3 3-3 3" />
      <path d="M17 17H4" />
      <path d="M7 14l-3 3 3 3" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.3-4.3" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5" />
      <path d="M12 7.5v0" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  check: <path d="M4 12l5 5L20 6" />,
  alert: (
    <>
      <path d="M12 3l9 16H3l9-16z" />
      <path d="M12 10v4" />
      <path d="M12 17v0" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 11a8 8 0 1 0-2.3 5.7" />
      <path d="M20 5v6h-6" />
    </>
  ),
  database: (
    <>
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v6c0 1.66 3.58 3 8 3s8-1.34 8-3V5" />
      <path d="M4 11v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6" />
    </>
  ),
  calendar: (
    <>
      <rect x="3.5" y="4.5" width="17" height="16" rx="2.5" />
      <path d="M3.5 9h17" />
      <path d="M8 3v3M16 3v3" />
    </>
  ),
  globe: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
      <path d="M12 3c2.5 2.6 2.5 15.4 0 18M12 3c-2.5 2.6-2.5 15.4 0 18" />
    </>
  ),
  layers: (
    <>
      <path d="M12 3l9 5-9 5-9-5 9-5z" />
      <path d="M3 13l9 5 9-5" />
    </>
  ),
  arrowRight: <path d="M5 12h14M13 6l6 6-6 6" />,
  // Opportunities / scanner
  target: (
    <>
      <circle cx="12" cy="12" r="8" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="12" cy="12" r="0.6" />
    </>
  ),
  // Options / contract — a price bracket around a strike
  contract: (
    <>
      <path d="M4 5v14M20 5v14" />
      <path d="M4 5h3M4 19h3M20 5h-3M20 19h-3" />
      <path d="M8 12h8" />
      <circle cx="12" cy="12" r="2.2" />
    </>
  ),
  // AI / generate
  sparkles: (
    <>
      <path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8L12 3z" />
      <path d="M18 15l.8 2.2L21 18l-2.2.8L18 21l-.8-2.2L15 18l2.2-.8L18 15z" />
    </>
  ),
};

export default function Icon({ name, size = 20, strokeWidth = 1.75, className = "", style = {} }) {
  const path = PATHS[name];
  if (!path) return null;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={{ flexShrink: 0, ...style }}
      aria-hidden="true"
    >
      {path}
    </svg>
  );
}
