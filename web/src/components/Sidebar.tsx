import { cssRamp, formatSeconds, type Theme } from '../lib/color';
import type { Meta, RemovalStep, TopRoad } from '../lib/data';

type Tab = 'roads' | 'removals' | 'speed';

interface Props {
  meta: Meta;
  removals: RemovalStep[];
  tab: Tab;
  onTab: (tab: Tab) => void;
  showTop: boolean;
  showFull: boolean;
  showRemovals: boolean;
  fullLoaded: boolean;
  fullLoading: boolean;
  onToggleTop: () => void;
  onToggleFull: () => void;
  onToggleRemovals: () => void;
  selectedRank: number | null;
  onSelect: (rank: number | null) => void;
  onFlyToRoad: (road: TopRoad) => void;
  theme: Theme;
  onToggleTheme: () => void;
}

export function Sidebar({
  meta,
  removals,
  tab,
  onTab,
  showTop,
  showFull,
  showRemovals,
  fullLoaded,
  fullLoading,
  onToggleTop,
  onToggleFull,
  onToggleRemovals,
  selectedRank,
  onSelect,
  onFlyToRoad,
  theme,
  onToggleTheme,
}: Props) {
  return (
    <aside className="sidebar">
      <header className="sidebar-head">
        <button
          className="theme-toggle"
          onClick={onToggleTheme}
          title={theme === 'dark' ? 'Switch to light map' : 'Switch to dark map'}
          aria-label={theme === 'dark' ? 'Switch to light map' : 'Switch to dark map'}
        >
          {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
        </button>
        <h1>Ho Chi Minh City road network</h1>
        <p className="sub">
          Criticality and vulnerability across {meta.edgeCount.toLocaleString()} segments,
          computed with Contraction Hierarchies.
        </p>
      </header>

      <section className="block">
        <h2>Layers</h2>
        <Toggle
          checked={showTop}
          onChange={onToggleTop}
          label={`Top ${meta.topCount.toLocaleString()} by betweenness`}
          swatch={<Gradient theme={theme} />}
        />
        <Toggle
          checked={showFull}
          onChange={onToggleFull}
          label={
            fullLoading
              ? 'Loading full network…'
              : `Full network (${meta.edgeCount.toLocaleString()} edges)`
          }
          hint={fullLoaded || fullLoading ? undefined : '≈4 MB download'}
          disabled={fullLoading}
        />
        <Toggle
          checked={showRemovals}
          onChange={onToggleRemovals}
          label={`Removed streets (${meta.removalCount})`}
          swatch={
            <span
              className="swatch"
              style={{ background: theme === 'dark' ? 'rgb(255,92,42)' : 'rgb(214,58,12)' }}
            />
          }
        />
      </section>

      <nav className="tabs" role="tablist">
        {(
          [
            ['roads', 'Top roads'],
            ['removals', 'Impact'],
            ['speed', 'Query speed'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            className={tab === key ? 'tab active' : 'tab'}
            onClick={() => onTab(key)}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="panel">
        {tab === 'roads' && <RoadTable meta={meta} onFlyToRoad={onFlyToRoad} theme={theme} />}
        {tab === 'removals' && (
          <RemovalTable
            removals={removals}
            selectedRank={selectedRank}
            onSelect={onSelect}
            theme={theme}
          />
        )}
        {tab === 'speed' && <SpeedTable meta={meta} />}
      </div>

      <footer className="sidebar-foot">
        <a href="https://github.com/hphuoc0906/hcmcity_road_evaluation">Source on GitHub</a>
        <span>Data: OpenStreetMap</span>
      </footer>
    </aside>
  );
}

function RoadTable({
  meta,
  onFlyToRoad,
  theme,
}: {
  meta: Meta;
  onFlyToRoad: Props['onFlyToRoad'];
  theme: Theme;
}) {
  const max = meta.topRoads[0]?.betweenness ?? 1;
  return (
    <>
      <p className="note">
        Streets ranked by their single most central segment. Scores are relative — they order
        roads by how often shortest paths use them, not by traffic volume.
      </p>
      <ol className="rows">
        {meta.topRoads.map((road, i) => (
          <li key={`${road.name}-${i}`}>
            <button className="row" onClick={() => onFlyToRoad(road)}>
              <span className="rank">{i + 1}</span>
              <span className="name">{road.name}</span>
              <span className="bar">
                <span
                  style={{
                    width: `${(road.betweenness / max) * 100}%`,
                    background: cssRamp(road.betweenness / max, theme),
                  }}
                />
              </span>
            </button>
          </li>
        ))}
      </ol>
    </>
  );
}

function RemovalTable({
  removals,
  selectedRank,
  onSelect,
  theme,
}: {
  removals: RemovalStep[];
  selectedRank: number | null;
  onSelect: Props['onSelect'];
  theme: Theme;
}) {
  const ranked = [...removals].sort((a, b) => b.deltaCost - a.deltaCost);
  const max = ranked[0]?.deltaCost ?? 1;
  return (
    <>
      <p className="note">
        Each street is deleted from the graph, the hierarchy is rebuilt, and 1,000 benchmark
        trips are re-routed. The bar is the extra distance those trips have to travel.
      </p>
      <ol className="rows">
        {ranked.map((step) => (
          <li key={step.rank}>
            <button
              className={step.rank === selectedRank ? 'row selected' : 'row'}
              onClick={() => onSelect(step.rank === selectedRank ? null : step.rank)}
            >
              <span className="rank">{step.rank}</span>
              <span className="name">{step.roadName}</span>
              <span className="value">+{Math.round(step.deltaCost).toLocaleString()} m</span>
              <span className="bar">
                <span
                  style={{
                    width: `${Math.max((step.deltaCost / max) * 100, 1.5)}%`,
                    background: theme === 'dark' ? 'rgb(255,92,42)' : 'rgb(214,58,12)',
                  }}
                />
              </span>
            </button>
          </li>
        ))}
      </ol>
    </>
  );
}

function SpeedTable({ meta }: { meta: Meta }) {
  const rows = [
    ['dijkstra', 'Dijkstra'],
    ['astar', 'A* (haversine)'],
    ['ch', 'Contraction Hierarchies'],
  ] as const;
  const slowest = meta.benchmarks.dijkstra?.overall ?? 1;

  return (
    <>
      <p className="note">
        Mean latency over 1,000 point-to-point queries, split by the degree band of the source
        node. Lower is better.
      </p>
      <table className="speed">
        <thead>
          <tr>
            <th>Algorithm</th>
            <th>deg ≤ 4</th>
            <th>5–9</th>
            <th>≥ 10</th>
            <th>Overall</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([key, label]) => {
            const band = meta.benchmarks[key];
            if (!band) return null;
            return (
              <tr key={key}>
                <td>{label}</td>
                <td>{formatSeconds(band.deg_level_1)}</td>
                <td>{formatSeconds(band.deg_level_2)}</td>
                <td>{formatSeconds(band.deg_level_3)}</td>
                <td className="strong">{formatSeconds(band.overall)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {meta.benchmarks.ch && (
        <p className="note">
          Contraction Hierarchies answers a query{' '}
          <strong>{Math.round(slowest / meta.benchmarks.ch.overall)}×</strong> faster than
          Dijkstra on the same graph.
        </p>
      )}
    </>
  );
}

function Toggle({
  checked,
  onChange,
  label,
  hint,
  swatch,
  disabled,
}: {
  checked: boolean;
  onChange: () => void;
  label: string;
  hint?: string;
  swatch?: React.ReactNode;
  disabled?: boolean;
}) {
  return (
    <label className={disabled ? 'toggle disabled' : 'toggle'}>
      <input type="checkbox" checked={checked} onChange={onChange} disabled={disabled} />
      <span className="toggle-label">
        {label}
        {hint && <em>{hint}</em>}
      </span>
      {swatch}
    </label>
  );
}

function Gradient({ theme }: { theme: Theme }) {
  const stops = Array.from({ length: 6 }, (_, i) => cssRamp(i / 5, theme)).join(', ');
  return <span className="swatch" style={{ background: `linear-gradient(90deg, ${stops})` }} />;
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    </svg>
  );
}
