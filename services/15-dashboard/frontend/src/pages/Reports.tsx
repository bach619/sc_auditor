import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Card } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Select } from '../components/ui/select'
import { Button } from '../components/ui/button'
import { StatusBadge } from '../components/StatusBadge'
import { LoadingState } from '../components/LoadingState'
import { EmptyState } from '../components/EmptyState'
import { ErrorBanner } from '../components/ErrorBanner'
import { PageHeader } from '../components/PageHeader'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../components/ui/dialog'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/table'
import { formatDate } from '../lib/utils'
import { Download, FileText, Loader2, Shield, ShieldAlert, ShieldCheck, AlertTriangle } from 'lucide-react'

interface Finding {
  case_id: string
  title: string
  severity: string
  status: string
  confidence: string
  contract: string
}

interface ReportEntry {
  report_id: string
  audit_id: string
  format: string
  status: string
  created_at: string
  download_url?: string
  findings: Finding[]
  findings_count: number
  total_findings: number
  severity_summary: Record<string, number>
}

const SEVERITY_COLORS: Record<string, string> = {
  Critical: 'text-red-400 bg-red-500/10 border-red-500/30',
  High: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
  Medium: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  Low: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  Info: 'text-gray-400 bg-gray-500/10 border-gray-500/30',
}

const SEVERITY_ICONS: Record<string, typeof Shield> = {
  Critical: ShieldAlert,
  High: ShieldAlert,
  Medium: Shield,
  Low: ShieldCheck,
  Info: AlertTriangle,
}

