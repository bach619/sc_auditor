// FILE: Audits.tsx
import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import type { Audit } from '../lib/api';

const STATUS_OPTIONS = ['all', 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'SCANNING'] as const;
type StatusFilter = (typeof STATUS_OPTIONS)[number];

function statusBadge(status: string) {
  const base = 'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium';
  const colors: Record<string, string> = {
    COMPLETED: 'bg-green-500/10 text-green-400 dark:text-green-400 light:text-green-600',
    RUNNING: 'bg-blue-500/10 text-blue-400 dark:text-blue-400 light:text-blue-600',
    SCANNING: 'bg-purple-500/10 text-purple-400 dark:text-purple-400 light:text-purple-600',
    PENDING: 'bg-yellow-500/10 text-yellow-400 dark:text-yellow-400 light:text-yellow-600',
    FAILED: 'bg-red-500/10 text-red-400 dark:text-red-400 light:text-red-600',
  };
  return `${base} ${colors[status] || 'bg-gray-500/10 text-gray-400'}`;
}

function formatDuration(seconds?: number): string {
  if (!seconds && seconds !== 0) return '—';
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

export default function Audits() {
  const navigate = useNavigate();
  const [audits, setAudits] = useState<Audit[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');

  const fetchAudits = async (status?: string) => {
    setLoading(true);
    setError(null);
    try {
      const params = status && status !== 'all' ? { state: status } : undefined;
      const res = await api.getAudits(params);
      setAudits(res.data ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load audits');
      setAudits([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAudits(statusFilter === 'all' ? undefined : statusFilter);
  }, [statusFilter]);

  const filtered = useMemo(() => {
    if (!search.trim()) return audits;
    const q = search.toLowerCase();
    return audits.filter(
      (a) =>
        a.audit_id?.toLowerCase().includes(q) ||
        a.program?.toLowerCase().includes(q) ||
        a.chain?.toLowerCase().includes(q) ||
        a.contract?.toLowerCase().includes(q),
    );
  }, [audits, search]);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h2 className="text-lg font-semibold dark:text-[#f4f4f5] light:text-[#09090b]">Audits</h2>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Search audits..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="px-3 py-1.5 rounded-lg text-sm border dark:bg-[#18181b] dark:border-[#27272a] dark:text-[#f4f4f5] dark:placeholder-[#52525b] light:bg-white light:border-[#e4e4e7] light:text-[#09090b] light:placeholder-[#a1a1aa] focus:outline-none focus:ring-2 focus:ring-vyper-500/40 w-48"
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            className="px-3 py-1.5 rounded-lg text-sm border dark:bg-[#18181b] dark:border-[#27272a] dark:text-[#f4f4f5] light:bg-white light:border-[#e4e4e7] light:text-[#09090b] focus:outline-none focus:ring-2 focus:ring-vyper-500/40"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>{s === 'all' ? 'All Status' : s}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="flex items-center gap-3 text-sm dark:text-[#a1a1aa] light:text-[#71717a]">
            <svg className="animate-spin h-5 w-5 text-vyper-400" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Loading audits...
          </div>
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="rounded-lg border dark:border-red-500/30 light:border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-400 dark:text-red-400 light:text-red-600">
          {error}
        </div>
      )}

      {/* Empty */}
      {!loading && !error && filtered.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-sm dark:text-[#a1a1aa] light:text-[#71717a]">
          <svg className="w-12 h-12 mb-3 opacity-40" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
          </svg>
          {search || statusFilter !== 'all' ? 'No audits match your filters.' : 'No audits yet. Submit your first contract to audit.'}
        </div>
      )}

      {/* Table */}
      {!loading && !error && filtered.length > 0 && (
        <div className="overflow-x-auto rounded-lg border dark:border-[#27272a] light:border-[#e4e4e7]">
          <table className="w-full text-sm">
            <thead className="dark:bg-[#18181b] light:bg-[#f4f4f5]">
              <tr>
                <th className="text-left px-4 py-3 font-medium dark:text-[#a1a1aa] light:text-[#71717a]">Audit ID</th>
                <th className="text-left px-4 py-3 font-medium dark:text-[#a1a1aa] light:text-[#71717a]">Program</th>
                <th className="text-left px-4 py-3 font-medium dark:text-[#a1a1aa] light:text-[#71717a]">Chain</th>
                <th className="text-left px-4 py-3 font-medium dark:text-[#a1a1aa] light:text-[#71717a]">Status</th>
                <th className="text-right px-4 py-3 font-medium dark:text-[#a1a1aa] light:text-[#71717a]">Findings</th>
                <th className="text-right px-4 py-3 font-medium dark:text-[#a1a1aa] light:text-[#71717a]">Duration</th>
                <th className="text-right px-4 py-3 font-medium dark:text-[#a1a1aa] light:text-[#71717a]">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-[#27272a] light:divide-[#e4e4e7]">
              {filtered.map((audit) => (
                <tr
                  key={audit.audit_id}
                  onClick={() => navigate(`/audits/${audit.audit_id}`)}
                  className="cursor-pointer dark:hover:bg-[#18181b] light:hover:bg-[#f4f4f5] transition-colors"
                >
                  <td className="px-4 py-3 font-mono text-xs dark:text-[#f4f4f5] light:text-[#09090b]">
                    {audit.audit_id?.slice(0, 8) || '—'}
                  </td>
                  <td className="px-4 py-3 dark:text-[#f4f4f5] light:text-[#09090b]">
                    {audit.program || '—'}
                  </td>
                  <td className="px-4 py-3">
                    {audit.chain ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono dark:bg-[#27272a] light:bg-[#e4e4e7] dark:text-[#a1a1aa] light:text-[#71717a]">
                        {audit.chain}
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <span className={statusBadge(audit.state)}>{audit.state}</span>
                  </td>
                  <td className="px-4 py-3 text-right dark:text-[#f4f4f5] light:text-[#09090b] font-mono">
                    {audit.findings_count ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-xs dark:text-[#a1a1aa] light:text-[#71717a]">
                    {formatDuration(audit.duration_seconds)}
                  </td>
                  <td className="px-4 py-3 text-right text-xs dark:text-[#a1a1aa] light:text-[#71717a] whitespace-nowrap">
                    {formatDate(audit.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

