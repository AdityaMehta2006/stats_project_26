/**
 * timeRange.js
 * ------------
 * Helpers for the chart time-range filters. Rows are assumed sorted ascending
 * by their date field (as the backend returns them).
 */

export const RANGE_DAYS = {
  "1M": 30, "3M": 91, "6M": 182, "1Y": 365,
  "2Y": 730, "3Y": 1095, "5Y": 1825,
};

export const DAILY_RANGES = ["1M", "3M", "6M", "1Y", "5Y", "All"];
export const MONTHLY_RANGES = ["1Y", "3Y", "5Y", "All"];

export function filterByRange(rows, range, dateKey = "date") {
  if (!rows || rows.length === 0 || range === "All") return rows || [];
  const days = RANGE_DAYS[range];
  if (!days) return rows;
  const last = new Date(rows[rows.length - 1][dateKey]);
  const cutoff = new Date(last);
  cutoff.setDate(cutoff.getDate() - days);
  return rows.filter((r) => new Date(r[dateKey]) >= cutoff);
}

/** Sensible XAxis tick interval for a series of length n (aim for ~8 labels). */
export function axisInterval(n, labels = 8) {
  return Math.max(0, Math.floor(n / labels));
}
