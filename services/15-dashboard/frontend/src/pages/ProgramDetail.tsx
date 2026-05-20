// FILE: ProgramDetail.tsx
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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

export default function ProgramDetail() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [program, setProgram] = useState<Program | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    setLoading(true);
    setError(null);
    api
      .getProgram(slug)
      .then((res) => {
        setProgram(res.data ?? null);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load program');
        setProgram(null);
      })
      .finally(() => setLoading(false));
  }, [slug]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="flex items-center gap-3 text-sm dark:text-[#a1a1aa] light:text-[#71717a]">
          <svg className="animate-spin h-5 w-5 text-vyper-400" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading program...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => navigate('/programs')}
          className="inline-flex items-center gap-1.5 text-sm dark:text-vyper-400 light:text-vyper-600 hover:underline"
        >
          <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
          </svg>
          Back to Programs
        </button>
        <div className="rounded-lg border dark:border-red-500/30 light:border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-400 dark:text-red-400 light:text-red-600">
          {error}
        </div>
      </div>
    );
  }

  if (!program) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => navigate('/programs')}
          className="inline-flex items-center gap-1.5 text-sm dark:text-vyper-400 light:text-vyper-600 hover:underline"
        >
          <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
          </svg>
          Back to Programs
        </button>
        <div className="rounded-lg border dark:border-[#27272a] light:border-[#e4e4e7] px-4 py-8 text-center text-sm dark:text-[#a1a1aa] light:text-[#71717a]">
          Program not found.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Back */}
      <button
        onClick={() => navigate('/programs')}
        className="inline-flex items-center gap-1.5 text-sm dark:text-vyper-400 light:text-vyper-600 hover:underline"
      >
        <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
        </svg>
        Back to Programs
      </button>

      {/* Program Card */}
      <div className="rounded-lg border dark:border-[#27272a] light:border-[#e4e4e7] dark:bg-[#18181b] light:bg-white p-5 space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold dark:text-[#f4f4f5] light:text-[#09090b]">
              {program.name || program.slug}
            </h2>
            <p className="mt-0.5 font-mono text-xs dark:text-[#a1a1aa] light:text-[#71717a]">{program.slug}</p>
          </div>
          <span className={statusBadge(program.status)}>
            {program.status || 'unknown'}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          {program.max_bounty && (
            <div>
              <span className="block text-xs dark:text-[#a1a1aa] light:text-[#71717a] mb-0.5">Max Bounty</span>
              <span className="font-semibold dark:text-vyper-300 light:text-vyper-600">{program.max_bounty}</span>
            </div>
          )}
          <div>
            <span className="block text-xs dark:text-[#a1a1aa] light:text-[#71717a] mb-0.5">Status</span>
            <span className="capitalize dark:text-[#f4f4f5] light:text-[#09090b]">{program.status || 'unknown'}</span>
          </div>
        </div>

        {program.chains && program.chains.length > 0 && (
          <div>
            <span className="block text-xs dark:text-[#a1a1aa] light:text-[#71717a] mb-2">Supported Chains</span>
            <div className="flex flex-wrap gap-1.5">
              {program.chains.map((chain) => (
                <span
                  key={chain}
                  className="px-2.5 py-1 rounded text-xs font-mono dark:bg-[#27272a] light:bg-[#e4e4e7] dark:text-[#a1a1aa] light:text-[#71717a]"
                >
                  {chain}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Audit History Placeholder */}
      <div className="rounded-lg border dark:border-[#27272a] light:border-[#e4e4e7] dark:bg-[#18181b] light:bg-white p-5">
        <h3 className="text-sm font-semibold dark:text-[#f4f4f5] light:text-[#09090b] mb-3">Audit History</h3>
        <p className="text-sm dark:text-[#a1a1aa] light:text-[#71717a]">
          Audit history for this program will appear here once audits are completed.
        </p>
      </div>
    </div>
  );
}

