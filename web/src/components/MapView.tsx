import { useMemo } from 'react';
import DeckGL from '@deck.gl/react';
import { LineLayer } from '@deck.gl/layers';
import { Map } from 'react-map-gl/maplibre';
import type { MapViewState } from '@deck.gl/core';
import 'maplibre-gl/dist/maplibre-gl.css';

import type { EdgeTier, RemovalStep } from '../lib/data';
import { HIGHLIGHT_RGB, REMOVED_RGB, buildColorBuffer, logScale, type Theme } from '../lib/color';

/** CARTO's public basemap styles need no API key, which keeps the deploy free. */
const BASEMAP: Record<Theme, string> = {
  dark: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  light: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
};

export const INITIAL_VIEW: MapViewState = {
  longitude: 106.7,
  latitude: 10.78,
  zoom: 10.6,
  pitch: 0,
  bearing: 0,
};

interface RemovalSegment {
  source: [number, number];
  target: [number, number];
  step: RemovalStep;
}

interface Props {
  viewState: MapViewState;
  onViewStateChange: (next: MapViewState) => void;
  topTier: EdgeTier | null;
  fullTier: EdgeTier | null;
  removals: RemovalStep[];
  maxBetweenness: number;
  showFull: boolean;
  showTop: boolean;
  showRemovals: boolean;
  selectedRank: number | null;
  onSelect: (rank: number | null) => void;
  theme: Theme;
}

export function MapView({
  viewState,
  onViewStateChange,
  topTier,
  fullTier,
  removals,
  maxBetweenness,
  showFull,
  showTop,
  showRemovals,
  selectedRank,
  onSelect,
  theme,
}: Props) {
  // Colour buffers are derived once per tier and theme; rebuilding 1.2M RGBA
  // values on every render would drop frames while panning.
  // The background tier is context, not the message: it stays in the low half of
  // the ramp so the scored top tier drawn over it still reads clearly. On the
  // pale basemap it also needs more opacity to survive against white.
  const fullColors = useMemo(
    () =>
      fullTier
        ? buildColorBuffer(
            fullTier.values,
            (rank) => rank * 0.42,
            theme === 'dark' ? (t) => 30 + t * 120 : (t) => 45 + t * 130,
            theme,
          )
        : null,
    [fullTier, theme],
  );

  const topColors = useMemo(() => {
    if (!topTier) return null;
    const scale = logScale(maxBetweenness);
    return buildColorBuffer(topTier.values, scale, (t) => 110 + t * 145, theme);
  }, [topTier, maxBetweenness, theme]);

  const removalSegments = useMemo<RemovalSegment[]>(
    () =>
      removals.flatMap((step) =>
        step.segments.map((s) => ({
          source: [s[0], s[1]] as [number, number],
          target: [s[2], s[3]] as [number, number],
          step,
        })),
      ),
    [removals],
  );

  const layers = [
    showFull && fullTier && fullColors
      ? new LineLayer({
          id: 'full-network',
          data: {
            length: fullTier.count,
            attributes: {
              getSourcePosition: { value: fullTier.sourcePositions, size: 2 },
              getTargetPosition: { value: fullTier.targetPositions, size: 2 },
              getColor: { value: fullColors, size: 4 },
            },
          },
          getWidth: 1,
          widthMinPixels: 0.5,
          widthMaxPixels: 2,
          pickable: false,
        })
      : null,
    showTop && topTier && topColors
      ? new LineLayer({
          id: 'top-betweenness',
          data: {
            length: topTier.count,
            attributes: {
              getSourcePosition: { value: topTier.sourcePositions, size: 2 },
              getTargetPosition: { value: topTier.targetPositions, size: 2 },
              getColor: { value: topColors, size: 4 },
            },
          },
          getWidth: 2,
          widthMinPixels: 1.2,
          widthMaxPixels: 6,
          pickable: false,
        })
      : null,
    showRemovals
      ? new LineLayer<RemovalSegment>({
          id: 'removed-segments',
          data: removalSegments,
          getSourcePosition: (d) => d.source,
          getTargetPosition: (d) => d.target,
          getColor: (d) =>
            d.step.rank === selectedRank ? HIGHLIGHT_RGB[theme] : REMOVED_RGB[theme],
          getWidth: (d) => (d.step.rank === selectedRank ? 9 : 5),
          widthMinPixels: 2.5,
          widthMaxPixels: 14,
          pickable: true,
          onClick: (info) => onSelect(info.object ? info.object.step.rank : null),
          updateTriggers: { getColor: [selectedRank, theme], getWidth: selectedRank },
        })
      : null,
  ].filter(Boolean);

  return (
    <DeckGL
      viewState={viewState}
      onViewStateChange={(e) => onViewStateChange(e.viewState as MapViewState)}
      controller={{ dragRotate: false }}
      layers={layers}
      getTooltip={({ object }) => {
        const segment = object as RemovalSegment | null;
        if (!segment) return null;
        const { step } = segment;
        return {
          html: `<strong>#${step.rank} ${escapeHtml(step.roadName)}</strong><br/>
                 Extra travel cost: ${step.deltaCost.toFixed(0)} m<br/>
                 ${step.edgeCount} segment${step.edgeCount === 1 ? '' : 's'} removed`,
          style: {
            background: theme === 'dark' ? 'rgba(12, 16, 24, 0.94)' : 'rgba(255, 255, 255, 0.97)',
            color: theme === 'dark' ? '#e8ecf4' : '#16202e',
            fontSize: '12px',
            padding: '8px 10px',
            borderRadius: '6px',
            border:
              theme === 'dark'
                ? '1px solid rgba(255,255,255,0.14)'
                : '1px solid rgba(16,26,40,0.18)',
            boxShadow: theme === 'dark' ? 'none' : '0 6px 20px rgba(16,26,40,0.14)',
            maxWidth: '240px',
          },
        };
      }}
    >
      <Map reuseMaps mapStyle={BASEMAP[theme]} />
    </DeckGL>
  );
}

function escapeHtml(value: string): string {
  return value.replace(
    /[&<>"']/g,
    (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string,
  );
}
