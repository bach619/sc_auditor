// FILE: AuditDetail.tsx
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import type { Audit } from '../lib/api';

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

function formatDate(dateStr?: string): string {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric', month: 'long', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

interface Step {
  name?: string;
  status?: string;
  duration?: number;
  error?: string;
}

export default function AuditDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [audit, setAudit] = useState<Audit | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    api
      .getAudit(id)
      .then((res) => {
        setAudit(res.data ?? null);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load audit');
        setAudit(null);
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="flex items-center gap-3 text-sm dark:text-[#a1a1aa] light:text-[#71717a]">
          <svg className="animate-spin h-5 w-5 text-vyper-400" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading audit...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => navigate('/audits')}
          className="inline-flex items-center gap-1.5 text-sm dark:text-vyper-400 light:text-vyper-600 hover:underline"
        >
          <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
          </svg>
          Back to Audits
        </button>
        <div className="rounded-lg border dark:border-red-500/30 light:border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-400 dark:text-red-400 light:text-red-600">
          {error}
        </div>
      </div>
    );
  }

  if (!audit) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => navigate('/audits')}
          className="inline-flex items-center gap-1.5 text-sm dark:text-vyper-400 light:text-vyper-600 hover:underline"
        >
          <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
          </svg>
          Back to Audits
        </button>
        <div className="rounded-lg border dark:border-[#27272a] light:border-[#e4e4e7] px-4 py-8 text-center text-sm dark:text-[#a1a1aa] light:text-[#71717a]">
          Audit not found.
        </div>
      </div>
    );
  }

  const steps: Step[] = audit.steps ?? [];

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Back */}
      <button
        onClick={() => navigate('/audits')}
        className="inline-flex items-center gap-1.5 text-sm dark:text-vyper-400 light:text-vyper-600 hover:underline"
      >
        <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
        </svg>
        Back to Audits
      </button>

      {/* Header Card */}
      <div className="rounded-lg border dark:border-[#27272a] light:border-[#e4e4e7] dark:bg-[#18181b] light:bg-white p-5 space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold dark:text-[#f4f4f5] light:text-[#09090b]">Audit Details</h2>
            <p className="mt-1 font-mono text-xs dark:text-[#a1a1aa] light:text-[#71717a] break-all">{audit.audit_id}</p>
          </div>
          <span className={statusBadge(audit.state)}>{audit.state}</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
          <div>
            <span className="block text-xs dark:text-[#a1a1aa] light:text-[#71717a] mb-0.5">Program</span>
            <span className="dark:text-[#f4f4f5] light:text-[#09090b]">{audit.program || '—'}</span>
          </div>
          <div>
            <span className="block text-xs dark:text-[#a1a1aa] light:text-[#71717a] mb-0.5">Chain</span>
            <span className="dark:text-[#f4f4f5] light:text-[#09090b]">{audit.chain || '—'}</span>
          </div>
          <div>
            <span className="block text-xs dark:text-[#a1a1aa] light:text-[#71717a] mb-0.5">Contract Address</span>
            <span className="font-mono text-xs dark:text-[#f4f4f5] light:text-[#09090b] break-all">
              {audit.contract || '—'}
            </span>
          </div>
          <div>
            <span className="block text-xs dark:text-[#a1a1aa] light:text-[#71717a] mb-0.5">Priority</span>
            <span className="dark:text-[#f4f4f5] light:text-[#09090b]">
              {audit.priority !== undefined ? `P${audit.priority}` : '—'}
            </span>
          </div>
          <div>
            <span className="block text-xs dark:text-[#a1a1aa] light:text-[#71717a] mb-0.5">Created</span>
            <span className="dark:text-[#f4f4f5] light:text-[#09090b]">{formatDate(audit.created_at)}</span>
          </div>
          <div>
            <span className="block text-xs dark:text-[#a1a1aa] light:text-[#71717a] mb-0.5">Findings</span>
            <span className="dark:text-[#f4f4f5] light:text-[#09090b]">
              {audit.findings_count !== undefined ? (
                <span className="inline-flex items-center gap-2">
                  <span>{audit.findings_count} total</span>
                  {audit.critical_count ? <span className="text-red-400">· {audit.critical_count} critical</span> : null}
                  {audit.high_count ? <span className="text-orange-400">· {audit.high_count} high</span> : null}
                </span>
              ) : '—'}
            </span>
          </div>
        </div>
      </div>

      {/* Error */}
      {audit.error && (
        <div className="rounded-lg border dark:border-red-500/30 light:border-red-500/30 bg-red-500/5 px-4 py-3">
          <div className="text-xs font-medium text-red-400 dark:text-red-400 light:text-red-600 mb-1">Error</div>
          <div className="text-sm text-red-300 dark:text-red-300 light:text-red-500 font-mono">{audit.error}</div>
        </div>
      )}

      {/* Pipeline Steps */}
      {steps.length > 0 && (
        <div className="rounded-lg border dark:border-[#27272a] light:border-[#e4e4e7] dark:bg-[#18181b] light:bg-white p-5">
          <h3 className="text-sm font-semibold dark:text-[#f4f4f5] light:text-[#09090b] mb-4">Pipeline Steps</h3>
          <div className="space-y-0">
            {steps.map((step, i) => {
              const isLast = i === steps.length - 1;
              const isDone = step.status === 'completed' || step.status === 'success';
              const isFailed = step.status === 'failed' || step.status === 'error';
              const isRunning = step.status === 'running' || step.status === 'in_progress';
              return (
                <div key={i} className="relative flex gap-3 pb-4">
                  {/* Connector line */}
                  {!isLast && (
                    <div className="absolute left-[13px] top-6 bottom-0 w-px dark:bg-[#27272a] light:bg-[#e4e4e7]" />
                  )}
                  {/* Icon */}
                  <div className="relative flex-shrink-0">
                    {isDone ? (
                      <div className="w-7 h-7 rounded-full bg-green-500/20 flex items-center justify-center">
                        <svg className="w-3.5 h-3.5 text-green-400" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                      </div>
                    ) : isFailed ? (
                      <div className="w-7 h-7 rounded-full bg-red-500/20 flex items-center justify-center">
                        <svg className="w-3.5 h-3.5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                        </svg>
                      </div>
                    ) : isRunning ? (
                      <div className="w-7 h-7 rounded-full bg-blue-500/20 flex items-center justify-center">
                        <svg className="w-3.5 h-3.5 text-blue-400 animate-spin" viewBox="0 0 24 24" fill="none">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                      </div>
                    ) : (
                      <div className="w-7 h-7 rounded-full dark:bg-[#27272a] light:bg-[#e4e4e7] flex items-center justify-center">
                        <div className="w-2 h-2 rounded-full dark:bg-[#52525b] light:bg-[#a1a1aa]" />
                      </div>
                    )}
                  </div>
                  {/* Content */}
                  <div className="flex-1 min-w-0 pt-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium dark:text-[#f4f4f5] light:text-[#09090b]">
                        {step.name || `Step ${i + 1}`}
                      </span>
                      {step.duration ? (
                        <span className="text-xs font-mono dark:text-[#a1a1aa] light:text-[#71717a]">
                          · {step.duration}s
                        </span>
                      ) : null}
                    </div>
                    {step.error && (
                      <p className="mt-0.5 text-xs text-red-400 dark:text-red-400 light:text-red-600 font-mono">
                        {step.error}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Findings Section Placeholder */}
      <div className="rounded-lg border dark:border-[#27272a] light:border-[#e4e4e7] dark:bg-[#18181b] light:bg-white p-5">
        <h3 className="text-sm font-semibold dark:text-[#f4f4f5] light:text-[#09090b] mb-3">Findings</h3>
        {audit.findings_count && audit.findings_count > 0 ? (
          <p className="text-sm dark:text-[#a1a1aa] light:text-[#71717a]">
            {audit.findings_count} finding{audit.findings_count !== 1 ? 's' : ''} detected.
            {audit.critical_count ? <span className="text-red-400"> {audit.critical_count} critical,</span> : null}
            {audit.high_count ? <span className="text-orange-400"> {audit.high_count} high,</span> : null}
            {audit.medium_count ? <span className="text-yellow-400"> {audit.medium_count} medium,</span> : null}
            {audit.low_count ? <span className="text-blue-400"> {audit.low_count} low.</span> : null}
          </p>
        ) : (
          <p className="text-sm dark:text-[#a1a1aa] light:text-[#71717a]">No findings reported for this audit.</p>
        )}
      </div>
    </div>
  );
}


