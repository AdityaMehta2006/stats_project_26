/**
 * ParamControls.jsx
 * -----------------
 * Numeric / select inputs for driving the pricing and simulation models.
 *
 * Design intent, matching the rest of the dashboard: every parameter carries a
 * hover tooltip explaining what it *means*, not just what it is called. Someone
 * who does not know what "vol-of-vol" or "mean-reversion speed" is should be
 * able to learn it from the UI rather than the source.
 *
 * Values are held as strings while typing (so a half-entered "-" or "0." does
 * not get coerced to NaN mid-keystroke) and only parsed on commit.
 */

import { useState, useCallback } from "react";
import Icon from "./Icon";
import { LabelWithTip } from "./Tooltip";

/**
 * @param {Array} fields  [{ key, label, tip, min, max, step, hint, type, options }]
 * @param {Object} values current values keyed by field key
 * @param {Function} onChange called with the full committed value object
 */
export default function ParamControls({ fields, values, onChange, onReset }) {
  // Only the field currently being typed into holds local draft state. Every
  // other input reads straight from props. This avoids mirroring the whole
  // value object into state and then having to re-sync it with an effect —
  // which would cause cascading renders and could go stale on a parent reset.
  const [editing, setEditing] = useState(null); // { key, raw } | null

  const displayValue = (key) =>
    editing && editing.key === key ? editing.raw : String(values[key] ?? "");

  const commit = useCallback(
    (key, raw) => {
      setEditing(null);
      const field = fields.find((f) => f.key === key);
      if (!field) return;

      if (field.type === "select") {
        if (raw !== values[key]) onChange({ ...values, [key]: raw });
        return;
      }

      const num = parseFloat(raw);
      // Unparseable input is simply discarded; clearing `editing` above already
      // restores the last committed value on screen.
      if (Number.isNaN(num)) return;

      // Clamp into the model's valid domain so the backend never receives a
      // negative volatility or a zero maturity.
      let clamped = num;
      if (field.min !== undefined) clamped = Math.max(field.min, clamped);
      if (field.max !== undefined) clamped = Math.min(field.max, clamped);
      if (clamped !== values[key]) onChange({ ...values, [key]: clamped });
    },
    [fields, values, onChange]
  );

  return (
    <div style={{ width: "100%" }}>
      <div className="param-grid">
        {fields.map((f) => (
          <div className="param-field" key={f.key}>
            <label htmlFor={`param-${f.key}`}>
              <LabelWithTip tip={f.tip}>{f.label}</LabelWithTip>
            </label>

            {f.type === "select" ? (
              <select
                id={`param-${f.key}`}
                value={String(values[f.key] ?? "")}
                onChange={(e) => commit(f.key, e.target.value)}
              >
                {f.options.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id={`param-${f.key}`}
                type="number"
                inputMode="decimal"
                value={displayValue(f.key)}
                min={f.min}
                max={f.max}
                step={f.step ?? "any"}
                onChange={(e) => setEditing({ key: f.key, raw: e.target.value })}
                onBlur={(e) => commit(f.key, e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") commit(f.key, e.currentTarget.value);
                  if (e.key === "Escape") setEditing(null);
                }}
              />
            )}

            {f.hint && <span className="param-hint">{f.hint}</span>}
          </div>
        ))}
      </div>

      {onReset && (
        <div className="param-actions" style={{ marginTop: "0.8rem" }}>
          <button className="param-reset" onClick={onReset} type="button">
            <Icon name="refresh" size={13} /> Reset to defaults
          </button>
        </div>
      )}
    </div>
  );
}
