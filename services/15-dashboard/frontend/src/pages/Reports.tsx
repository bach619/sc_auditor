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
import { Download, FileText, Loader2 } from 'lucide-react'

export default function Reports() {
  const [reports, setReports] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [genAuditId, setGenAuditId] = useState('')
  const [genFormat, setGenFormat] = useState('immunefi')
  const [genLoading, setGenLoading] = useState(false)
  const [genError, setGenError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const res = await api.getReports()
        if (!cancelled) setReports(Array.isArray(res.data) ? res.data : [])
      } catch (err: any) {
        if (!cancelled) setError(err?.message || 'Failed to load reports')
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
      setReports(Array.isArray(res.data) ? res.data : [])
    } catch (err: any) {
      setGenError(err?.message || 'Failed to generate report')
    } finally { setGenLoading(false) }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Reports" description="Generate and download audit reports" />

      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      <div className="flex justify-end">
        <Button onClick={() => { setModalOpen(true); setGenError('') }}>
          <FileText className="w-4 h-4" /> Generate Report
        </Button>
      </div>

      {loading ? (
        <LoadingState message="Loading reports..." />
      ) : reports.length === 0 ? (
        <EmptyState message="No reports generated yet." action={{ label: 'Generate Report', onClick: () => setModalOpen(true) }} />
      ) : (
        <Card>
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
              {reports.map((r: any, i: number) => (
                <TableRow key={r.report_id || i}>
                  <TableCell className="font-mono text-xs">{r.report_id ? r.report_id.slice(0, 12) + '...' : '—'}</TableCell>
                  <TableCell className="font-mono text-xs">{r.audit_id ? r.audit_id.slice(0, 12) + '...' : '—'}</TableCell>
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
