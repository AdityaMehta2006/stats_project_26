/**
 * Tooltip.jsx
 * -----------
 * InfoTip: an accessible hover/focus tooltip used to explain metrics and terms.
 * Rendered as a small "i" icon that reveals an explanatory bubble on hover.
 */

import Icon from "./Icon";

export function InfoTip({ text, size = 14 }) {
  return (
    <span className="infotip" tabIndex={0} role="note">
      <Icon name="info" size={size} className="infotip-icon" />
      <span className="infotip-bubble" role="tooltip">
        {text}
      </span>
    </span>
  );
}

/**
 * Label + InfoTip pairing for stat boxes and card headings.
 */
export function LabelWithTip({ children, tip, className = "" }) {
  return (
    <span className={`label-with-tip ${className}`}>
      {children}
      {tip && <InfoTip text={tip} />}
    </span>
  );
}
