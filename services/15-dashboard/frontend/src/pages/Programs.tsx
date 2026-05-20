// FILE: Programs.tsx
import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import type { Program } from '../lib/api';

function statusBadge(status?: string) {
  const base = 'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium';
  const colors: Record<string, string> = {
    active: 'bg-green-500/10 text-green-400 dark:text-green-400 light:text-green-600',
    inactive: 'bg-gray-500/10 text-gray-400 dark:text-gray-400 light:text-gray-600',
    paused: 'bg-yellow-500/10 text-yellow-400 dark:text-yellow-400 light:text-yellow-600',
  };
  return `${base} ${colors[status?.toLowerCase() || ''] || 'bg-gray-500/10 text-gray-400'}`;
}

export default function Programs() {
  const navigate = useNavigate();
  const [programs, setPrograms] = useState<Program[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .getPrograms()
      .then((res) => {
        setPrograms(res.data ?? []);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load programs');
        setPrograms([]);
      })
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    if (!search.trim()) return programs;
    const q = search.toLowerCase();
    return programs.filter(
      (p) =>
        p.name?.toLowerCase().includes(q) ||
        p.slug?.toLowerCase().includes(q) ||
        p.chains?.some((c) => c.toLowerCase().includes(q)),
    );
  }, [programs, search]);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h2 className="text-lg font-semibold dark:text-[#f4f4f5] light:text-[#09090b]">Programs</h2>
        <input
          type="text"
          placeholder="Search programs..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="px-3 py-1.5 rounded-lg text-sm border dark:bg-[#18181b] dark:border-[#27272a] dark:text-[#f4f4f5] dark:placeholder-[#52525b] light:bg-white light:border-[#e4e4e7] light:text-[#09090b] light:placeholder-[#a1a1aa] focus:outline-none focus:ring-2 focus:ring-vyper-500/40 w-56"
        />
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="flex items-center gap-3 text-sm dark:text-[#a1a1aa] light:text-[#71717a]">
            <svg className="animate-spin h-5 w-5 text-vyper-400" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Loading programs...
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
            <path fillRule="evenodd" d="M5 3a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2V5a2 2 0 00-2-2H5zM5 11a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2v-2a2 2 0 00-2-2H5zM11 5a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V5zM11 13a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" clipRule="evenodd" />
          </svg>
          {search ? 'No programs match your search.' : 'No programs configured yet.'}
        </div>
      )}

      {/* Grid */}
      {!loading && !error && filtered.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((program) => (
            <div
              key={program.slug}
              onClick={() => navigate(`/programs/${program.slug}`)}
              className="rounded-lg border dark:border-[#27272a] light:border-[#e4e4e7] dark:bg-[#18181b] light:bg-white p-4 cursor-pointer hover:dark:border-vyper-500/30 hover:light:border-vyper-500/30 transition-colors space-y-3"
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-sm font-semibold dark:text-[#f4f4f5] light:text-[#09090b] leading-tight">
                  {program.name || program.slug}
                </h3>
                <span className={statusBadge(program.status)}>
                  {program.status || 'unknown'}
                </span>
              </div>

              <p className="text-xs font-mono dark:text-[#a1a1aa] light:text-[#71717a]">
                {program.slug}
              </p>

              {program.max_bounty && (
                <div className="text-sm">
                  <span className="text-xs dark:text-[#a1a1aa] light:text-[#71717a]">Max Bounty: </span>
                  <span className="font-semibold dark:text-vyper-300 light:text-vyper-600">{program.max_bounty}</span>
                </div>
              )}

              {program.chains && program.chains.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {program.chains.map((chain) => (
                    <span
                      key={chain}
                      className="px-2 py-0.5 rounded text-xs font-mono dark:bg-[#27272a] light:bg-[#e4e4e7] dark:text-[#a1a1aa] light:text-[#71717a]"
                    >
                      {chain}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

