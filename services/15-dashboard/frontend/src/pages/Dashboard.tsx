import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type Audit, type DaemonState, type MetricsSummary, type CaseStatsData } from '../lib/api'
import { useSSE } from '../hooks/useSSE'
import { useDaemon } from '../lib/daemon-context'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Select } from '../components/ui/select'
import { StatCard } from '../components/StatCard'
import { StatusBadge } from '../components/StatusBadge'
import { LoadingState } from '../components/LoadingState'
import { ErrorBanner } from '../components/ErrorBanner'
import { PageHeader } from '../components/PageHeader'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../components/ui/dialog'
import { formatDuration, formatDate, shortId } from '../lib/utils'
import { Play, Square, RefreshCw, Loader2 } from 'lucide-react'

const CHAINS = [
  { value: 'ethereum', label: 'Ethereum' },
  { value: 'bsc', label: 'BSC' },
  { value: 'polygon', label: 'Polygon' },
  { value: 'arbitrum', label: 'Arbitrum' },
  { value: 'optimism', label: 'Optimism' },
  { value: 'avalanche', label: 'Avalanche' },
  { value: 'solana', label: 'Solana' },
]

export default function Dashboard() {
  const navigate = useNavigate()
  const { setDaemonStatus } = useDaemon()
  const [audits, setAudits] = useState<Audit[]>([])
  const [auditsLoading, setAuditsLoading] = useState(true)
  const [stats, setStats] = useState<any>(null)
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null)
  const [caseStats, setCaseStats] = useState<CaseStatsData | null>(null)
  const [daemon, setDaemon] = useState<DaemonState>({ status: 'running', total_contracts_audited: 0, total_cycles_completed: 0 })
  const [daemonToggling, setDaemonToggling] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [modalLoading, setModalLoading] = useState(false)
  const [modalError, setModalError] = useState('')
  const [clock, setClock] = useState('')
  const [actionError, setActionError] = useState('')

  useEffect(() => {
    const update = () => setClock(new Date().toLocaleString('en-US', {
      weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    }))
    update()
    const id = setInterval(update, 1000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [auditsRes, statsRes, daemonRes, metricsRes, caseStatsRes] = await Promise.all([
          api.getAudits({ limit: 10 }), api.getStats(), api.getDaemonStatus(),
          api.getMetrics(), api.getCaseStats(),
        ])
        if (cancelled) return
        setAudits(auditsRes.data || [])
        setStats(statsRes.data || null)
        setDaemon(daemonRes.data || { status: 'running', total_contracts_audited: 0, total_cycles_completed: 0 })
        setMetrics(metricsRes.data || null)
        setCaseStats(caseStatsRes.data || null)
      } catch {}
      if (!cancelled) setAuditsLoading(false)
    }
    load()
    return () => { cancelled = true }
  }, [])

  useSSE((msg) => {
    if (msg.event === 'daemon_status' && msg.data) {
      setDaemon((prev) => prev ? { ...prev, status: msg.data.status } : prev)
    }
    if (msg.event === 'audit_complete' || msg.event === 'audit_progress') {
      api.getAudits({ limit: 10 }).then((r) => setAudits(r.data || [])).catch(() => {})
    }
  })

  const daemonIsRunning = daemon?.status === 'running'

  async function handleToggleDaemon() {
    setDaemonToggling(true)
    setActionError('')
    try {
      if (daemonIsRunning) await api.daemonStop()
      else await api.daemonStart()
      const res = await api.getDaemonStatus()
      const newState = res.data || { status: daemonIsRunning ? 'stopped' : 'running', total_contracts_audited: 0, total_cycles_completed: 0 }
      setDaemon(newState)
      setDaemonStatus(newState.status)
    } catch (err: any) {
      setActionError(err?.message || 'Failed to toggle daemon')
    } finally { setDaemonToggling(false) }
  }

  async function handleRunSync() {
    setSyncing(true)
    setActionError('')
    try {
      await api.daemonSync()
      const res = await api.getDaemonStatus()
      setDaemon(res.data || null)
    } catch (err: any) {
      setActionError(err?.message || 'Failed to run sync')
    } finally { setSyncing(false) }
  }

  async function handleStartAudit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setModalLoading(true)
    setModalError('')
    const form = e.currentTarget
    const data = new FormData(form)
    try {
      await api.startAudit({
        chain: String(data.get('chain') || 'ethereum'),
        address: String(data.get('address') || ''),
        program: String(data.get('program') || ''),
        priority: Number(data.get('priority')) || 5,
      })
      setModalOpen(false)
      const [auditsRes, statsRes] = await Promise.all([api.getAudits({ limit: 10 }), api.getStats()])
      setAudits(auditsRes.data || [])
      setStats(statsRes.data || null)
    } catch (err: any) {
      setModalError(err?.message || 'Failed to start audit')
    } finally { setModalLoading(false) }
  }

  const tpRate = metrics?.true_positive_rate ?? 0

  return (
    <div className="space-y-6">
      <PageHeader title="Welcome to Vyper" description={`Smart contract bug hunting platform — ${clock}`} />

      {actionError && <ErrorBanner message={actionError} onDismiss={() => setActionError('')} />}

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Audits" value={stats?.total_audits} subtext="Last 30 days" trend="+12%" />
        <StatCard label="Critical Findings" value={metrics?.critical_findings} subtext="Unresolved" accent accentColor="red" />
        <StatCard label="TP Rate" value={metrics != null ? `${(tpRate * 100).toFixed(1)}%` : '—'} subtext="True Positive Rate" accent accentColor="green" />
        <StatCard label="Daemon Status" value={daemon ? (daemonIsRunning ? 'Running' : 'Stopped') : '—'}
          subtext={daemonIsRunning && daemon?.last_run_at ? `Last run: ${new Date(daemon.last_run_at).toLocaleString()}` : 'Click to toggle'}
          accent accentColor={daemonIsRunning ? 'green' : 'yellow'} />
      </div>

      {/* Quick Actions */}
      <Card>
        <h3 className="font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b]">Quick Actions</h3>
        <div className="flex flex-wrap gap-3">
          <Button onClick={() => { setModalOpen(true); setModalError('') }}>
            <Play className="w-4 h-4" /> Start Audit
          </Button>
          <Button variant="outline" onClick={handleToggleDaemon} disabled={daemonToggling}>
            {daemonToggling
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : daemonIsRunning
                ? <Square className="w-4 h-4" />
                : <Play className="w-4 h-4" />
            }
            {daemonToggling ? 'Toggling...' : daemonIsRunning ? 'Stop Daemon' : 'Start Daemon'}
          </Button>
          <Button variant="outline" onClick={handleRunSync} disabled={syncing}>
            {syncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            {syncing ? 'Syncing...' : 'Run Sync'}
          </Button>
        </div>
      </Card>

      {/* Case Management */}
      {caseStats && (
        <>
          <div className="flex items-center justify-between">
            <h3 className="font-semibold dark:text-[#d4d4dc] light:text-[#09090b]">Case Management</h3>
            <Link to="/scanning" className="text-sm text-vyper-400 hover:text-vyper-300 transition-colors">View all cases →</Link>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Open Cases" value={caseStats.open_cases} />
            <StatCard label="Closed Cases" value={caseStats.closed_cases} />
            <StatCard label="Avg Confidence" value={`${(caseStats.avg_confidence * 100).toFixed(0)}%`} accent accentColor="blue" />
            <StatCard label="Total Bounty" value={`$${caseStats.total_bounty.toLocaleString()}`} accent accentColor="green" />
          </div>

          {caseStats.recent_cases && caseStats.recent_cases.length > 0 && (
            <Card>
              <h3 className="font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b]">Recent Open Cases</h3>
              <div className="space-y-2">
                {caseStats.recent_cases.map((c) => (
                  <Link key={c.case_id} to={`/scanning?case=${c.case_id}`}
                    className="flex items-center justify-between py-2 px-3 rounded-lg dark:bg-[#0a0a12] light:bg-[#f4f4f5] hover:dark:bg-vyper-500/5 transition-colors">
                    <div className="flex items-center gap-3">
                      <span className={`w-2 h-2 rounded-full ${
                        c.severity === 'Critical' ? 'bg-red-500' : c.severity === 'High' ? 'bg-orange-500' :
                        c.severity === 'Medium' ? 'bg-yellow-500' : 'bg-green-500'}`} />
                      <div>
                        <div className="text-sm font-medium dark:text-[#d4d4dc] light:text-[#09090b]">{c.title}</div>
                        <div className="text-xs font-mono dark:text-[#68687a] light:text-[#71717a]">{c.case_id}</div>
                      </div>
                    </div>
                    <div className="text-xs dark:text-[#68687a] light:text-[#71717a]">{(c.confidence * 100).toFixed(0)}% confidence</div>
                  </Link>
                ))}
              </div>
            </Card>
          )}
        </>
      )}

      {/* Recent Audits */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold dark:text-[#d4d4dc] light:text-[#09090b]">Recent Audits</h3>
          <Link to="/scanning" className="text-sm text-vyper-400 hover:text-vyper-300 transition-colors">View all →</Link>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Audit ID</TableHead>
              <TableHead>Program</TableHead>
              <TableHead>Chain</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Findings</TableHead>
              <TableHead className="text-right">Duration</TableHead>
              <TableHead>Date</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {auditsLoading ? (
              <TableRow><TableCell colSpan={7} className="text-center py-8 dark:text-[#68687a]">Loading audits...</TableCell></TableRow>
            ) : audits.length === 0 ? (
              <TableRow><TableCell colSpan={7} className="text-center py-8 dark:text-[#68687a]">No audits yet. Start your first audit!</TableCell></TableRow>
            ) : audits.map((a) => (
              <TableRow key={a.audit_id} onClick={() => navigate(`/scanning?audit=${a.audit_id}`)} className="cursor-pointer">
                <TableCell><span className="font-mono text-xs">{shortId(a.audit_id)}</span></TableCell>
                <TableCell>{a.program || '—'}</TableCell>
                <TableCell>{a.chain || '—'}</TableCell>
                <TableCell><StatusBadge status={a.state || 'PENDING'} /></TableCell>
                <TableCell className="text-right">{a.findings_count ?? '—'}</TableCell>
                <TableCell className="text-right font-mono text-xs">{formatDuration(a.duration_seconds)}</TableCell>
                <TableCell className="text-xs dark:text-[#68687a]">{formatDate(a.created_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {/* Start Audit Modal */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Start New Audit</DialogTitle>
            <DialogDescription>Configure and start a new smart contract audit.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleStartAudit}>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Chain</label>
                <Select name="chain" required>
                  {CHAINS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                </Select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Contract Address</label>
                <Input type="text" name="address" placeholder="0x..." required className="font-mono text-xs" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Program (optional)</label>
                <Input type="text" name="program" placeholder="Immunefi program slug" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Priority (0-10)</label>
                <Input type="number" name="priority" defaultValue={5} min={0} max={10} />
              </div>
            </div>
            {modalError && <p className="mt-3 text-sm text-red-400">{modalError}</p>}
            <DialogFooter className="mt-6">
              <Button type="button" variant="outline" onClick={() => setModalOpen(false)} disabled={modalLoading}>Cancel</Button>
              <Button type="submit" disabled={modalLoading}>
                {modalLoading ? <><Loader2 className="w-4 h-4 animate-spin" /> Starting...</> : 'Start Audit'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
