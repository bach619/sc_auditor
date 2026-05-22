import { useEffect, useState } from 'react';
import { api } from '../lib/api';

interface GraphNode {
  name: string;
  status: string;
  colour: string;
  latency_ms: number;
  error: string;
  timestamp: string;
}

interface GraphEdge {
  from: string;
  to: string;
}

interface GraphData {
  nodes: Record<string, GraphNode>;
  edges: GraphEdge[];
}

interface MetricsData {
  total_services: number;
  healthy: number;
  degraded: number;
  down: number;
  unknown: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  error_rate: number;
  timestamp: string;
}

interface AlertConfig {
  latencyThreshold: number;
  errorRateThreshold: number;
  checkInterval: number;
}

const ALERT_CONFIG_KEY = 'vyper-alert-config';

const DEFAULT_ALERT_CONFIG: AlertConfig = {
  latencyThreshold: 500,
  errorRateThreshold: 5,
  checkInterval: 30,
};

function statCardClass(): string {
  return 'rounded-xl p-6 dark:bg-[#1a1a1e] dark:border dark:border-[#27272a] light:bg-white light:border light:border-[#e4e4e7] transition-all duration-200';
}

function tabClass(active: boolean): string {
  return active
    ? 'px-4 py-2 rounded-lg text-sm font-medium dark:bg-vyper-500/20 dark:text-vyper-400 light:bg-vyper-50 light:text-vyper-600 border dark:border-vyper-500/30 light:border-vyper-500/30'
    : 'px-4 py-2 rounded-lg text-sm font-medium dark:text-[#a1a1aa] light:text-[#71717a] hover:dark:bg-[#27272a] hover:light:bg-gray-100 border border-transparent';
}

function nodeColour(colour: string): string {
  switch (colour) {
    case 'green': return 'fill-green-500';
    case 'yellow': return 'fill-yellow-500';
    case 'red': return 'fill-red-500';
    default: return 'fill-gray-400';
  }
}

function nodeStroke(colour: string): string {
  switch (colour) {
    case 'green': return 'stroke-green-400';
    case 'yellow': return 'stroke-yellow-400';
    case 'red': return 'stroke-red-400';
    default: return 'stroke-gray-400';
  }
}

function nodeTextClass(colour: string): string {
  switch (colour) {
    case 'green': return 'text-green-400';
    case 'yellow': return 'text-yellow-400';
    case 'red': return 'text-red-400';
    default: return 'text-gray-400';
  }
}

function computeLayout(nodes: Record<string, GraphNode>, edges: GraphEdge[]) {
  const names = Object.keys(nodes);
  if (names.length === 0) return { positioned: [], width: 800, height: 600 };

  const inDegree: Record<string, number> = {};
  const outEdges: Record<string, string[]> = {};
  for (const n of names) {
    inDegree[n] = 0;
    outEdges[n] = [];
  }
  for (const e of edges) {
    if (inDegree[e.to] !== undefined) {
      inDegree[e.to] = (inDegree[e.to] || 0) + 1;
    }
    if (outEdges[e.from] !== undefined) {
      outEdges[e.from].push(e.to);
    }
  }

  const layers: string[][] = [];
  let queue = names.filter(n => inDegree[n] === 0);
  const visited = new Set<string>();
  while (queue.length > 0) {
    layers.push([...queue]);
    const next: string[] = [];
    for (const n of queue) {
      visited.add(n);
      for (const to of (outEdges[n] || [])) {
        inDegree[to]--;
        if (inDegree[to] === 0 && !visited.has(to)) {
          next.push(to);
        }
      }
    }
    queue = next;
  }

  const remaining = names.filter(n => !visited.has(n));
  if (remaining.length > 0) {
    layers.push(remaining);
  }

  const NODE_W = 160;
  const NODE_H = 50;
  const LAYER_GAP = 100;
  const NODE_GAP = 20;
  const PAD = 40;

  const layerWidth = layers.length * (NODE_W + LAYER_GAP) + PAD;
  const maxNodes = Math.max(...layers.map(l => l.length));
  const layerHeight = maxNodes * (NODE_H + NODE_GAP) + PAD;

  const width = Math.max(800, layerWidth);
  const height = Math.max(600, layerHeight);

  const positioned: Array<{ name: string; x: number; y: number }> = [];

  for (let li = 0; li < layers.length; li++) {
    const layer = layers[li];
    const totalH = layer.length * (NODE_H + NODE_GAP) - NODE_GAP;
    const startY = (height - totalH) / 2;
    const x = PAD + li * (NODE_W + LAYER_GAP);
    for (let ni = 0; ni < layer.length; ni++) {
      const y = startY + ni * (NODE_H + NODE_GAP);
      positioned.push({ name: layer[ni], x, y });
    }
  }

  return { positioned, width, height, NODE_W, NODE_H };
}

