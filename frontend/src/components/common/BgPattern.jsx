/**
 * BgPattern.jsx
 * -------------
 * Plotting-paper grid. The two teal/cyan radial glows that used to sit on top
 * of it are gone — they were the ambient decoration the flat canvas replaces,
 * and they were the source of the stray tint band across the page.
 *
 * The grid stays because it means something here: this is a measurement
 * surface. It reads at the edge of perception and inherits the hairline token,
 * so it follows light and dark without a second definition.
 */
export default function BgPattern() {
  return (
    <div className="bg-pattern" aria-hidden="true">
      <svg width="100%" height="100%" preserveAspectRatio="xMidYMid slice">
        <defs>
          <pattern id="grid-sm" width="32" height="32" patternUnits="userSpaceOnUse">
            <path d="M32 0H0V32" fill="none" stroke="var(--hairline)" strokeWidth="0.5" />
          </pattern>

          <linearGradient id="grid-fade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fff" stopOpacity="0.55" />
            <stop offset="55%" stopColor="#fff" stopOpacity="0.14" />
            <stop offset="100%" stopColor="#fff" stopOpacity="0" />
          </linearGradient>
          <mask id="grid-mask">
            <rect width="100%" height="100%" fill="url(#grid-fade)" />
          </mask>
        </defs>

        <g mask="url(#grid-mask)">
          <rect width="100%" height="100%" fill="url(#grid-sm)" />
        </g>
      </svg>
    </div>
  );
}
