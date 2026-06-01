import { useEffect, useState } from 'react'
import { api, type Audit, type VpCase, type CaseStatsData } from '../lib/api'
import { Card } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Select } from '../components/ui/select'
import { StatusBadge } from '../components/StatusBadge'
import { StatCard } from '../components/StatCard'
import { LoadingState } from '../components/LoadingState'
import { EmptyState } from '../components/EmptyState'
import { ErrorBanner } from '../components/ErrorBanner'
import { PageHeader } from '../components/PageHeader'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/table'
import { formatDuration, formatDate, shortId } from '../lib/utils'

const SEVERITY_ORDER = ['Critical', 'High', 'Medium', 'Low', 'Info']

export default function Scanning() {
  // Audits state
  const [audits, setAudits] = useState<Audit[]>([])
  const [auditsLoading, setAuditsLoading] = useState(true)
  const [auditSearch, setAuditSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [error, setError] = useState('')

  // Pipeline state
  const [pipelineStats, setPipelineStats] = useState<any>(null)
  const [pipelineSteps, setPipelineSteps] = useState<any[]>([])

  // Cases state
  const [cases, setCases] = useState<VpCase[]>([])
  const [casesLoading, setCasesLoading] = useState(true)
  const [caseStats, setCaseStats] = useState<CaseStatsData | null>(null)
  const [caseSearch, setCaseSearch] = useState('')
  const [severityFilter, setSeverityFilter] = useState('')
  const [caseSort, setCaseSort] = useState('created_at')
  const [caseOrder, setCaseOrder] = useState('desc')

  // Fetch Audits
  useEffect(() => {
    let cancelled = false
    async function load() {
      setAuditsLoading(true)
      try {
        const params: any = { limit: 50 }
        if (statusFilter) params.state = statusFilter
        const res = await api.getAudits(params)
        if (!cancelled) setAudits(Array.isArray(res.data) ? res.data : [])
      } catch { /* ignore */ }
      if (!cancelled) setAuditsLoading(false)
    }
    load()
    return () => { cancelled = true }
  }, [statusFilter])

  // Fetch Pipeline
  useEffect(() => {
    Promise.all([
      api.getPipelineStatus().then(r => r.data).catch(() => null),
      api.getPipelineSteps().then(r => r.data).catch(() => null),
    ]).then(([stats, steps]) => {
      setPipelineStats(stats)
      setPipelineSteps(Array.isArray(steps) ? steps : [])
    })
  }, [])

  // Fetch Cases
  useEffect(() => {
    let cancelled = false
    async function load() {
      setCasesLoading(true)
      try {
        const params: any = { status: 'OPEN', limit: 100, sort: caseSort, order: caseOrder }
        if (caseSearch) params.search = caseSearch
        if (severityFilter) params.severity = severityFilter
        const [casesRes, statsRes] = await Promise.all([api.getCases(params), api.getCaseStats()])
        if (!cancelled) {
          setCases(Array.isArray(casesRes.data) ? casesRes.data : [])
          setCaseStats(statsRes.data || null)
        }
      } catch {}
      if (!cancelled) setCasesLoading(false)
    }
    load()
    return () => { cancelled = true }
  }, [caseSearch, severityFilter, caseSort, caseOrder])

  const filteredAudits = audits.filter(a =>
    !auditSearch || a.audit_id.toLowerCase().includes(auditSearch.toLowerCase()) ||
    a.program?.toLowerCase().includes(auditSearch.toLowerCase())
  )

  return (
    <div className="space-y-6">
      <PageHeader title="Scanning" description="Audit pipeline, scanner results, and open cases" />

      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      <Tabs defaultValue="audits">
        <TabsList>
          <TabsTrigger value="audits">Audits</TabsTrigger>
          <TabsTrigger value="pipeline">Pipeline</TabsTrigger>
          <TabsTrigger value="cases">Cases</TabsTrigger>
        </TabsList>

        {/* ═══ Audits Tab ═══ */}
        <TabsContent value="audits">
          <div className="flex flex-wrap gap-4 items-center mb-4">
            <Input
              value={auditSearch}
              onChange={(e) => setAuditSearch(e.target.value)}
              placeholder="Search by ID or program..."
              className="max-w-xs"
            />
            <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="w-36">
              <option value="">All Status</option>
              <option value="PENDING">Pending</option>
              <option value="RUNNING">Running</option>
              <option value="COMPLETED">Completed</option>
              <option value="FAILED">Failed</option>
              <option value="SCANNING">Scanning</option>
            </Select>
          </div>

          {auditsLoading ? (
            <LoadingState message="Loading audits..." />
          ) : filteredAudits.length === 0 ? (
            <EmptyState message="No audits found." />
          ) : (
            <Card>
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
                  {filteredAudits.map((a) => (
                    <TableRow key={a.audit_id}>
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
          )}
        </TabsContent>

        {/* ═══ Pipeline Tab ═══ */}
        <TabsContent value="pipeline">
          {pipelineStats && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
              <StatCard label="Total" value={pipelineStats.total_audits} />
              <StatCard label="Completed" value={pipelineStats.completed} accent accentColor="green" />
              <StatCard label="In Progress" value={pipelineStats.in_progress} accent accentColor="blue" />
              <StatCard label="Failed" value={pipelineStats.failed} accent accentColor="red" />
            </div>
          )}

          {pipelineSteps.length > 0 ? (
            <Card>
              <h3 className="font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b]">Pipeline Steps</h3>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Step</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead>Timestamp</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pipelineSteps.map((s: any, i: number) => (
                    <TableRow key={i}>
                      <TableCell>{s.step || s.name || `Step ${i + 1}`}</TableCell>
                      <TableCell><StatusBadge status={s.status || 'PENDING'} /></TableCell>
                      <TableCell className="font-mono text-xs">{s.duration ? `${s.duration}s` : '—'}</TableCell>
                      <TableCell className="text-xs dark:text-[#68687a]">{s.timestamp ? formatDate(s.timestamp) : '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          ) : (
            <Card><p className="text-sm dark:text-[#68687a] text-center py-8">No pipeline data available.</p></Card>
          )}
        </TabsContent>

        {/* ═══ Cases Tab ═══ */}
        <TabsContent value="cases">
          {caseStats && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
              <StatCard label="Open Cases" value={caseStats.open_cases} />
              <StatCard label="Closed Cases" value={caseStats.closed_cases} />
              <StatCard label="Avg Confidence" value={`${(caseStats.avg_confidence * 100).toFixed(0)}%`} accent accentColor="blue" />
              <StatCard label="Total Bounty" value={`$${caseStats.total_bounty.toLocaleString()}`} accent accentColor="green" />
            </div>
          )}

          <div className="flex flex-wrap gap-4 items-center mb-4">
            <Input
              value={caseSearch}
              onChange={(e) => setCaseSearch(e.target.value)}
              placeholder="Search cases..."
              className="max-w-xs"
            />
            <Select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)} className="w-36">
              <option value="">All Severities</option>
              {SEVERITY_ORDER.map(s => <option key={s} value={s}>{s}</option>)}
            </Select>
          </div>

          {casesLoading ? (
            <LoadingState message="Loading cases..." />
          ) : cases.length === 0 ? (
            <EmptyState message="No open cases. Run a scan to find bugs!" />
          ) : (
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Case</TableHead>
                    <TableHead>Severity</TableHead>
                    <TableHead>Scanners</TableHead>
                    <TableHead>Confidence</TableHead>
                    <TableHead>Contract</TableHead>
                    <TableHead>Created</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {cases.map((c) => (
                    <TableRow key={c.case_id}>
                      <TableCell>
                        <div className="text-sm font-medium dark:text-[#d4d4dc]">{c.title}</div>
                        <div className="text-xs font-mono dark:text-[#68687a]">{c.case_id}</div>
                      </TableCell>
                      <TableCell><StatusBadge status={c.severity} /></TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {c.scanners.map((s, i) => (
                            <span key={i} className="text-xs px-1.5 py-0.5 rounded dark:bg-[#0a0a12] light:bg-gray-100 font-mono dark:text-[#68687a]">
                              {s.name}
                            </span>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 rounded-full dark:bg-[#1a1a28] light:bg-[#e4e4e7] overflow-hidden">
                            <div className={`h-full rounded-full ${c.confidence >= 0.8 ? 'bg-green-500' : c.confidence >= 0.6 ? 'bg-yellow-500' : 'bg-red-500'}`}
                              style={{ width: `${Math.round(c.confidence * 100)}%` }} />
                          </div>
                          <span className="text-xs font-mono">{(c.confidence * 100).toFixed(0)}%</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-xs font-mono">{c.contract || '—'}</TableCell>
                      <TableCell className="text-xs dark:text-[#68687a]">{formatDate(c.created_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
