import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Card } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { StatusBadge } from '../components/StatusBadge'
import { StatCard } from '../components/StatCard'
import { LoadingState } from '../components/LoadingState'
import { EmptyState } from '../components/EmptyState'
import { ErrorBanner } from '../components/ErrorBanner'
import { PageHeader } from '../components/PageHeader'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../components/ui/dialog'
import { formatDate } from '../lib/utils'
import { Bot, Play, Loader2, Users, Brain, Search, Cpu, MessageSquare, Activity, Server } from 'lucide-react'

interface TeamMember {
  name: string; role: string; skills: string[]; status?: string
}

interface Session {
  session_id: string; status: string; created_at: string; goal?: string; task_type?: string
}

interface SkillMetrics {
  skill_name: string; call_count: number; success_count: number;
  error_count: number; success_rate: number; avg_duration_ms: number;
}

const SERVICE_AGENTS = [
  { id: '02-immunefi', name: 'Immunefi Agent', role: 'Program Discovery', status: 'checking' as const },
  { id: '03-source', name: 'Source Agent', role: 'Source Code Fetcher', status: 'checking' as const },
  { id: '04-scanner', name: 'Scanner Agent', role: 'Static Analysis', status: 'checking' as const },
  { id: '06-ai', name: 'AI Agent', role: 'LLM Analysis', status: 'checking' as const },
  { id: '07-classifier', name: 'Classifier Agent', role: 'Bug Classification', status: 'checking' as const },
  { id: '08-exploit', name: 'Exploit Agent', role: 'PoC Exploitation', status: 'checking' as const },
  { id: '09-reporter', name: 'Reporter Agent', role: 'Report Generation', status: 'checking' as const },
  { id: '10-notifier', name: 'Notifier Agent', role: 'Notifications', status: 'checking' as const },
  { id: '11-orchestrator', name: 'Orchestrator Agent', role: 'Pipeline Orchestration', status: 'checking' as const },
  { id: '12-webhook', name: 'Webhook Agent', role: 'Webhook Events', status: 'checking' as const },
  { id: '13-upkeep', name: 'Upkeep Agent', role: 'Scheduler', status: 'checking' as const },
  { id: '16-submission', name: 'Submission Agent', role: 'Immunefi Assistant', status: 'checking' as const },
]

type ServiceStatus = 'healthy' | 'degraded' | 'down' | 'unknown' | 'checking'

