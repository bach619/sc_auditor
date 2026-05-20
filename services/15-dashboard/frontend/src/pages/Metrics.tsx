// FILE: Metrics.tsx
import { useState, useEffect } from 'react';
import { api } from '../lib/api';
import type { MetricsSummary } from '../lib/api';

function formatPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatCount(value: number): string {
  return value.toLocaleString();
}

function StatCard({
  label,
  value,
  color,
  sub,
}: {
  label: string;
  value: string | number;
  color: string;
  sub?: string;
}) {
  return (
    <div className="rounded-lg border dark:border-[#27272a] light:border-[#e4e4e7] dark:bg-[#18181b] light:bg-white p-4 space-y-1">
      <div className="text-xs dark:text-[#a1a1aa] light:text-[#71717a]">{label}</div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      {sub && <div className="text-xs dark:text-[#a1a1aa] light:text-[#71717a]">{sub}</div>}
    </div>
  );
}

interface PerToolEntry {
  tool: string;
  audits: number;
  findings: number;
  tp: number;
  fp: number;
  precision?: number;
  recall?: number;
}

export default function Metrics() {
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .getMetrics()
      .then((res) => {
        setMetrics(res.data ?? null);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load metrics');
        setMetrics(null);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="flex items-center gap-3 text-sm dark:text-[#a1a1aa] light:text-[#71717a]">
          <svg className="animate-spin h-5 w-5 text-vyper-400" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading metrics...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border dark:border-red-500/30 light:border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-400 dark:text-red-400 light:text-red-600">
        {error}
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-sm dark:text-[#a1a1aa] light:text-[#71717a]">
        <svg className="w-12 h-12 mb-3 opacity-40" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M2 11a1 1 0 011-1h2a1 1 0 011 1v5a1 1 0 01-1 1H3a1 1 0 01-1-1v-5zM8 7a1 1 0 011-1h2a1 1 0 011 1v9a1 1 0 01-1 1H9a1 1 0 01-1-1V7zM14 4a1 1 0 011-1h2a1 1 0 011 1v12a1 1 0 01-1 1h-2a1 1 0 01-1-1V4z" clipRule="evenodd" />
        </svg>
        No metrics available yet.
      </div>
    );
  }

  // Parse per_tool data if available
  const perToolEntries: PerToolEntry[] = metrics.per_tool
    ? Object.entries(metrics.per_tool).map(([tool, data]: [string, any]) => ({
        tool,
        audits: data.audits ?? 0,
        findings: data.findings ?? 0,
        tp: data.tp ?? 0,
        fp: data.fp ?? 0,
        precision: data.precision,
        recall: data.recall,
      }))
    : [];

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold dark:text-[#f4f4f5] light:text-[#09090b]">Metrics</h2>

      {/* Overview Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard label="Total Audits" value={formatCount(metrics.total_audits)} color="dark:text-[#f4f4f5] light:text-[#09090b]" />
        <StatCard label="Total Findings" value={formatCount(metrics.total_findings)} color="dark:text-[#f4f4f5] light:text-[#09090b]" />
        <StatCard label="Critical" value={formatCount(metrics.critical_findings)} color="text-red-400" />
        <StatCard label="High" value={formatCount(metrics.high_findings)} color="text-orange-400" />
        <StatCard label="Medium" value={formatCount(metrics.medium_findings)} color="text-yellow-400" />
        <StatCard label="Low" value={formatCount(metrics.low_findings)} color="text-blue-400" />
      </div>

      {/* TP/FP/FN */}
      <div className="rounded-lg border dark:border-[#27272a] light:border-[#e4e4e7] dark:bg-[#18181b] light:bg-white p-4">
        <h3 className="text-sm font-semibold dark:text-[#f4f4f5] light:text-[#09090b] mb-3">Classification Breakdown</h3>
        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-1">
            <div className="text-xs dark:text-[#a1a1aa] light:text-[#71717a]">True Positives</div>
            <div className="text-xl font-bold text-green-400">{formatCount(metrics.true_positives)}</div>
          </div>
          <div className="space-y-1">
            <div className="text-xs dark:text-[#a1a1aa] light:text-[#71717a]">False Positives</div>
            <div className="text-xl font-bold text-red-400">{formatCount(metrics.false_positives)}</div>
          </div>
          <div className="space-y-1">
            <div className="text-xs dark:text-[#a1a1aa] light:text-[#71717a]">Not Classified</div>
            <div className="text-xl font-bold dark:text-[#a1a1aa] light:text-[#71717a]">
              {formatCount(Math.max(0, metrics.total_findings - metrics.true_positives - metrics.false_positives))}
            </div>
          </div>
        </div>
      </div>

      {/* True Positive Rate */}
      <div className="rounded-lg border dark:border-[#27272a] light:border-[#e4e4e7] dark:bg-[#18181b] light:bg-white p-4">
        <div className="flex items-center gap-4">
          <div>
            <div className="text-xs dark:text-[#a1a1aa] light:text-[#71717a]">True Positive Rate</div>
            <div className="text-3xl font-bold text-vyper-400">{formatPct(metrics.true_positive_rate)}</div>
          </div>
          <div className="flex-1 h-2 rounded-full dark:bg-[#27272a] light:bg-[#e4e4e7] overflow-hidden">
            <div
              className="h-full rounded-full bg-vyper-500 transition-all duration-500"
              style={{ width: `${Math.min(metrics.true_positive_rate * 100, 100)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Precision / Recall / F1 */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <StatCard
          label="Precision"
          value={formatPct(metrics.precision)}
          color="text-vyper-300"
          sub={`${formatCount(metrics.true_positives)} TP / ${formatCount(metrics.true_positives + metrics.false_positives)} total`}
        />
        <StatCard
          label="Recall"
          value={formatPct(metrics.recall)}
          color="text-vyper-300"
          sub="True positives vs actual positives"
        />
        <StatCard
          label="F1 Score"
          value={formatPct(metrics.f1_score)}
          color="text-vyper-400"
          sub="Harmonic mean of precision & recall"
        />
      </div>

      {/* Per-Tool Breakdown */}
      {perToolEntries.length > 0 && (
        <div className="rounded-lg border dark:border-[#27272a] light:border-[#e4e4e7] dark:bg-[#18181b] light:bg-white p-4">
          <h3 className="text-sm font-semibold dark:text-[#f4f4f5] light:text-[#09090b] mb-3">Per-Tool Breakdown</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="dark:border-b dark:border-[#27272a] light:border-b light:border-[#e4e4e7]">
                  <th className="text-left pb-2 font-medium dark:text-[#a1a1aa] light:text-[#71717a]">Tool</th>
                  <th className="text-right pb-2 font-medium dark:text-[#a1a1aa] light:text-[#71717a]">Audits</th>
                  <th className="text-right pb-2 font-medium dark:text-[#a1a1aa] light:text-[#71717a]">Findings</th>
                  <th className="text-right pb-2 font-medium dark:text-[#a1a1aa] light:text-[#71717a]">TP</th>
                  <th className="text-right pb-2 font-medium dark:text-[#a1a1aa] light:text-[#71717a]">FP</th>
                  {perToolEntries.some((e) => e.precision !== undefined) && (
                    <th className="text-right pb-2 font-medium dark:text-[#a1a1aa] light:text-[#71717a]">Precision</th>
                  )}
                  {perToolEntries.some((e) => e.recall !== undefined) && (
                    <th className="text-right pb-2 font-medium dark:text-[#a1a1aa] light:text-[#71717a]">Recall</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {perToolEntries.map((entry) => (
                  <tr key={entry.tool} className="dark:border-b dark:border-[#27272a]/50 light:border-b light:border-[#e4e4e7]/50">
                    <td className="py-2 dark:text-[#f4f4f5] light:text-[#09090b] font-medium">{entry.tool}</td>
                    <td className="py-2 text-right font-mono dark:text-[#a1a1aa] light:text-[#71717a]">{entry.audits}</td>
                    <td className="py-2 text-right font-mono dark:text-[#a1a1aa] light:text-[#71717a]">{entry.findings}</td>
                    <td className="py-2 text-right font-mono text-green-400">{entry.tp}</td>
                    <td className="py-2 text-right font-mono text-red-400">{entry.fp}</td>
                    {perToolEntries.some((e) => e.precision !== undefined) && (
                      <td className="py-2 text-right font-mono dark:text-[#f4f4f5] light:text-[#09090b]">
                        {entry.precision !== undefined ? formatPct(entry.precision) : '—'}
                      </td>
                    )}
                    {perToolEntries.some((e) => e.recall !== undefined) && (
                      <td className="py-2 text-right font-mono dark:text-[#f4f4f5] light:text-[#09090b]">
                        {entry.recall !== undefined ? formatPct(entry.recall) : '—'}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

