/**
 * BgPattern.jsx
 * -------------
 * Fixed, non-interactive SVG backdrop: a faint blueprint grid plus a soft
 * horizon glow. Deliberately low-contrast ("stealth") so it adds depth and a
 * quant-terminal texture without competing with the data.
 */

export default function BgPattern() {
  return (
    <div className="bg-pattern" aria-hidden="true">
      <svg width="100%" height="100%" preserveAspectRatio="xMidYMid slice">
        <defs>
          <pattern id="grid-sm" width="34" height="34" patternUnits="userSpaceOnUse">
            <path d="M34 0H0V34" fill="none" stroke="rgba(148,163,184,0.05)" strokeWidth="1" />
          </pattern>
          <pattern id="grid-lg" width="170" height="170" patternUnits="userSpaceOnUse">
            <path d="M170 0H0V170" fill="none" stroke="rgba(45,212,191,0.05)" strokeWidth="1" />
          </pattern>

          {/* Vertical fade so the grid only reads near the top and dissolves below */}
          <linearGradient id="grid-fade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fff" stopOpacity="0.9" />
            <stop offset="45%" stopColor="#fff" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#fff" stopOpacity="0" />
          </linearGradient>
          <mask id="grid-mask">
            <rect width="100%" height="100%" fill="url(#grid-fade)" />
          </mask>

          {/* Soft teal horizon glow */}
          <radialGradient id="glow" cx="50%" cy="0%" r="75%">
            <stop offset="0%" stopColor="#2DD4BF" stopOpacity="0.06" />
            <stop offset="100%" stopColor="#2DD4BF" stopOpacity="0" />
          </radialGradient>
        </defs>

        <rect width="100%" height="100%" fill="url(#glow)" />
        <g mask="url(#grid-mask)">
          <rect width="100%" height="100%" fill="url(#grid-sm)" />
          <rect width="100%" height="100%" fill="url(#grid-lg)" />
        </g>
      </svg>
    </div>
  );
}
