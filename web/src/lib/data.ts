/**
 * Loaders for the payloads written by `roadnet export-web`.
 *
 * Both edge tiers arrive as flat typed arrays rather than GeoJSON: 1.2M
 * segments as JSON would be several hundred MB and would stall the main thread
 * for seconds while parsing.
 */

export interface Bounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

export interface BandLatency {
  deg_level_1: number;
  deg_level_2: number;
  deg_level_3: number;
  overall: number;
}

export interface TopRoad {
  name: string;
  betweenness: number;
  totalBetweenness: number;
  /** [x1, y1, x2, y2] of the road's single most central segment. */
  segment: [number, number, number, number];
}

export interface Meta {
  generatedAt: string;
  bounds: Bounds;
  nodeCount: number;
  edgeCount: number;
  topCount: number;
  quantMax: number;
  betweenness: { max: number; min: number; topThreshold: number };
  topRoads: TopRoad[];
  removalCount: number;
  benchmarks: Partial<Record<'dijkstra' | 'astar' | 'ch', BandLatency>>;
}

export interface RemovalStep {
  rank: number;
  roadName: string;
  deltaCost: number;
  cumulativeDelta: number;
  baselineCost: number;
  betweenness: number;
  edgeCount: number;
  /** Flat [x1, y1, x2, y2] per removed segment. */
  segments: number[][];
}

/** Positions split into source/target pairs, the shape deck.gl's LineLayer wants. */
export interface EdgeTier {
  count: number;
  sourcePositions: Float32Array;
  targetPositions: Float32Array;
  /** Betweenness, either raw (top tier) or a 0-1 rank (full tier). */
  values: Float32Array;
}

const DATA_ROOT = `${import.meta.env.BASE_URL}data`;

export async function loadMeta(): Promise<Meta> {
  const response = await fetch(`${DATA_ROOT}/meta.json`);
  if (!response.ok) throw new Error(`meta.json: ${response.status}`);
  return response.json();
}

export async function loadRemovals(): Promise<RemovalStep[]> {
  const response = await fetch(`${DATA_ROOT}/removals.json`);
  if (!response.ok) throw new Error(`removals.json: ${response.status}`);
  return response.json();
}

/**
 * `top.bin`: Float32 [x1,y1,x2,y2] per edge, then one Float32 betweenness each.
 */
export async function loadTopTier(count: number): Promise<EdgeTier> {
  const buffer = await fetchBuffer(`${DATA_ROOT}/top.bin`);
  const coords = new Float32Array(buffer, 0, count * 4);
  const values = new Float32Array(buffer, count * 4 * 4, count);
  return { count, ...splitPositions(coords, count), values };
}

/**
 * `network.bin`: Uint16 [x1,y1,x2,y2] per edge quantised over `bounds`, then
 * one Uint8 rank each. Dequantised here so the GPU still receives floats.
 */
export async function loadFullTier(
  count: number,
  bounds: Bounds,
  quantMax: number,
): Promise<EdgeTier> {
  const buffer = await fetchBuffer(`${DATA_ROOT}/network.bin`);
  const quantised = new Uint16Array(buffer, 0, count * 4);
  const ranks = new Uint8Array(buffer, count * 4 * 2, count);

  const spanX = (bounds.maxX - bounds.minX) / quantMax;
  const spanY = (bounds.maxY - bounds.minY) / quantMax;
  const sourcePositions = new Float32Array(count * 2);
  const targetPositions = new Float32Array(count * 2);
  const values = new Float32Array(count);

  for (let i = 0; i < count; i++) {
    const q = i * 4;
    sourcePositions[i * 2] = bounds.minX + quantised[q] * spanX;
    sourcePositions[i * 2 + 1] = bounds.minY + quantised[q + 1] * spanY;
    targetPositions[i * 2] = bounds.minX + quantised[q + 2] * spanX;
    targetPositions[i * 2 + 1] = bounds.minY + quantised[q + 3] * spanY;
    values[i] = ranks[i] / 255;
  }
  return { count, sourcePositions, targetPositions, values };
}

function splitPositions(coords: Float32Array, count: number) {
  const sourcePositions = new Float32Array(count * 2);
  const targetPositions = new Float32Array(count * 2);
  for (let i = 0; i < count; i++) {
    sourcePositions[i * 2] = coords[i * 4];
    sourcePositions[i * 2 + 1] = coords[i * 4 + 1];
    targetPositions[i * 2] = coords[i * 4 + 2];
    targetPositions[i * 2 + 1] = coords[i * 4 + 3];
  }
  return { sourcePositions, targetPositions };
}

async function fetchBuffer(url: string): Promise<ArrayBuffer> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  return response.arrayBuffer();
}
