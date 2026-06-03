import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Card } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Select } from '../components/ui/select'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { StatusBadge } from '../components/StatusBadge'
import { LoadingState } from '../components/LoadingState'
import { EmptyState } from '../components/EmptyState'
import { ErrorBanner } from '../components/ErrorBanner'
import { AuditErrorAlert } from '../components/AuditErrorAlert'
import { PageHeader } from '../components/PageHeader'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../components/ui/dialog'
import { formatDate } from '../lib/utils'
import { Bot, Play, Loader2, Users, CheckCircle2 } from 'lucide-react'

interface TeamMember {
  name: string
  role: string
  skills: string[]
  status?: string
}

interface Session {
  session_id: string
  status: string
  created_at: string
  goal?: string
  task_type?: string
}

export default function Agent() {
  const [team, setTeam] = useState<TeamMember[]>([])
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [genLoading, setGenLoading] = useState(false)
  const [genError, setGenError] = useState('')
  const [genSuccess, setGenSuccess] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [teamRes, sessionsRes] = await Promise.all([
          api.getTeamStructure().catch(() => ({ data: [] })),
          api.getTeamSessions({ limit: 20 }).catch(() => ({ data: [] })),
        ])
        if (!cancelled) {
          setTeam(Array.isArray(teamRes.data) ? teamRes.data : [])
          setSessions(Array.isArray(sessionsRes.data) ? sessionsRes.data : [])
        }
      } catch {}
      if (!cancelled) setLoading(false)
    }
    load()
    return () => { cancelled = true }
  }, [])

  async function handleRunAudit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setGenLoading(true)
    setGenError('')
    setGenSuccess('')
    const form = e.currentTarget
    const data = new FormData(form)
    const address = String(data.get('address') || '')
    const chain = String(data.get('chain') || 'ethereum')
    const goal = String(data.get('goal') || '')
    try {
      await api.runTeamAudit({
        task_type: 'full_audit',
        input_data: { address, chain },
        goal: goal || undefined,
        max_delegations: 15,
      })
      // Refresh sessions before closing modal
      try {
        const res = await api.getTeamSessions({ limit: 20 })
        setSessions(Array.isArray(res.data) ? res.data : [])
      } catch { /* refresh best-effort */ }
      setModalOpen(false)
      setGenSuccess(`Team audit started for ${address.slice(0, 10)}... on ${chain}`)
    } catch (err: any) {
      setGenError(err?.message || 'Failed to run audit')
    } finally { setGenLoading(false) }
  }

  if (loading) return <LoadingState message="Loading agent data..." />

  return (
    <div className="space-y-6">
      <PageHeader title="Agent" description="AI agent team — autonomous smart contract auditing" />

      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
      {genSuccess && (
        <div className="rounded-xl p-4 bg-green-500/10 border border-green-500/20 text-green-400 text-sm flex items-start gap-2">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span className="flex-1">{genSuccess}</span>
          <button onClick={() => setGenSuccess('')} className="text-green-400/70 hover:text-green-400 transition-colors">
            ✕
          </button>
        </div>
      )}

      {/* Team Structure */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold dark:text-[#d4d4dc] light:text-[#09090b] flex items-center gap-2">
            <Users className="w-4 h-4 text-vyper-400" /> Agent Team
          </h3>
          <Button onClick={() => { setModalOpen(true); setGenError('') }}>
            <Play className="w-4 h-4" /> Run Audit
          </Button>
        </div>
        {team.length === 0 ? (
          <p className="text-sm dark:text-[#68687a] text-center py-4">No team data available.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {team.map((m) => (
              <div key={m.name} className="dark:bg-[#0a0a12] light:bg-gray-50 rounded-lg p-4 border dark:border-[#1a1a28] light:border-[#e4e4e7]">
                <div className="flex items-center gap-3 mb-2">
                  <Bot className="w-5 h-5 text-vyper-400" />
                  <div>
                    <div className="text-sm font-medium dark:text-[#d4d4dc]">{m.name}</div>
                    <div className="text-xs dark:text-[#68687a]">{m.role}</div>
                  </div>
                </div>
                <div className="flex flex-wrap gap-1">
                  {m.skills?.map((s) => (
                    <Badge key={s} variant="secondary" className="text-[10px]">{s}</Badge>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Session History */}
      <Card>
        <h3 className="font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b]">Session History</h3>
        {sessions.length === 0 ? (
          <EmptyState message="No agent sessions yet." action={{ label: 'Run Audit', onClick: () => setModalOpen(true) }} />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Session ID</TableHead>
                <TableHead>Goal</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sessions.map((s) => (
                <TableRow key={s.session_id}>
                  <TableCell className="font-mono text-xs">{s.session_id.slice(0, 12)}...</TableCell>
                  <TableCell className="max-w-[200px] truncate">{s.goal || s.task_type || '—'}</TableCell>
                  <TableCell><StatusBadge status={s.status} /></TableCell>
                  <TableCell className="text-xs dark:text-[#68687a]">{formatDate(s.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      {/* Run Audit Modal */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Run Team Audit</DialogTitle>
            <DialogDescription>Deploy the agent team to audit a smart contract.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleRunAudit}>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Contract Address</label>
                <Input name="address" placeholder="0x..." required className="font-mono text-xs" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Chain</label>
                <Select name="chain" required>
                  <option value="ethereum">Ethereum</option>
                  <option value="bsc">BSC</option>
                  <option value="polygon">Polygon</option>
                  <option value="arbitrum">Arbitrum</option>
                  <option value="solana">Solana</option>
                </Select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Goal (optional)</label>
                <Input name="goal" placeholder="e.g., Find all reentrancy vulnerabilities" />
              </div>
            </div>
            <AuditErrorAlert message={genError} onDismiss={() => setGenError('')} />
            <DialogFooter className="mt-6">
              <Button type="button" variant="outline" onClick={() => setModalOpen(false)} disabled={genLoading}>Cancel</Button>
              <Button type="submit" disabled={genLoading}>
                {genLoading ? <><Loader2 className="w-4 h-4 animate-spin" /> Running...</> : 'Run Audit'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
