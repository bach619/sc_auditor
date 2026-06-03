import { useEffect, useRef, useState, useCallback } from 'react'
import { api, type Audit } from '../lib/api'
import { Terminal as TerminalIcon, Activity, Clock, AlertTriangle, CheckCircle, XCircle, Loader2 } from 'lucide-react'

// ── Pipeline stage display names ───────────────────────────────────

const STAGE_NAMES: Record<string, string> = {
  PENDING: 'Queued',
  FETCHING_PROGRAM: 'Fetching program',
  FETCHING_SOURCE: 'Fetching source',
  SCANNING: 'Static analysis',
  INTELLIGENCE_CORRELATION: 'Threat intel',
  AI_ANALYSIS: 'AI analysis',
  CLASSIFYING: 'Classifying',
  EXPLOITING: 'PoC exploit',
  RECLASSIFYING: 'Reclassifying',
  REPORTING: 'Report',
  NOTIFYING: 'Notifying',
  COMPLETED: 'Completed',
  COMPLETED_WITH_WARN: 'Completed ⚠',
  FAILED: 'Failed',
  TIMEOUT: 'Timeout',
  FETCH_FAILED: 'Fetch failed',
  SCAN_FAILED: 'Scan failed',
  AI_FAILED: 'AI failed',
  CLASSIFY_FAILED: 'Classify failed',
  EXPLOIT_FAILED: 'Exploit failed',
  REPORT_FAILED: 'Report failed',
  NOTIFY_FAILED: 'Notify failed',
  INTEL_CORRELATION_FAILED: 'Intel failed',
}

// Total number of active pipeline stages (excluding terminal states)
const ACTIVE_STAGES = [
  'PENDING', 'FETCHING_PROGRAM', 'FETCHING_SOURCE', 'SCANNING',
  'INTELLIGENCE_CORRELATION', 'AI_ANALYSIS', 'CLASSIFYING', 'EXPLOITING',
  'RECLASSIFYING', 'REPORTING', 'NOTIFYING',
]

const TERMINAL_STATES = [
  'COMPLETED', 'COMPLETED_WITH_WARN', 'FAILED', 'TIMEOUT',
  'FETCH_FAILED', 'SCAN_FAILED', 'AI_FAILED', 'CLASSIFY_FAILED',
  'EXPLOIT_FAILED', 'REPORT_FAILED', 'NOTIFY_FAILED',
  'INTEL_CORRELATION_FAILED',
]

function isActive(state: string): boolean {
  return ACTIVE_STAGES.includes(state) || (!TERMINAL_STATES.includes(state) && state !== '')
}

function isFailed(state: string): boolean {
  return state.includes('FAILED') || state === 'TIMEOUT'
}

function isCompleted(state: string): boolean {
  return state === 'COMPLETED' || state === 'COMPLETED_WITH_WARN'
}

function stageColor(state: string): string {
  if (isCompleted(state)) return '#00ff88'
  if (isFailed(state)) return '#ff4444'
  if (state === 'PENDING') return '#ffaa00'
  return '#8080ff'
}

function stageIcon(state: string): string {
  if (isCompleted(state)) return '✓'
  if (isFailed(state)) return '✗'
  if (state === 'PENDING') return '○'
  return '▸'
}

// ── Helpers ────────────────────────────────────────────────────────

function now(): string {
  return new Date().toLocaleTimeString('en-US', { hour12: false })
}