function DependencyGraph({ data }: { data: GraphData }) {
  const { nodes, edges } = data;
  const { positioned, width, height, NODE_W, NODE_H } = computeLayout(nodes, edges);
  const posMap = new Map(positioned.map(p => [p.name, p]));

  if (positioned.length === 0) {
    return (
      <div className={statCardClass()}>
        <div className="text-center py-8 text-sm dark:text-[#a1a1aa] light:text-[#71717a]">
          No graph data available.
      </div>
      <div className={`${statCardClass()} mt-4`}>
        <h3 className="text-sm font-semibold mb-3 dark:text-[#f4f4f5] light:text-[#09090b]">Cache Performance</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs dark:text-[#a1a1aa] light:text-[#71717a]">Hits</div>
            <div className="text-lg font-bold text-green-400">--</div>
          </div>
          <div>
            <div className="text-xs dark:text-[#a1a1aa] light:text-[#71717a]">Misses</div>
            <div className="text-lg font-bold text-yellow-400">--</div>
          </div>
          <div>
            <div className="text-xs dark:text-[#a1a1aa] light:text-[#71717a]">Hit Rate</div>
            <div className="text-lg font-bold text-blue-400">--</div>
          </div>
          <div>
            <div className="text-xs dark:text-[#a1a1aa] light:text-[#71717a]">Cache Size</div>
            <div className="text-lg font-bold">--</div>
          </div>
        </div>
      </div>
    </div>
  );
}

  return (
    <div className={`${statCardClass()} overflow-auto`}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="500" className="min-w-[800px]">
        <defs>
          <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" className="fill-gray-500" />
          </marker>
        </defs>

        {edges.map((e, i) => {
          const from = posMap.get(e.from);
          const to = posMap.get(e.to);
          if (!from || !to) return null;
          const x1 = from.x + NODE_W;
          const y1 = from.y + NODE_H / 2;
          const x2 = to.x;
          const y2 = to.y + NODE_H / 2;
          const midX = (x1 + x2) / 2;
          return (
            <path
              key={i}
              d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
              fill="none"
              className="stroke-gray-500"
              strokeWidth="1.5"
              markerEnd="url(#arrowhead)"
            />
          );
        })}

        {positioned.map(p => {
          const node = nodes[p.name];
          if (!node) return null;
          const fill = nodeColour(node.colour);
          const stroke = nodeStroke(node.colour);
          return (
            <g key={p.name}>
              <rect
                x={p.x}
                y={p.y}
                width={NODE_W}
                height={NODE_H}
                rx="6"
                className={`${fill} ${stroke} stroke-2 fill-opacity-10`}
              />
              <text
                x={p.x + NODE_W / 2}
                y={p.y + NODE_H / 2 - 5}
                textAnchor="middle"
                dominantBaseline="middle"
                className={`text-[11px] ${nodeTextClass(node.colour)} font-medium`}
                fill="currentColor"
              >
                {p.name}
              </text>
              {node.latency_ms != null && (
                <text
                  x={p.x + NODE_W / 2}
                  y={p.y + NODE_H / 2 + 12}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  className={`text-[10px] ${nodeTextClass(node.colour)}`}
                  fill="currentColor"
                  opacity="0.8"
                >
                  {node.latency_ms}ms
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function MetricsPanel({ data }: { data: MetricsData }) {
  const items = [
    { label: 'Total Services', value: data.total_services },
    { label: 'Healthy', value: data.healthy, colour: 'text-green-400' },
    { label: 'Degraded', value: data.degraded, colour: 'text-yellow-400' },
    { label: 'Down', value: data.down, colour: 'text-red-400' },
    { label: 'Unknown', value: data.unknown, colour: 'text-gray-400' },
  ];

  return (
    <div className={statCardClass()}>
      <h3 className="text-lg font-semibold mb-4 dark:text-[#f4f4f5] light:text-[#09090b]">
        Aggregated Metrics
      </h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
        {items.map(item => (
          <div key={item.label} className="text-center">
            <div className={`text-2xl font-bold ${item.colour || 'dark:text-[#f4f4f5] light:text-[#09090b]'}`}>
              {item.value}
            </div>
            <div className="text-xs dark:text-[#a1a1aa] light:text-[#71717a] mt-1">{item.label}</div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="dark:bg-[#18181b] light:bg-gray-50 rounded-lg p-4">
          <div className="text-sm dark:text-[#a1a1aa] light:text-[#71717a]">Avg Latency</div>
          <div className="text-xl font-bold dark:text-[#f4f4f5] light:text-[#09090b]">
            {data.avg_latency_ms != null ? `${data.avg_latency_ms} ms` : '—'}
          </div>
        </div>
        <div className="dark:bg-[#18181b] light:bg-gray-50 rounded-lg p-4">
          <div className="text-sm dark:text-[#a1a1aa] light:text-[#71717a]">P95 Latency</div>
          <div className="text-xl font-bold dark:text-[#f4f4f5] light:text-[#09090b]">
            {data.p95_latency_ms != null ? `${data.p95_latency_ms} ms` : '—'}
          </div>
        </div>
        <div className="dark:bg-[#18181b] light:bg-gray-50 rounded-lg p-4">
          <div className="text-sm dark:text-[#a1a1aa] light:text-[#71717a]">Error Rate</div>
          <div className={`text-xl font-bold ${(data.error_rate ?? 0) > 5 ? 'text-red-400' : 'text-green-400'}`}>
            {data.error_rate != null ? `${data.error_rate.toFixed(2)}%` : '—'}
          </div>
        </div>
        <div className="dark:bg-[#18181b] light:bg-gray-50 rounded-lg p-4">
          <div className="text-sm dark:text-[#a1a1aa] light:text-[#71717a]">Last Check</div>
          <div className="text-xl font-bold dark:text-[#f4f4f5] light:text-[#09090b] text-sm truncate">
            {data.timestamp ? new Date(data.timestamp).toLocaleString() : '—'}
          </div>
        </div>
      </div>
    </div>
  );
}

function AlertConfigPanel() {
  const [config, setConfig] = useState<AlertConfig>(DEFAULT_ALERT_CONFIG);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(ALERT_CONFIG_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        setConfig({ ...DEFAULT_ALERT_CONFIG, ...parsed });
      }
    } catch {}
  }, []);

  const handleSave = () => {
    localStorage.setItem(ALERT_CONFIG_KEY, JSON.stringify(config));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const inputClass = 'w-full rounded-lg px-3 py-2 text-sm dark:bg-[#18181b] dark:border dark:border-[#27272a] dark:text-[#f4f4f5] light:bg-gray-50 light:border light:border-[#e4e4e7] light:text-[#09090b] focus:outline-none focus:ring-2 focus:ring-vyper-500/50';

  return (
    <div className={statCardClass()}>
      <h3 className="text-lg font-semibold mb-4 dark:text-[#f4f4f5] light:text-[#09090b]">
        Alert Configuration
      </h3>
      <div className="space-y-4 max-w-md">
        <div>
          <label className="block text-sm font-medium dark:text-[#a1a1aa] light:text-[#71717a] mb-1">
            Latency Threshold (ms)
          </label>
          <input
            type="number"
            value={config.latencyThreshold}
            onChange={e => setConfig(c => ({ ...c, latencyThreshold: Number(e.target.value) }))}
            className={inputClass}
            min={0}
          />
        </div>
        <div>
          <label className="block text-sm font-medium dark:text-[#a1a1aa] light:text-[#71717a] mb-1">
            Error Rate Threshold (%)
          </label>
          <input
            type="number"
            value={config.errorRateThreshold}
            onChange={e => setConfig(c => ({ ...c, errorRateThreshold: Number(e.target.value) }))}
            className={inputClass}
            min={0}
            max={100}
          />
        </div>
        <div>
          <label className="block text-sm font-medium dark:text-[#a1a1aa] light:text-[#71717a] mb-1">
            Check Interval (seconds)
          </label>
          <input
            type="number"
            value={config.checkInterval}
            onChange={e => setConfig(c => ({ ...c, checkInterval: Number(e.target.value) }))}
            className={inputClass}
            min={5}
          />
        </div>
        <button
          onClick={handleSave}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-vyper-500 text-white hover:bg-vyper-600 transition-colors"
        >
          {saved ? 'Saved!' : 'Save'}
        </button>
      </div>
    </div>
  );
}

export default function ServiceHealth() {
  const [tab, setTab] = useState<'graph' | 'metrics' | 'alerts'>('graph');
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [metricsData, setMetricsData] = useState<MetricsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError('');
      try {
        const [graphRes, metricsRes] = await Promise.all([
          api.getHealthGraph(),
          api.getHealthMetrics(),
        ]);
        if (!cancelled) {
          setGraphData(graphRes.data || null);
          setMetricsData(metricsRes.data || null);
        }
      } catch (err: any) {
        if (!cancelled) setError(err?.message || 'Failed to fetch health data');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    const interval = setInterval(load, 30000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Service Health</h2>
        <p className="dark:text-[#a1a1aa] light:text-[#71717a] mt-1">
          Real-time health status for all Vyper microservices
        </p>
      </div>

      <div className="flex gap-2">
        <button onClick={() => setTab('graph')} className={tabClass(tab === 'graph')}>
          Dependency Graph
        </button>
        <button onClick={() => setTab('metrics')} className={tabClass(tab === 'metrics')}>
          Metrics
        </button>
        <button onClick={() => setTab('alerts')} className={tabClass(tab === 'alerts')}>
          Alert Config
        </button>
      </div>

      {error && (
        <div className="rounded-xl p-4 bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
          <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className={statCardClass()}>
          <div className="text-center py-8 text-sm dark:text-[#a1a1aa] light:text-[#71717a]">
            Loading service health...
          </div>
        </div>
      ) : tab === 'graph' ? (
        graphData ? <DependencyGraph data={graphData} /> : (
          <div className={statCardClass()}>
            <div className="text-center py-8 text-sm dark:text-[#a1a1aa] light:text-[#71717a]">
              No graph data available.
            </div>
          </div>
        )
      ) : tab === 'metrics' ? (
        metricsData ? <MetricsPanel data={metricsData} /> : (
          <div className={statCardClass()}>
            <div className="text-center py-8 text-sm dark:text-[#a1a1aa] light:text-[#71717a]">
              No metrics data available.
            </div>
          </div>
        )
      ) : (
        <AlertConfigPanel />
      )}
    </div>
  );
}
