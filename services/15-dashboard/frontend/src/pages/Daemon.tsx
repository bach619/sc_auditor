// FILE: Daemon.tsx
import { useState, useEffect, useRef } from 'react';
import { api } from '../lib/api';
import type { DaemonState } from '../lib/api';

function formatDate(dateStr?: string): string {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

export default function Daemon() {
  const [daemon, setDaemon] = useState<DaemonState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = async (showLoading = false) => {
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const res = await api.getDaemonStatus();
      setDaemon(res.data ?? null);
    } catch (err) {
      if (showLoading) {
        setError(err instanceof Error ? err.message : 'Failed to load daemon status');
      }
      setDaemon(null);
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus(true);
    intervalRef.current = setInterval(() => fetchStatus(false), 5000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  const handleAction = async (action: string, apiFn: () => Promise<any>) => {
    setActionLoading(action);
    try {
      await apiFn();
      await fetchStatus(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action} daemon`);
    } finally {
      setActionLoading(null);
    }
  };

  const status = daemon?.status || 'stopped';
  const isRunning = status === 'running';
  
  const isPaused = status === 'paused';
  const isError = status === 'error';

  const indicatorColor = isRunning
    ? 'bg-green-500 shadow-[0_0_20px_rgba(34,197,94,0.4)]'
    : isPaused
      ? 'bg-yellow-500 shadow-[0_0_20px_rgba(245,158,11,0.4)]'
      : 'bg-red-500 shadow-[0_0_20px_rgba(239,68,68,0.4)]';

  const statusLabel = isRunning ? 'Running' : isPaused ? 'Paused' : isError ? 'Error' : 'Stopped';

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="flex items-center gap-3 text-sm dark:text-[#a1a1aa] light:text-[#71717a]">
          <svg className="animate-spin h-5 w-5 text-vyper-400" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading daemon status...
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <h2 className="text-lg font-semibold dark:text-[#f4f4f5] light:text-[#09090b]">Daemon Control</h2>

      {/* Status Indicator */}
      <div className="rounded-lg border dark:border-[#27272a] light:border-[#e4e4e7] dark:bg-[#18181b] light:bg-white p-6">
        <div className="flex flex-col sm:flex-row items-center gap-6">
          <div className="flex flex-col items-center gap-2">
            <div className={`w-20 h-20 rounded-full ${indicatorColor} flex items-center justify-center`}>
              {isRunning ? (
                <svg className="w-10 h-10 text-white" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
                </svg>
              ) : isPaused ? (
                <svg className="w-10 h-10 text-white" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              ) : (
                <svg className="w-10 h-10 text-white" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clipRule="evenodd" />
                </svg>
              )}
            </div>
            <span className={`text-sm font-semibold ${
              isRunning ? 'text-green-400' : isPaused ? 'text-yellow-400' : 'text-red-400'
            }`}>
              {statusLabel}
            </span>
          </div>

          <div className="flex-1 grid grid-cols-2 gap-4 text-sm w-full">
            <div>
              <div className="text-xs dark:text-[#a1a1aa] light:text-[#71717a]">Contracts Audited</div>
              <div className="text-xl font-bold dark:text-[#f4f4f5] light:text-[#09090b]">
                {daemon?.total_contracts_audited?.toLocaleString() ?? '—'}
              </div>
            </div>
            <div>
              <div className="text-xs dark:text-[#a1a1aa] light:text-[#71717a]">Cycles Completed</div>
              <div className="text-xl font-bold dark:text-[#f4f4f5] light:text-[#09090b]">
                {daemon?.total_cycles_completed?.toLocaleString() ?? '—'}
              </div>
            </div>
            <div>
              <div className="text-xs dark:text-[#a1a1aa] light:text-[#71717a]">Last Run</div>
              <div className="text-sm font-mono dark:text-[#f4f4f5] light:text-[#09090b]">
                {formatDate(daemon?.last_run_at)}
              </div>
            </div>
            <div>
              <div className="text-xs dark:text-[#a1a1aa] light:text-[#71717a]">Next Run</div>
              <div className="text-sm font-mono dark:text-[#f4f4f5] light:text-[#09090b]">
                {formatDate(daemon?.next_run_at)}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border dark:border-red-500/30 light:border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-400 dark:text-red-400 light:text-red-600">
          {error}
        </div>
      )}

      {/* Last Error */}
      {daemon?.last_error && (
        <div className="rounded-lg border dark:border-red-500/30 light:border-red-500/30 bg-red-500/5 px-4 py-3">
          <div className="text-xs font-medium text-red-400 dark:text-red-400 light:text-red-600 mb-1">Last Error</div>
          <div className="text-sm text-red-300 dark:text-red-300 light:text-red-500 font-mono">{daemon.last_error}</div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-3">
        <button
          onClick={() => handleAction('start', () => api.daemonStart())}
          disabled={isRunning || actionLoading !== null}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border dark:border-green-500/30 light:border-green-500/30 bg-green-500/10 text-green-400 dark:text-green-400 light:text-green-600 hover:bg-green-500/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {actionLoading === 'start' ? (
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
            </svg>
          )}
          Start
        </button>

        <button
          onClick={() => handleAction('stop', () => api.daemonStop())}
          disabled={!isRunning || actionLoading !== null}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border dark:border-red-500/30 light:border-red-500/30 bg-red-500/10 text-red-400 dark:text-red-400 light:text-red-600 hover:bg-red-500/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {actionLoading === 'stop' ? (
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clipRule="evenodd" />
            </svg>
          )}
          Stop
        </button>

        <button
          onClick={() => handleAction('sync', () => api.daemonSync())}
          disabled={actionLoading !== null}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border dark:border-vyper-500/30 light:border-vyper-500/30 bg-vyper-500/10 text-vyper-400 dark:text-vyper-400 light:text-vyper-600 hover:bg-vyper-500/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {actionLoading === 'sync' ? (
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clipRule="evenodd" />
            </svg>
          )}
          Sync
        </button>
      </div>
    </div>
  );
}