export default function Antonio() {
  // Team
  const [team, setTeam] = useState<TeamMember[]>([])
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Skills
  const [skills, setSkills] = useState<SkillMetrics[]>([])
  const [memStats, setMemStats] = useState<any>(null)
  const [learning, setLearning] = useState<any>(null)

  // Memory search
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [searching, setSearching] = useState(false)

  // Run audit
  const [modalOpen, setModalOpen] = useState(false)
  const [genLoading, setGenLoading] = useState(false)
  const [genError, setGenError] = useState('')

  // Service agents health
  const [serviceStatuses, setServiceStatuses] = useState<Record<string, ServiceStatus>>({})

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [teamRes, sessionsRes, skillsRes, memRes, learnRes, healthRes] = await Promise.all([
          api.getTeamStructure().catch(() => ({ data: [] })),
          api.getTeamSessions({ limit: 10 }).catch(() => ({ data: [] })),
          api.getAgentSkillMetrics().catch(() => ({ data: [] })),
          api.getMemoryStats().catch(() => ({ data: null })),
          api.getLearningStats().catch(() => ({ data: null })),
          api.getHealthAll().catch(() => ({ data: {} })),
        ])
        if (!cancelled) {
          setTeam(Array.isArray(teamRes.data) ? teamRes.data : [])
          setSessions(Array.isArray(sessionsRes.data) ? sessionsRes.data : [])
          setSkills(Array.isArray(skillsRes.data) ? skillsRes.data as SkillMetrics[] : [])

          const memD = memRes.data as any
          setMemStats(memD)
          setLearning(learnRes.data)

          // Map health results to service agents
          const healthData = healthRes.data as Record<string, any> || {}
          const statuses: Record<string, ServiceStatus> = {}
          for (const svc of SERVICE_AGENTS) {
            const h = healthData[svc.id]
            statuses[svc.id] = h ? (h.status === 'healthy' ? 'healthy' : h.status === 'unreachable' ? 'down' : 'degraded') : 'unknown'
          }
          setServiceStatuses(statuses)
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
    const form = e.currentTarget
    const data = new FormData(form)
    try {
      await api.runTeamAudit({
        address: String(data.get('address') || ''),
        chain: String(data.get('chain') || 'ethereum'),
        goal: String(data.get('goal') || ''),
      } as any)
      setModalOpen(false)
      const res = await api.getTeamSessions({ limit: 10 })
      setSessions(Array.isArray(res.data) ? res.data : [])
    } catch (err: any) {
      setGenError(err?.message || 'Failed to run audit')
    } finally { setGenLoading(false) }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setSearching(true)
    try {
      const res = await api.memorySearch(searchQuery, 'vector')
      setSearchResults(Array.isArray(res.data?.results) ? res.data.results : [])
    } catch { setSearchResults([]) }
    setSearching(false)
  }

  const getAgentStatusColor = (status: ServiceStatus) => {
    switch (status) {
      case 'healthy': return 'bg-green-500'
      case 'degraded': return 'bg-yellow-500'
      case 'down': return 'bg-red-500'
      default: return 'bg-gray-500'
    }
  }

  if (loading) return <LoadingState message="Initializing Antonio..." />

  return (
    <div className="space-y-6">
      <PageHeader title="Antonio" description="AI Agent Commander — orchestrates all service agents via natural language" />

      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      {/* Quick Command Bar */}
      <Card>
        <div className="flex items-center gap-3">
          <Bot className="w-5 h-5 text-vyper-400 flex-shrink-0" />
          <Input
            placeholder="Chat with Antonio — e.g., 'audit 0x1234 on ethereum', 'show me programs', 'generate report for audit_xxx'..."
            className="flex-1"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && e.currentTarget.value.trim()) {
                setModalOpen(true)
              }
            }}
          />
          <Button onClick={() => setModalOpen(true)}>
            <Play className="w-4 h-4" /> Run Audit
          </Button>
        </div>
      </Card>

      {/* Service Agents Status */}
      <Card>
        <div className="flex items-center gap-2 mb-4">
          <Server className="w-4 h-4 text-vyper-400" />
          <h3 className="font-semibold dark:text-[#d4d4dc] light:text-[#09090b]">Service Agents</h3>
          <span className="text-xs dark:text-[#68687a] ml-auto">
            {Object.values(serviceStatuses).filter(s => s === 'healthy').length}/{SERVICE_AGENTS.length} online
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-2">
          {SERVICE_AGENTS.map((svc) => {
            const status = serviceStatuses[svc.id] || 'unknown'
            return (
              <div key={svc.id} className="dark:bg-[#0a0a12] light:bg-gray-50 rounded-lg p-3 border dark:border-[#1a1a28] light:border-[#e4e4e7]">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`w-2 h-2 rounded-full ${getAgentStatusColor(status)}`} />
                  <span className="text-xs font-medium dark:text-[#d4d4dc] truncate">{svc.name}</span>
                </div>
                <div className="text-[10px] dark:text-[#68687a] truncate">{svc.role}</div>
              </div>
            )
          })}
        </div>
      </Card>

      <Tabs defaultValue="team">
        <TabsList>
          <TabsTrigger value="team"><Users className="w-3.5 h-3.5" /> Team</TabsTrigger>
          <TabsTrigger value="skills"><Cpu className="w-3.5 h-3.5" /> Skills</TabsTrigger>
          <TabsTrigger value="memory"><Brain className="w-3.5 h-3.5" /> Memory</TabsTrigger>
          <TabsTrigger value="sessions"><Activity className="w-3.5 h-3.5" /> Sessions</TabsTrigger>
        </TabsList>

        {/* ═══════ TEAM TAB ═══════ */}
        <TabsContent value="team">
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
        </TabsContent>

        {/* ═══════ SKILLS TAB ═══════ */}
        <TabsContent value="skills">
          <Card>
            <h3 className="font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b] flex items-center gap-2">
              <Cpu className="w-4 h-4 text-vyper-400" /> Skill Metrics
            </h3>
            {skills.length === 0 ? (
              <p className="text-sm dark:text-[#68687a] text-center py-4">No skill data available yet.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Skill</TableHead>
                    <TableHead className="text-right">Calls</TableHead>
                    <TableHead className="text-right">Success Rate</TableHead>
                    <TableHead className="text-right">Avg Duration</TableHead>
                    <TableHead className="text-right">Errors</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {skills.map((s) => (
                    <TableRow key={s.skill_name}>
                      <TableCell className="font-medium dark:text-[#d4d4dc]">{s.skill_name}</TableCell>
                      <TableCell className="text-right">{s.call_count}</TableCell>
                      <TableCell className="text-right">
                        <span className={s.success_rate >= 0.8 ? 'text-green-400' : 'text-yellow-400'}>
                          {(s.success_rate * 100).toFixed(0)}%
                        </span>
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs">{s.avg_duration_ms}ms</TableCell>
                      <TableCell className="text-right">
                        <span className={s.error_count > 0 ? 'text-red-400' : 'dark:text-[#68687a]'}>{s.error_count}</span>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Card>

          {/* Learning Stats */}
          {learning && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
              <Card>
                <h3 className="font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b]">Learning Stats</h3>
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between">
                    <span className="dark:text-[#68687a]">Sessions Analyzed</span>
                    <span className="font-medium dark:text-[#d4d4dc]">{learning.total_sessions_analyzed}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="dark:text-[#68687a]">Patterns Found</span>
                    <span className="font-medium dark:text-[#d4d4dc]">{learning.patterns_found}</span>
                  </div>
                </div>
              </Card>
              <Card>
                <h3 className="font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b]">Memory Stats</h3>
                <div className="space-y-3 text-sm">
                  {[
                    ['Vector Store', memStats?.vector_store?.total_entries],
                    ['Episodic Store', memStats?.episodic_store?.total_entries],
                    ['Graph Memory', memStats?.graph_memory?.total_entries],
                  ].map(([label, value]) => (
                    <div key={String(label)} className="flex justify-between">
                      <span className="dark:text-[#68687a]">{String(label)}</span>
                      <span className="font-medium dark:text-[#d4d4dc]">{value ?? 0} items</span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}
        </TabsContent>

        {/* ═══════ MEMORY TAB ═══════ */}
        <TabsContent value="memory">
          <Card>
            <h3 className="font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b]">Memory Search</h3>
            <div className="flex gap-3 mb-4">
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Search memory (e.g., reentrancy, exploit pattern)..."
                className="flex-1"
              />
              <Button onClick={handleSearch} disabled={searching || !searchQuery.trim()}>
                {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                Search
              </Button>
            </div>
            {searchResults.length > 0 && (
              <div className="space-y-2">
                {searchResults.map((r: any, i: number) => (
                  <div key={i} className="dark:bg-[#0a0a12] light:bg-gray-50 rounded p-3 text-sm border dark:border-[#1a1a28]">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-vyper-400 font-medium">{r.key}</span>
                      {r.score !== undefined && <span className="dark:text-[#68687a] text-xs">score: {r.score}</span>}
                      {r.node_type && <Badge variant="default" className="text-[10px]">{r.node_type}</Badge>}
                    </div>
                    <p className="dark:text-[#68687a] text-xs">{(r.content_preview || r.label || '')}</p>
                  </div>
                ))}
              </div>
            )}
            {searchResults.length === 0 && searchQuery && !searching && (
              <p className="dark:text-[#68687a] text-sm">No results found.</p>
            )}
          </Card>
        </TabsContent>

        {/* ═══════ SESSIONS TAB ═══════ */}
        <TabsContent value="sessions">
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
        </TabsContent>
      </Tabs>

      {/* Run Audit Modal */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Run Team Audit</DialogTitle>
            <DialogDescription>Antonio will orchestrate all service agents to audit a smart contract.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleRunAudit}>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Contract Address</label>
                <Input name="address" placeholder="0x..." required className="font-mono text-xs" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Chain</label>
                <select name="chain" required className="w-full h-10 rounded-lg px-3 text-sm dark:bg-[#0a0a12] light:bg-gray-50 dark:border dark:border-[#1a1a28] light:border light:border-[#e4e4e7] dark:text-[#d4d4dc]">
                  <option value="ethereum">Ethereum</option>
                  <option value="bsc">BSC</option>
                  <option value="polygon">Polygon</option>
                  <option value="arbitrum">Arbitrum</option>
                  <option value="solana">Solana</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Goal (optional)</label>
                <Input name="goal" placeholder="e.g., Find all reentrancy vulnerabilities" />
              </div>
            </div>
            {genError && <p className="mt-3 text-sm text-red-400">{genError}</p>}
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
