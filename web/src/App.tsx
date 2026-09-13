import { useCallback, useEffect, useState } from 'react';
import type { MapViewState } from '@deck.gl/core';

import { INITIAL_VIEW, MapView } from './components/MapView';
import { Sidebar } from './components/Sidebar';
import {
  loadFullTier,
  loadMeta,
  loadRemovals,
  loadTopTier,
  type EdgeTier,
  type Meta,
  type RemovalStep,
  type TopRoad,
} from './lib/data';

type Tab = 'roads' | 'removals' | 'speed';

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [removals, setRemovals] = useState<RemovalStep[]>([]);
  const [topTier, setTopTier] = useState<EdgeTier | null>(null);
  const [fullTier, setFullTier] = useState<EdgeTier | null>(null);
  const [fullLoading, setFullLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [showTop, setShowTop] = useState(true);
  const [showFull, setShowFull] = useState(false);
  const [showRemovals, setShowRemovals] = useState(true);
  const [tab, setTab] = useState<Tab>('roads');
  const [selectedRank, setSelectedRank] = useState<number | null>(null);
  const [viewState, setViewState] = useState<MapViewState>(INITIAL_VIEW);
  const [panelOpen, setPanelOpen] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const loaded = await loadMeta();
        setMeta(loaded);
        const [tier, steps] = await Promise.all([
          loadTopTier(loaded.topCount),
          loadRemovals(),
        ]);
        setTopTier(tier);
        setRemovals(steps);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : String(cause));
      }
    })();
  }, []);

  // The full network is ~4 MB, so it is fetched only when someone asks for it,
  // then kept in memory for the rest of the session.
  const toggleFull = useCallback(async () => {
    if (showFull) {
      setShowFull(false);
      return;
    }
    if (fullTier || !meta) {
      setShowFull(true);
      return;
    }
    setFullLoading(true);
    try {
      setFullTier(await loadFullTier(meta.edgeCount, meta.bounds, meta.quantMax));
      setShowFull(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setFullLoading(false);
    }
  }, [showFull, fullTier, meta]);

  const flyTo = useCallback((longitude: number, latitude: number, zoom = 15) => {
    setViewState((current) => ({ ...current, longitude, latitude, zoom }));
    setPanelOpen(false);
  }, []);

  const selectRemoval = useCallback(
    (rank: number | null) => {
      setSelectedRank(rank);
      const step = removals.find((s) => s.rank === rank);
      const first = step?.segments[0];
      if (first) flyTo((first[0] + first[2]) / 2, (first[1] + first[3]) / 2, 14.5);
    },
    [removals, flyTo],
  );

  const flyToRoad = useCallback(
    (road: TopRoad) => {
      const [x1, y1, x2, y2] = road.segment;
      flyTo((x1 + x2) / 2, (y1 + y2) / 2, 15);
    },
    [flyTo],
  );

  if (error) {
    return (
      <div className="fullscreen-message">
        <h1>Could not load the analysis data</h1>
        <p>{error}</p>
        <p className="note">
          Run <code>roadnet export-web</code> to regenerate <code>web/public/data</code>.
        </p>
      </div>
    );
  }

  if (!meta) {
    return (
      <div className="fullscreen-message">
        <div className="spinner" aria-hidden />
        <p>Loading road network…</p>
      </div>
    );
  }

  return (
    <div className={panelOpen ? 'layout panel-open' : 'layout'}>
      <MapView
        viewState={viewState}
        onViewStateChange={setViewState}
        topTier={topTier}
        fullTier={fullTier}
        removals={removals}
        maxBetweenness={meta.betweenness.max}
        showFull={showFull}
        showTop={showTop}
        showRemovals={showRemovals}
        selectedRank={selectedRank}
        onSelect={selectRemoval}
      />

      <Sidebar
        meta={meta}
        removals={removals}
        tab={tab}
        onTab={setTab}
        showTop={showTop}
        showFull={showFull}
        showRemovals={showRemovals}
        fullLoaded={fullTier !== null}
        fullLoading={fullLoading}
        onToggleTop={() => setShowTop((v) => !v)}
        onToggleFull={toggleFull}
        onToggleRemovals={() => setShowRemovals((v) => !v)}
        selectedRank={selectedRank}
        onSelect={selectRemoval}
        onFlyToRoad={flyToRoad}
      />

      <button
        className="panel-handle"
        onClick={() => setPanelOpen((v) => !v)}
        aria-expanded={panelOpen}
      >
        {panelOpen ? 'Hide details' : 'Show details'}
      </button>

      <button
        className="reset-view"
        onClick={() => {
          setViewState(INITIAL_VIEW);
          setSelectedRank(null);
        }}
      >
        Reset view
      </button>
    </div>
  );
}
