/**
 * Colour ramps for the map.
 *
 * Betweenness is extremely skewed, so raw values are mapped through a rank or
 * log transform before hitting the ramp — otherwise every road but the top few
 * arterials collapses into the first colour stop.
 */

export type RGB = [number, number, number];

/** Viridis, subsampled. Perceptually uniform and legible on a dark basemap. */
const VIRIDIS: RGB[] = [
  [68, 1, 84],
  [72, 40, 120],
  [62, 74, 137],
  [49, 104, 142],
  [38, 130, 142],
  [31, 158, 137],
  [53, 183, 121],
  [109, 205, 89],
  [180, 222, 44],
  [253, 231, 37],
];

/** Signal colour for segments removed by the simulation. */
export const REMOVED_RGB: RGB = [255, 92, 42];
export const HIGHLIGHT_RGB: RGB = [255, 236, 120];

export function ramp(t: number): RGB {
  const clamped = Math.min(1, Math.max(0, t));
  const scaled = clamped * (VIRIDIS.length - 1);
  const i = Math.min(VIRIDIS.length - 2, Math.floor(scaled));
  const f = scaled - i;
  const a = VIRIDIS[i];
  const b = VIRIDIS[i + 1];
  return [
    Math.round(a[0] + (b[0] - a[0]) * f),
    Math.round(a[1] + (b[1] - a[1]) * f),
    Math.round(a[2] + (b[2] - a[2]) * f),
  ];
}

export function cssRamp(t: number): string {
  const [r, g, b] = ramp(t);
  return `rgb(${r}, ${g}, ${b})`;
}

/**
 * Packs per-edge colours into one RGBA buffer for deck.gl's binary attribute path.
 *
 * `transform` maps a raw value to 0-1; `alpha` maps it to opacity, which lets the
 * background tier fade out unimportant roads instead of drawing a uniform mat.
 */
export function buildColorBuffer(
  values: Float32Array,
  transform: (value: number) => number,
  alpha: (t: number) => number,
): Uint8Array {
  const colors = new Uint8Array(values.length * 4);
  for (let i = 0; i < values.length; i++) {
    const t = transform(values[i]);
    const [r, g, b] = ramp(t);
    colors[i * 4] = r;
    colors[i * 4 + 1] = g;
    colors[i * 4 + 2] = b;
    colors[i * 4 + 3] = alpha(t);
  }
  return colors;
}

/** Log transform for raw betweenness, which spans several orders of magnitude. */
export function logScale(max: number) {
  const denominator = Math.log1p(max * 1e6) || 1;
  return (value: number) => Math.log1p(Math.max(value, 0) * 1e6) / denominator;
}

export function formatMeters(meters: number): string {
  if (Math.abs(meters) >= 1000) return `${(meters / 1000).toFixed(1)} km`;
  return `${meters.toFixed(0)} m`;
}

export function formatSeconds(seconds: number): string {
  if (seconds < 0.001) return `${(seconds * 1e6).toFixed(0)} µs`;
  if (seconds < 1) return `${(seconds * 1000).toFixed(1)} ms`;
  return `${seconds.toFixed(2)} s`;
}
