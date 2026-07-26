/**
 * TiltGauge.jsx
 * -------------
 * The verdict, as one instrument.
 *
 * It replaces four separate readouts that all described the same thing — a
 * conviction stat box, a direction stat box, a conviction meter, and an
 * "agreeing weight / against" line.
 *
 *   bear ◄──────────────┬──────────────► bull
 *              ▓▓▓▓▓●▓▓▓▓▓
 *
 * The marker sits at `tilt` (−1..+1). The band around it is the *inverse* of
 * conviction: thin evidence reads as a wide, faint band, strong evidence as a
 * tight, solid one. That is literally a confidence interval, which is this
 * project's own vernacular — a statistician reads it immediately, and a
 * beginner reads "the dot is left and the band is wide, so it leans down but
 * isn't sure".
 *
 * Direction is encoded by position as well as hue, so the red/green axis is
 * never load-bearing on its own.
 */

import { motion } from "framer-motion";

// Inset the ends so a marker at tilt = ±1 stays fully on the track instead of
// being clipped in half by the edge. Extremes are common here, not an edge case.
const pct = (t) => 1.5 + ((t + 1) / 2) * 97;

export default function TiltGauge({ tilt = 0, conviction = 0, stance = "" }) {
  const centre = pct(tilt);
  // Wide when unconvinced, narrow when certain. Floored so it stays visible.
  const halfWidth = Math.max(3, (1 - conviction) * 34);
  const left = Math.max(0, centre - halfWidth);
  const right = Math.min(100, centre + halfWidth);

  const tone = stance.includes("bull") ? "up" : stance.includes("bear") ? "down" : "flat";

  return (
    <div className="gauge">
      <div className="gauge-scale">
        <span>bear</span>
        <span>balanced</span>
        <span>bull</span>
      </div>

      <div className={`gauge-track ${tone}`}>
        <span className="gauge-centre" />

        <motion.span
          className="gauge-band"
          initial={{ left: "50%", right: "50%", opacity: 0 }}
          animate={{ left: `${left}%`, right: `${100 - right}%`, opacity: 1 }}
          transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
        />

        <motion.span
          className="gauge-marker"
          initial={{ left: "50%" }}
          animate={{ left: `${centre}%` }}
          transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>

      <div className="gauge-readout">
        <span className="mono-dim">
          tilt {tilt > 0 ? "+" : ""}{tilt.toFixed(2)}
        </span>
        <span className="mono-dim">conviction {conviction.toFixed(2)}</span>
      </div>
    </div>
  );
}

/**
 * Risk is a separate axis from direction — a volatility spike says the ride is
 * rough, not which way it goes. Segments rather than a smooth bar, so it reads
 * as an instrument and not as a progress indicator.
 */
export function RiskMeter({ risk = 0, segments = 10 }) {
  const lit = Math.round(risk * segments);
  return (
    <div className="risk-meter" role="img" aria-label={`Risk ${risk.toFixed(2)} of 1`}>
      {Array.from({ length: segments }, (_, i) => (
        <motion.span
          key={i}
          className={`risk-seg ${i < lit ? "lit" : ""}`}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.12 + i * 0.018, duration: 0.2 }}
        />
      ))}
    </div>
  );
}
