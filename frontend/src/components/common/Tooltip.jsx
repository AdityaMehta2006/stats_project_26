/**
 * Tooltip.jsx
 * -----------
 * InfoTip: an accessible hover/focus tooltip used to explain metrics and terms.
 * Rendered as a small "i" icon that reveals an explanatory bubble on hover.
 *
 * The bubble is a **popover**, so the browser paints it in the top layer. It was
 * previously an absolutely-positioned child, which meant any ancestor with a
 * clipping overflow ate it — and three separate ones did: `.stat-box` is
 * `overflow: hidden`, every wide table sits in an `overflow-x: auto` wrapper,
 * and `.card` clips too. Measured across the six tabs, 36 of 74 tooltips were
 * cut off. The top layer is immune to all of them, and to transformed ancestors
 * (framer-motion sets `transform` mid-animation, which would break a plain
 * `position: fixed` fallback).
 *
 * Placement is ours because CSS anchor positioning is still Chromium-only.
 */

import { useRef, useCallback, useEffect } from "react";
import Icon from "./Icon";

const GAP = 9;   // space between the icon and the bubble
const EDGE = 8;  // keep this far off the viewport edge

/**
 * Prefer above; flip below when there isn't room. Clamp horizontally so a tip
 * on the first or last stat box stays fully on screen, and let the arrow slide
 * to stay pointed at the icon when that clamp kicks in.
 */
function place(anchor, bubble) {
  const a = anchor.getBoundingClientRect();
  const b = bubble.getBoundingClientRect();

  const above = a.top - GAP - b.height >= EDGE;
  const top = above ? a.top - GAP - b.height : a.bottom + GAP;

  const ideal = a.left + a.width / 2 - b.width / 2;
  const left = Math.max(EDGE, Math.min(ideal, window.innerWidth - b.width - EDGE));

  bubble.style.top = `${top}px`;
  bubble.style.left = `${left}px`;
  bubble.dataset.side = above ? "top" : "bottom";
  bubble.style.setProperty("--arrow-x", `${a.left + a.width / 2 - left}px`);
}

export function InfoTip({ text, size = 14 }) {
  const anchorRef = useRef(null);
  const bubbleRef = useRef(null);

  const reposition = useCallback(() => {
    const a = anchorRef.current, b = bubbleRef.current;
    if (a && b?.matches(":popover-open")) place(a, b);
  }, []);

  const show = useCallback(() => {
    const a = anchorRef.current, b = bubbleRef.current;
    if (!a || !b || b.matches(":popover-open")) return;
    b.showPopover();
    place(a, b);   // after showing: a hidden element measures 0×0
  }, []);

  const hide = useCallback(() => {
    const b = bubbleRef.current;
    if (b?.matches(":popover-open")) b.hidePopover();
  }, []);

  // Coordinates are viewport-relative, so they go stale the moment the page
  // moves underneath an open tooltip.
  useEffect(() => {
    window.addEventListener("scroll", reposition, true);
    window.addEventListener("resize", reposition);
    return () => {
      window.removeEventListener("scroll", reposition, true);
      window.removeEventListener("resize", reposition);
    };
  }, [reposition]);

  return (
    <span
      ref={anchorRef}
      className="infotip"
      tabIndex={0}
      role="note"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      onKeyDown={(e) => e.key === "Escape" && hide()}
    >
      <Icon name="info" size={size} className="infotip-icon" />
      <span ref={bubbleRef} className="infotip-bubble" role="tooltip" popover="manual">
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
