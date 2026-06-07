import { useState, useEffect } from 'react'
import { api } from '../lib/api'
import { Card } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { LoadingState } from '../components/LoadingState'
import { PageHeader } from '../components/PageHeader'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/table'
import { Brain, Cpu, Search, Loader2, Play, Square } from 'lucide-react'

interface DaemonStatus {
  running: boolean; interval: number; total_cycles: number; total_errors: number;
  auto_hunts_done: number; uptime: string; avg_cycle_duration_ms: number;
}

interface SkillMetrics {
  skill_name: string; call_count: number; success_count: number;
  error_count: number; success_rate: number; avg_duration_ms: number;
}

export default function AIConfig() {
  const [daemon, setDaemon] = useState<DaemonStatus | null>(null)
  const [skills, setSkills] = useState<SkillMetrics[]>([])
  const [memStats, setMemStats] = useState<Record<string, unknown> | null>(null)
  const [learning, setLearning] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)

  const [searchQuery, setSearchQuery] = useState('')
  const [searchStore, setSearchStore] = useState<'vector' | 'episodic' | 'graph'>('vector')
  const [searchResults, setSearchResults] = useState<unknown[]>([])
  const [searching, setSearching] = useState(false)

  useEffect(() => {
    Promise.all([
      api.getAgentDaemonStatus().then(r => r.data).catch(() => null),
      api.getAgentSkillMetrics().then(r => r.data).catch(() => null),
      api.getMemoryStats().then(r => r.data).catch(() => null),
      api.getLearningStats().then(r => r.data).catch(() => null),
    ]).then(([d, s, m, l]) => {
      if (d) setDaemon(d as DaemonStatus)
      if (s) setSkills(Array.isArray(s) ? s as SkillMetrics[] : [])
      if (m) setMemStats(m as Record<string, unknown>)
      if (l) setLearning(l as Record<string, unknown>)
      setLoading(false)
    })
  }, [])

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setSearching(true)
    try {
      const res = await api.memorySearch(searchQuery, searchStore)
      const resData = res.data as Record<string, unknown>
      setSearchResults(Array.isArray(resData?.results) ? resData.results as unknown[] : [])
    } catch { setSearchResults([]) }
    setSearching(false)
  }

  const handleDaemonToggle = async () => {
    try {
      if (daemon?.running) await api.daemonStop()
      else await api.daemonStart()
      const res = await api.getAgentDaemonStatus()
      setDaemon(res.data as DaemonStatus)
    } catch (err) { console.error('AIConfig toggle failed', err) }
  }

  if (loading) return <LoadingState message="Loading AI configuration..." />

  return (
    <div className="space-y-6">
      <PageHeader title="AI Agent" description="Autonomous daemon control, skill metrics, and memory intelligence" />

      {/* Daemon Control */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold dark:text-[#d4d4dc] light:text-[#09090b] flex items-center gap-2">
            <Cpu className="w-4 h-4 text-vyper-400" /> Autonomous Daemon
          </h3>
          <Button onClick={handleDaemonToggle} variant={daemon?.running ? 'destructive' : 'default'}>
            {daemon?.running ? <><Square className="w-4 h-4" /> Stop</> : <><Play className="w-4 h-4" /> Start</>}
          </Button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <div className="text-xs dark:text-[#68687a] light:text-[#71717a]">Status</div>
            <div className="flex items-center gap-2 mt-1">
              <span className={`h-2 w-2 rounded-full ${daemon?.running ? 'bg-green-400' : 'bg-red-500'}`} />
              <span className="font-medium dark:text-[#d4d4dc]">{daemon?.running ? 'Running' : 'Stopped'}</span>
            </div>
          </div>
          <div>
            <div className="text-xs dark:text-[#68687a] light:text-[#71717a]">Cycles</div>
            <div className="font-medium dark:text-[#d4d4dc] mt-1">{daemon?.total_cycles ?? 0}</div>
          </div>
          <div>
            <div className="text-xs dark:text-[#68687a] light:text-[#71717a]">Errors</div>
            <div className={`font-medium mt-1 ${(daemon?.total_errors ?? 0) > 0 ? 'text-red-400' : 'dark:text-[#d4d4dc]'}`}>
              {daemon?.total_errors ?? 0}
            </div>
          </div>
          <div>
            <div className="text-xs dark:text-[#68687a] light:text-[#71717a]">Uptime</div>
            <div className="font-medium dark:text-[#d4d4dc] mt-1">{daemon?.uptime ?? 'N/A'}</div>
          </div>
          <div>
            <div className="text-xs dark:text-[#68687a] light:text-[#71717a]">Avg Cycle</div>
            <div className="font-medium dark:text-[#d4d4dc] mt-1">{daemon?.avg_cycle_duration_ms ?? 0}ms</div>
          </div>
          <div>
            <div className="text-xs dark:text-[#68687a] light:text-[#71717a]">Auto-Hunts</div>
            <div className="font-medium dark:text-[#d4d4dc] mt-1">{daemon?.auto_hunts_done ?? 0}</div>
          </div>
        </div>
      </Card>

      {/* Skill Metrics */}
      <Card>
        <h3 className="font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b] flex items-center gap-2">
          <Brain className="w-4 h-4 text-vyper-400" /> Skill Metrics
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

      {/* Memory Search */}
      <Card>
        <h3 className="font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b]">Memory Search</h3>
        <div className="flex gap-3 mb-4">
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search memory (e.g., reentrancy, session)..."
            className="flex-1"
          />
          <select
            value={searchStore}
            onChange={(e) => setSearchStore(e.target.value as 'vector' | 'episodic' | 'graph')}
            className="h-10 rounded-lg px-3 text-sm dark:bg-[#0a0a12] light:bg-gray-50 dark:border dark:border-[#1a1a28] light:border light:border-[#e4e4e7] dark:text-[#d4d4dc]"
          >
            <option value="vector">Vector</option>
            <option value="episodic">Episodic</option>
            <option value="graph">Graph</option>
          </select>
          <Button onClick={handleSearch} disabled={searching || !searchQuery.trim()}>
            {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            Search
          </Button>
        </div>
        {searchResults.length > 0 && (
          <div className="space-y-2">
            {searchResults.map((item, i: number) => {
              const r = item as Record<string, unknown>
              return (
              <div key={i} className="dark:bg-[#0a0a12] light:bg-gray-50 rounded p-3 text-sm border dark:border-[#1a1a28]">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-vyper-400 font-medium">{r.key as string}</span>
                  {r.score !== undefined && <span className="dark:text-[#68687a] text-xs">score: {String(r.score)}</span>}
                  {r.node_type ? <Badge variant="default" className="text-[10px]">{r.node_type as string}</Badge> : null}
                </div>
                <p className="dark:text-[#68687a] text-xs">{String(r.content_preview || r.label || '')}</p>
              </div>
              )
            })}
          </div>
        )}
        {searchResults.length === 0 && searchQuery && !searching && (
          <p className="dark:text-[#68687a] text-sm">No results found.</p>
        )}
      </Card>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Memory Stats */}
        <Card>
          <h3 className="font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b]">Memory Stats</h3>
          {memStats ? (
            <div className="space-y-3 text-sm">
              {[
                ['Vector Store', (memStats.vector_store as Record<string, unknown>)?.total_entries as number],
                ['Vector Searches', (memStats.vector_store as Record<string, unknown>)?.total_searches as number],
                ['Episodic Store', (memStats.episodic_store as Record<string, unknown>)?.total_entries as number],
                ['Graph Memory', (memStats.graph_memory as Record<string, unknown>)?.total_entries as number],
              ].map(([label, value]) => (
                <div key={String(label)} className="flex justify-between">
                  <span className="dark:text-[#68687a]">{String(label)}</span>
                  <span className="font-medium dark:text-[#d4d4dc]">{value ?? 0} items</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="dark:text-[#68687a] text-sm">No data.</p>
          )}
        </Card>

        {/* Learning Stats */}
        <Card>
          <h3 className="font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b]">Learning Stats</h3>
          {learning ? (
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="dark:text-[#68687a]">Sessions Analyzed</span>
                <span className="font-medium dark:text-[#d4d4dc]">{learning.total_sessions_analyzed as number}</span>
              </div>
              <div className="flex justify-between">
                <span className="dark:text-[#68687a]">Patterns Found</span>
                <span className="font-medium dark:text-[#d4d4dc]">{learning.patterns_found as number}</span>
              </div>
              {learning.top_error_patterns && typeof learning.top_error_patterns === 'object' && Object.keys(learning.top_error_patterns as Record<string, unknown>).length > 0 ? (
                <div className="pt-3 border-t dark:border-[#1a1a28]">
                  <div className="text-xs font-medium uppercase tracking-wider text-red-400 mb-2">Top Error Patterns</div>
                  {Object.entries(learning.top_error_patterns as Record<string, unknown>).slice(0, 5).map(([pattern, count]) => (
                    <div key={pattern} className="flex justify-between mt-1">
                      <span className="text-xs dark:text-[#68687a] truncate mr-2">{pattern}</span>
                      <span className="text-xs text-red-400 font-medium">{String(count)}x</span>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : (
            <p className="dark:text-[#68687a] text-sm">No learning data yet.</p>
          )}
        </Card>
      </div>
    </div>
  )
}
