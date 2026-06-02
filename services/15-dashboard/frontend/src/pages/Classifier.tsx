import { useEffect, useState } from 'react'
import { api, type MetricsSummary } from '../lib/api'
import { Card } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Select } from '../components/ui/select'
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
import { BarChart3, ThumbsUp, ThumbsDown, MessageSquare, Loader2 } from 'lucide-react'

interface FeedbackItem {
  id?: string
  finding_id: string
  feedback: string
  status: string
  created_at?: string
}

export default function Classifier() {
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null)
  const [feedback, setFeedback] = useState<FeedbackItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Feedback modal
  const [modalOpen, setModalOpen] = useState(false)
  const [fbFindingId, setFbFindingId] = useState('')
  const [fbFeedback, setFbFeedback] = useState('')
  const [fbStatus, setFbStatus] = useState('pending_review')
  const [fbSubmitting, setFbSubmitting] = useState(false)
  const [fbError, setFbError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [metricsRes, feedbackRes] = await Promise.all([
          api.getMetrics().catch(() => ({ data: null })),
          api.getFeedback().catch(() => ({ data: [] })),
        ])
        if (!cancelled) {
          setMetrics(metricsRes.data as MetricsSummary)
          setFeedback(Array.isArray(feedbackRes.data) ? feedbackRes.data : [])
        }
      } catch {}
      if (!cancelled) setLoading(false)
    }
    load()
    return () => { cancelled = true }
  }, [])

  async function handleSubmitFeedback() {
    if (!fbFindingId.trim() || !fbFeedback.trim()) return
    setFbSubmitting(true)
    setFbError('')
    try {
      await api.submitFeedback({ finding_id: fbFindingId, feedback: fbFeedback, status: fbStatus })
      setModalOpen(false)
      setFbFindingId('')
      setFbFeedback('')
      setFbStatus('pending_review')
      // Refresh feedback list
      const res = await api.getFeedback()
      setFeedback(Array.isArray(res.data) ? res.data : [])
    } catch (err: any) {
      setFbError(err?.message || 'Failed to submit feedback')
    } finally { setFbSubmitting(false) }
  }

  if (loading) return <LoadingState message="Loading classifier data..." />

  const tpRate = metrics?.true_positive_rate ?? 0
  const precision = metrics?.precision ?? 0
  const recall = metrics?.recall ?? 0
  const f1 = metrics?.f1_score ?? 0

  return (
    <div className="space-y-6">
      <PageHeader title="Classifier" description="Bug classification metrics, feedback, and true positive analysis" />

      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      {/* Metrics Cards */}
      {metrics && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <StatCard label="Total Audits" value={metrics.total_audits} />
          <StatCard label="Total Findings" value={metrics.total_findings} />
          <StatCard label="True Positive Rate" value={`${(tpRate * 100).toFixed(1)}%`} accent accentColor="green" />
          <StatCard label="Precision" value={`${(precision * 100).toFixed(1)}%`} accent accentColor="blue" />
          <StatCard label="F1 Score" value={`${(f1 * 100).toFixed(1)}%`} accent accentColor="blue" />
        </div>
      )}

      {metrics && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Critical" value={metrics.critical_findings} accent accentColor="red" />
          <StatCard label="High" value={metrics.high_findings} accent accentColor="red" />
          <StatCard label="Medium" value={metrics.medium_findings} accent accentColor="yellow" />
          <StatCard label="Low" value={metrics.low_findings} />
        </div>
      )}

      <Tabs defaultValue="feedback">
        <TabsList>
          <TabsTrigger value="feedback">Feedback</TabsTrigger>
          <TabsTrigger value="per-tool">Per-Tool Metrics</TabsTrigger>
        </TabsList>

        {/* Feedback Tab */}
        <TabsContent value="feedback">
          <div className="flex justify-end mb-4">
            <Button onClick={() => { setModalOpen(true); setFbError('') }}>
              <MessageSquare className="w-4 h-4" /> Submit Feedback
            </Button>
          </div>

          {feedback.length === 0 ? (
            <EmptyState message="No feedback entries yet." action={{ label: 'Submit Feedback', onClick: () => setModalOpen(true) }} />
          ) : (
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Finding ID</TableHead>
                    <TableHead>Feedback</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {feedback.map((f, i) => (
                    <TableRow key={f.id || f.finding_id || i}>
                      <TableCell className="font-mono text-xs">{f.finding_id?.slice(0, 16) || '—'}</TableCell>
                      <TableCell className="max-w-md truncate">{f.feedback}</TableCell>
                      <TableCell><StatusBadge status={f.status || 'unknown'} /></TableCell>
                      <TableCell className="text-xs dark:text-[#68687a]">{formatDate(f.created_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}
        </TabsContent>

        {/* Per-Tool Metrics Tab */}
        <TabsContent value="per-tool">
          {metrics?.per_tool && Object.keys(metrics.per_tool).length > 0 ? (
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Tool</TableHead>
                    <TableHead className="text-right">Findings</TableHead>
                    <TableHead className="text-right">TP</TableHead>
                    <TableHead className="text-right">FP</TableHead>
                    <TableHead className="text-right">TP Rate</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Object.entries(metrics.per_tool).map(([tool, data]: [string, any]) => (
                    <TableRow key={tool}>
                      <TableCell className="font-medium dark:text-[#d4d4dc]">{tool}</TableCell>
                      <TableCell className="text-right">{data.total_findings ?? data.total ?? 0}</TableCell>
                      <TableCell className="text-right text-green-400">{data.true_positives ?? data.tp ?? 0}</TableCell>
                      <TableCell className="text-right text-red-400">{data.false_positives ?? data.fp ?? 0}</TableCell>
                      <TableCell className="text-right">
                        {data.true_positive_rate != null
                          ? `${(data.true_positive_rate * 100).toFixed(0)}%`
                          : data.tp_rate != null
                            ? `${(data.tp_rate * 100).toFixed(0)}%`
                            : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          ) : (
            <Card><p className="text-sm dark:text-[#68687a] text-center py-8">No per-tool metrics available.</p></Card>
          )}
        </TabsContent>
      </Tabs>

      {/* Submit Feedback Modal */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Submit Feedback</DialogTitle>
            <DialogDescription>Provide feedback on a bug finding classification.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Finding ID</label>
              <Input value={fbFindingId} onChange={(e) => setFbFindingId(e.target.value)} placeholder="finding_..." className="font-mono" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Status</label>
              <Select value={fbStatus} onChange={(e) => setFbStatus(e.target.value)}>
                <option value="pending_review">Pending Review</option>
                <option value="confirmed">Confirmed</option>
                <option value="false_positive">False Positive</option>
                <option value="disputed">Disputed</option>
              </Select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Feedback</label>
              <textarea
                value={fbFeedback}
                onChange={(e) => setFbFeedback(e.target.value)}
                placeholder="Describe your feedback..."
                rows={4}
                className="w-full rounded-lg px-3 py-2 text-sm resize-none dark:bg-[#0a0a12] light:bg-gray-50 dark:border dark:border-[#1a1a28] light:border light:border-[#e4e4e7] dark:text-[#d4d4dc] placeholder:text-[#68687a] focus:outline-none focus:ring-2 focus:ring-vyper-500/40"
              />
            </div>
          </div>
          {fbError && <p className="text-sm text-red-400">{fbError}</p>}
          <DialogFooter>
            <Button variant="outline" onClick={() => setModalOpen(false)} disabled={fbSubmitting}>Cancel</Button>
            <Button onClick={handleSubmitFeedback} disabled={fbSubmitting || !fbFindingId.trim() || !fbFeedback.trim()}>
              {fbSubmitting ? <><Loader2 className="w-4 h-4 animate-spin" /> Submitting...</> : 'Submit'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