function SeverityBadge({ severity }: { severity: string }) {
  const colorClass = SEVERITY_COLORS[severity] || SEVERITY_COLORS.Info
  const Icon = SEVERITY_ICONS[severity] || Shield
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border ${colorClass}`}>
      <Icon className="w-3 h-3" />
      {severity}
    </span>
  )
}

export default function Reports() {
  const [reports, setReports] = useState<ReportEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [genAuditId, setGenAuditId] = useState('')
  const [genFormat, setGenFormat] = useState('immunefi')
  const [genLoading, setGenLoading] = useState(false)
  const [genError, setGenError] = useState('')
  const [severityFilter, setSeverityFilter] = useState('all')
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const res = await api.getReports()
        if (!cancelled) setReports(Array.isArray(res.data) ? res.data as ReportEntry[] : [])
      } catch (err: unknown) {
        if (!cancelled) setError((err as { message?: string })?.message || 'Failed to load reports')
      } finally { if (!cancelled) setLoading(false) }
    }
    load()
    return () => { cancelled = true }
  }, [])

  async function handleGenerate() {
    if (!genAuditId.trim()) return
    setGenLoading(true)
    setGenError('')
    try {
      await api.generateReport(genAuditId, genFormat)
      setModalOpen(false)
      setGenAuditId('')
      // Refresh list
      const res = await api.getReports()
      setReports(Array.isArray(res.data) ? res.data as ReportEntry[] : [])
    } catch (err: unknown) {
      setGenError((err as { message?: string })?.message || 'Failed to generate report')
    } finally { setGenLoading(false) }
  }

  // Collect all findings across reports and flatten into rows
  const allFindings: { finding: Finding; report: ReportEntry }[] = []
  for (const report of reports) {
    if (report.findings && Array.isArray(report.findings)) {
      for (const finding of report.findings) {
        if (severityFilter === 'all' || finding.severity.toLowerCase() === severityFilter.toLowerCase()) {
          allFindings.push({ finding, report })
        }
      }
    }
  }

  // Also show rows for reports that have no findings (so they're not invisible)
  const reportsWithoutFindings = reports.filter(r => !r.findings || r.findings.length === 0)

  const toggleExpand = (reportId: string) => {
    setExpandedRow(prev => prev === reportId ? null : reportId)
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Reports" description="Bug findings with severity levels — generate and download audit reports" />

      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs dark:text-[#68687a]">Filter severity:</span>
          <Select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)} className="w-32">
            <option value="all">All</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
            <option value="info">Info</option>
          </Select>
        </div>
        <Button onClick={() => { setModalOpen(true); setGenError('') }}>
          <FileText className="w-4 h-4" /> Generate Report
        </Button>
      </div>

      {loading ? (
        <LoadingState message="Loading reports..." />
      ) : allFindings.length === 0 && reportsWithoutFindings.length === 0 ? (
        <EmptyState message="No reports generated yet." action={{ label: 'Generate Report', onClick: () => setModalOpen(true) }} />
      ) : (
        <div className="space-y-4">
          {/* Findings Table — one row per bug finding */}
          {allFindings.length > 0 && (
            <Card>
              <div className="flex items-center gap-2 mb-4">
                <ShieldAlert className="w-4 h-4 text-vyper-400" />
                <h3 className="font-semibold dark:text-[#d4d4dc] light:text-[#09090b]">Bug Findings</h3>
                <span className="text-xs dark:text-[#68687a] ml-auto">{allFindings.length} findings</span>
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8"></TableHead>
                    <TableHead>Bug / Finding</TableHead>
                    <TableHead>Severity</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Confidence</TableHead>
                    <TableHead>Contract</TableHead>
                    <TableHead>Discovered</TableHead>
                    <TableHead className="text-right">Report</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {allFindings.map(({ finding, report }, i) => (
                    <TableRow key={`${report.report_id}-${finding.case_id || i}`}>
                      <TableCell>
                        <button
                          onClick={() => toggleExpand(finding.case_id)}
                          className="text-[#68687a] hover:text-[#d4d4dc] transition-colors"
                        >
                          {expandedRow === finding.case_id ? '▾' : '▸'}
                        </button>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="text-sm font-medium dark:text-[#d4d4dc]">{finding.title}</span>
                          <span className="text-[10px] dark:text-[#68687a] font-mono">{finding.case_id}</span>
                        </div>
                      </TableCell>
                      <TableCell><SeverityBadge severity={finding.severity} /></TableCell>
                      <TableCell><StatusBadge status={finding.status} /></TableCell>
                      <TableCell>
                        <span className={`text-xs font-medium ${
                          finding.confidence === 'Critical' ? 'text-red-400' :
                          finding.confidence === 'High' ? 'text-orange-400' :
                          finding.confidence === 'Medium' ? 'text-yellow-400' :
                          'text-blue-400'
                        }`}>{finding.confidence}</span>
                      </TableCell>
                      <TableCell className="text-xs font-mono dark:text-[#68687a] max-w-[120px] truncate">
                        {finding.contract || '—'}
                      </TableCell>
                      <TableCell className="text-xs dark:text-[#68687a]">{formatDate(report.created_at)}</TableCell>
                      <TableCell className="text-right">
                        {report.download_url ? (
                          <a href={report.download_url} target="_blank" rel="noopener noreferrer">
                            <Button variant="ghost" size="icon" title={`Download ${report.format} report`}>
                              <Download className="w-4 h-4" />
                            </Button>
                          </a>
                        ) : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}

          {/* Reports without findings — show as simple list */}
          {reportsWithoutFindings.length > 0 && (
            <Card>
              <div className="flex items-center gap-2 mb-4">
                <FileText className="w-4 h-4 text-vyper-400" />
                <h3 className="font-semibold dark:text-[#d4d4dc] light:text-[#09090b]">Generated Reports</h3>
                <span className="text-xs dark:text-[#68687a] ml-auto">{reportsWithoutFindings.length} files</span>
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Report ID</TableHead>
                    <TableHead>Audit ID</TableHead>
                    <TableHead>Format</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {reportsWithoutFindings.map((r) => (
                    <TableRow key={r.report_id}>
                      <TableCell className="font-mono text-xs">{r.report_id?.slice(0, 12) + '...' || '—'}</TableCell>
                      <TableCell className="font-mono text-xs">{r.audit_id?.slice(0, 12) + '...' || '—'}</TableCell>
                      <TableCell><StatusBadge status={r.format || 'unknown'} /></TableCell>
                      <TableCell><StatusBadge status={r.status || 'unknown'} /></TableCell>
                      <TableCell className="text-xs dark:text-[#68687a]">{formatDate(r.created_at)}</TableCell>
                      <TableCell className="text-right">
                        {r.download_url ? (
                          <a href={r.download_url} target="_blank" rel="noopener noreferrer">
                            <Button variant="ghost" size="icon"><Download className="w-4 h-4" /></Button>
                          </a>
                        ) : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}
        </div>
      )}

      {/* Generate Report Modal */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Generate Report</DialogTitle>
            <DialogDescription>Create a new audit report in your preferred format.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Audit ID</label>
              <Input value={genAuditId} onChange={(e) => setGenAuditId(e.target.value)} placeholder="audit_..." className="font-mono" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Format</label>
              <Select value={genFormat} onChange={(e) => setGenFormat(e.target.value)}>
                <option value="immunefi">Immunefi</option>
                <option value="full">Full Report</option>
                <option value="pdf">PDF</option>
                <option value="markdown">Markdown</option>
              </Select>
            </div>
          </div>
          {genError && <p className="text-sm text-red-400">{genError}</p>}
          <DialogFooter>
            <Button variant="outline" onClick={() => setModalOpen(false)} disabled={genLoading}>Cancel</Button>
            <Button onClick={handleGenerate} disabled={genLoading || !genAuditId.trim()}>
              {genLoading ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</> : 'Generate'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