function elapsed(iso: string | undefined): string {
  if (!iso) return '—'
  const ms = Date.now() - new Date(iso).getTime()
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ${s % 60}s`
  const h = Math.floor(m / 60)
  return `${h}h ${m % 60}m`
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n) + '…' : s
}

// ── Terminal Component ─────────────────────────────────────────────

interface TerminalProps {
  className?: string
}

export function Terminal({ className = '' }: TerminalProps) {
  // Audit data
  const [audits, setAudits] = useState<Audit[]>([])
  const [daemonStatus, setDaemonStatus] = useState<string>('unknown')
  const [stats, setStats] = useState<{ total: number; completed: number; failed: number; active: number }>({ total: 0, completed: 0, failed: 0, active: 0 })
  const [lastUpdate, setLastUpdate] = useState<string>(now())
  const [loading, setLoading] = useState(true)

  const scrollRef = useRef<HTMLDivElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // ── Poll audits ──────────────────────────────────────────────────

  const fetchAudits = useCallback(async () => {
    try {
      const [auditsRes, statsRes, dsRes] = await Promise.all([
        api.getAudits({ limit: 50 }).catch(() => ({ data: [] })),
        api.getStats().catch(() => ({ data: {} })),
        api.getDaemonStatus().catch(() => ({ data: {} })),
      ])

      const list = Array.isArray(auditsRes.data) ? auditsRes.data as Audit[] : []
      // Sort: active first, then by created_at descending
      list.sort((a, b) => {
        const aActive = isActive(a.state) ? 0 : 1
        const bActive = isActive(b.state) ? 0 : 1
        if (aActive !== bActive) return aActive - bActive
        return (b.created_at || '').localeCompare(a.created_at || '')
      })
      setAudits(list)

      const st = statsRes.data as any
      setStats({
        total: st?.total_audits || list.length,
        completed: st?.completed || 0,
        failed: st?.failed || 0,
        active: st?.in_progress || list.filter((a: Audit) => isActive(a.state)).length,
      })

      const ds = (dsRes.data as any) || {}
      setDaemonStatus(ds.status || 'unknown')
      setLastUpdate(now())
    } catch { /* silent */ }
    setLoading(false)
  }, [])

  useEffect(() => {
    fetchAudits()
    pollRef.current = setInterval(fetchAudits, 2000)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [fetchAudits])

  // ── SSE connection ───────────────────────────────────────────────

  useEffect(() => {
    const es = new EventSource('/events')

    es.addEventListener('audit_progress', () => {
      // Trigger immediate refresh on any progress event
      fetchAudits()
    })

    es.addEventListener('audit_complete', () => {
      fetchAudits()
    })

    es.addEventListener('daemon_status', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data)
        setDaemonStatus(data.status)
      } catch { /* ignore */ }
    })

    es.onerror = () => { /* auto-reconnect */ }

    return () => es.close()
  }, [fetchAudits])

  // ── Auto-scroll event log ───────────────────────────────────────

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [audits])

  // ── Derived data ─────────────────────────────────────────────────

  const activeAudits = audits.filter(a => isActive(a.state))
  const recentAudits = audits.filter(a => !isActive(a.state)).slice(0, 15)

  // ── Compute stage progress bar ──────────────────────────────────

  function progressPct(state: string): number {
    const idx = ACTIVE_STAGES.indexOf(state)
    if (idx === -1) return isCompleted(state) ? 100 : 0
    return Math.round(((idx + 0.5) / ACTIVE_STAGES.length) * 100)
  }

  // ── Render ───────────────────────────────────────────────────────

  return (
    <div className={`rounded-lg overflow-hidden border dark:border-[#1a1a28] light:border-[#e4e4e7] shadow-2xl ${className}`}>
      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-[#1c1c24] border-b dark:border-[#1a1a28] light:border-[#e4e4e7] select-none">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
          <span className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
          <span className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
        </div>
        <div className="flex-1 text-center text-[11px] text-[#888] font-medium tracking-wide">
          <TerminalIcon className="w-3 h-3 inline mr-1.5 -mt-0.5" />
          vyper — audit monitor
        </div>
        <div className="flex items-center gap-3 text-[10px]">
          <span style={{ color: daemonStatus === 'running' ? '#28c840' : daemonStatus === 'error' ? '#ff5f57' : '#888' }}>
            <span className={`inline-block w-1.5 h-1.5 rounded-full mr-1 ${daemonStatus === 'running' ? 'bg-[#28c840] animate-pulse' : daemonStatus === 'error' ? 'bg-[#ff5f57]' : 'bg-[#888]'}`} />
            daemon: {daemonStatus}
          </span>
          <span className="text-[#68687a]">updated: {lastUpdate}</span>
        </div>
      </div>

      {/* ── Stats Bar ────────────────────────────────────────── */}
      <div className="flex items-center gap-4 px-4 py-2 bg-[#0d0d16] border-b dark:border-[#1a1a28] font-mono text-[11px]">
        <span className="text-[#8080ff]">
          <Activity className="w-3 h-3 inline mr-1 -mt-0.5" />
          {stats.active} active
        </span>
        <span className="text-[#00ff88]">
          <CheckCircle className="w-3 h-3 inline mr-1 -mt-0.5" />
          {stats.completed} done
        </span>
        <span className="text-[#ff4444]">
          <XCircle className="w-3 h-3 inline mr-1 -mt-0.5" />
          {stats.failed} failed
        </span>
        <span className="text-[#888] ml-auto">
          <Clock className="w-3 h-3 inline mr-1 -mt-0.5" />
          {stats.total} total
        </span>
      </div>

      {/* ── Main content area ────────────────────────────────── */}
      <div className="flex flex-col" style={{ backgroundColor: '#0a0a0f' }}>
        {/* Active audits table */}
        {activeAudits.length > 0 && (
          <div className="border-b dark:border-[#1a1a28]">
            <div className="px-4 py-2 text-[10px] text-[#ffaa00] font-mono uppercase tracking-wider">
              ▸ Active Processes
            </div>
            <div className="overflow-x-auto">
              <table className="w-full font-mono text-[12px]">
                <thead>
                  <tr className="text-[#68687a] text-[10px] uppercase">
                    <th className="text-left px-4 py-1.5 font-normal">ID</th>
                    <th className="text-left px-2 py-1.5 font-normal">Contract</th>
                    <th className="text-left px-2 py-1.5 font-normal">Chain</th>
                    <th className="text-left px-2 py-1.5 font-normal">Stage</th>
                    <th className="text-left px-2 py-1.5 font-normal">Progress</th>
                    <th className="text-left px-2 py-1.5 font-normal">Elapsed</th>
                  </tr>
                </thead>
                <tbody>
                  {activeAudits.map((a) => {
                    const pct = progressPct(a.state)
                    const color = stageColor(a.state)
                    return (
                      <tr key={a.audit_id} className="border-t dark:border-[#1a1a28]/50 hover:bg-[#0d0d16]/50">
                        <td className="px-4 py-1.5 text-[#68687a]">{truncate(a.audit_id, 12)}</td>
                        <td className="px-2 py-1.5 text-[#d4d4dc]">{truncate(a.contract || a.program || '—', 20)}</td>
                        <td className="px-2 py-1.5 text-[#68687a]">{a.chain || '—'}</td>
                        <td className="px-2 py-1.5" style={{ color }}>
                          {stageIcon(a.state)} {STAGE_NAMES[a.state] || a.state}
                        </td>
                        <td className="px-2 py-1.5">
                          <div className="flex items-center gap-2">
                            <div className="flex-1 h-1 rounded-full bg-[#1a1a28] overflow-hidden">
                              <div
                                className="h-full rounded-full transition-all duration-500"
                                style={{ width: `${pct}%`, backgroundColor: color }}
                              />
                            </div>
                            <span className="text-[10px] text-[#68687a] w-7 text-right">{pct}%</span>
                          </div>
                        </td>
                        <td className="px-2 py-1.5 text-[#68687a]">{elapsed(a.created_at)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* No active audits */}
        {activeAudits.length === 0 && !loading && (
          <div className="px-4 py-8 text-center text-[#68687a] font-mono text-xs">
            <span className="text-[#00ff88]">✓</span> No active audits — system idle
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div className="px-4 py-8 text-center text-[#68687a] font-mono text-xs">
            <Loader2 className="w-3 h-3 inline animate-spin mr-2" />
            Loading audit data...
          </div>
        )}

        {/* Recent history log */}
        {recentAudits.length > 0 && (
          <div ref={scrollRef} className="max-h-[280px] overflow-y-auto border-t dark:border-[#1a1a28]">
            <div className="px-4 py-2 text-[10px] text-[#68687a] font-mono uppercase tracking-wider sticky top-0 bg-[#0a0a0f]">
              ▸ Event Log
            </div>
            <div className="px-4 pb-3 space-y-0.5 font-mono text-[12px]">
              {recentAudits.map((a) => {
                const color = stageColor(a.state)
                const icon = stageIcon(a.state)
                const name = STAGE_NAMES[a.state] || a.state
                const findings = a.findings_count || 0
                const target = a.contract || a.program || '—'
                return (
                  <div key={a.audit_id} className="flex items-start gap-2 leading-relaxed">
                    <span className="text-[#68687a] shrink-0 text-[11px]">
                      [{a.created_at ? new Date(a.created_at).toLocaleTimeString('en-US', { hour12: false }) : '--:--:--'}]
                    </span>
                    <span style={{ color }} className="shrink-0">{icon}</span>
                    <span style={{ color }}>{name}</span>
                    <span className="text-[#68687a]">
                      [{truncate(a.audit_id, 10)}]
                    </span>
                    <span className="text-[#d4d4dc]">{target}</span>
                    {findings > 0 && (
                      <span style={{ color: findings > 0 ? '#ffaa00' : '#68687a' }}>
                        ({findings} finding{findings !== 1 ? 's' : ''})
                      </span>
                    )}
                    {a.error && (
                      <span className="text-[#ff4444] truncate max-w-[200px]">{a.error}</span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* ── Footer status bar ────────────────────────────────── */}
      <div className="flex items-center gap-3 px-4 py-1.5 bg-[#0d0d16] border-t dark:border-[#1a1a28] font-mono text-[10px] text-[#68687a]">
        <span>poll: 2s</span>
        <span className="text-[#3a3a4a]">|</span>
        <span>sse: {daemonStatus !== 'unknown' ? 'connected' : 'connecting…'}</span>
        <span className="ml-auto">vyper v4.0.0</span>
      </div>
    </div>
  )
}

export { STAGE_NAMES }
