/**
 * lib/colors.ts — Light shade pastel color palette for flash cards.
 * Provides soft, attractive backgrounds with matching borders, text, and accents.
 */

export interface LightShade {
  bg: string;
  border: string;
  text: string;
  badge: string;
  accent: string;
}

export const LIGHT_SHADES: LightShade[] = [
  { bg: "#f0f7ff", border: "#bae0fd", text: "#0369a1", badge: "#e0f2fe", accent: "#0284c7" }, // Sky Blue
  { bg: "#f5f3ff", border: "#ddd6fe", text: "#6d28d9", badge: "#ede9fe", accent: "#7c3aed" }, // Lavender
  { bg: "#f0fdf4", border: "#bbf7d0", text: "#15803d", badge: "#dcfce7", accent: "#16a34a" }, // Mint Green
  { bg: "#fffbeb", border: "#fde68a", text: "#b45309", badge: "#fef3c7", accent: "#d97706" }, // Amber
  { bg: "#fff1f2", border: "#fecdd3", text: "#be123c", badge: "#ffe4e6", accent: "#e11d48" }, // Rose
  { bg: "#f0fdfa", border: "#99f6e4", text: "#0f766e", badge: "#ccfbf1", accent: "#0d9488" }, // Teal
  { bg: "#eef2ff", border: "#c7d2fe", text: "#4338ca", badge: "#e0e7ff", accent: "#4f46e5" }, // Indigo
  { bg: "#fdf4ff", border: "#f5d0fe", text: "#a21caf", badge: "#fae8ff", accent: "#c026d3" }, // Fuchsia
];

/** Returns a coordinating light pastel shade for cards by index or random */
export function getLightShade(index?: number): LightShade {
  if (typeof index === "number") {
    return LIGHT_SHADES[Math.abs(index) % LIGHT_SHADES.length];
  }
  return LIGHT_SHADES[Math.floor(Math.random() * LIGHT_SHADES.length)];
}
