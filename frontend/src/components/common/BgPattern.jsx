export default function BgPattern() {
  return (
    <div className="bg-pattern" aria-hidden="true">
      <svg width="100%" height="100%" preserveAspectRatio="xMidYMid slice">
        <defs>
          <pattern id="grid-sm" width="30" height="30" patternUnits="userSpaceOnUse">
            <path d="M30 0H0V30" fill="none" stroke="rgba(148,163,184,0.042)" strokeWidth="0.75" />
          </pattern>
          <pattern id="grid-lg" width="150" height="150" patternUnits="userSpaceOnUse">
            <path d="M150 0H0V150" fill="none" stroke="rgba(45,212,191,0.04)" strokeWidth="0.75" />
          </pattern>

          <linearGradient id="grid-fade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor="#fff" stopOpacity="0.85" />
            <stop offset="40%"  stopColor="#fff" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#fff" stopOpacity="0" />
          </linearGradient>
          <mask id="grid-mask">
            <rect width="100%" height="100%" fill="url(#grid-fade)" />
          </mask>

          <radialGradient id="glow-top" cx="50%" cy="0%" r="65%">
            <stop offset="0%"   stopColor="#2DD4BF" stopOpacity="0.055" />
            <stop offset="100%" stopColor="#2DD4BF" stopOpacity="0" />
          </radialGradient>

          <radialGradient id="glow-corner" cx="95%" cy="5%" r="40%">
            <stop offset="0%"   stopColor="#38BDF8" stopOpacity="0.04" />
            <stop offset="100%" stopColor="#38BDF8" stopOpacity="0" />
          </radialGradient>
        </defs>

        <rect width="100%" height="100%" fill="url(#glow-top)" />
        <rect width="100%" height="100%" fill="url(#glow-corner)" />
        <g mask="url(#grid-mask)">
          <rect width="100%" height="100%" fill="url(#grid-sm)" />
          <rect width="100%" height="100%" fill="url(#grid-lg)" />
        </g>
      </svg>
    </div>
  );
}
