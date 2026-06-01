import { useEffect, useState } from 'react'
import { api } from '../lib/api'
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
import { formatDate, shortId } from '../lib/utils'
import { Send, FileText, Plus, Loader2, MessageSquare, Eye } from 'lucide-react'

interface SubmissionItem {
  id: string
  finding_id: string
  program_slug: string
  bug_category: string
  title: string
  severity: string
  status: string
  created_at: string
}

export default function Submission() {
  const [submissions, setSubmissions] = useState<SubmissionItem[]>([])
  const [stats, setStats] = useState<any>(null)
  const [categoryStats, setCategoryStats] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  // Create modal
  const [createOpen, setCreateOpen] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)
  const [createError, setCreateError] = useState('')

  // Draft modal
  const [draftOpen, setDraftOpen] = useState(false)
  const [draftFindingId, setDraftFindingId] = useState('')
  const [draftMessage, setDraftMessage] = useState('')
  const [draftResult, setDraftResult] = useState<any>(null)
  const [draftLoading, setDraftLoading] = useState(false)
  const [draftError, setDraftError] = useState('')

  // Detail modal
  const [detailOpen, setDetailOpen] = useState(false)
  const [detailSubmission, setDetailSubmission] = useState<any>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')

  async function loadSubmissions() {
    try {
      const params: any = {}
      if (categoryFilter) params.category = categoryFilter
      if (statusFilter) params.status = statusFilter
      const res = await api.getSubmissions(params)
      setSubmissions(Array.isArray(res.data) ? res.data : [])
    } catch {}
  }

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [subsRes, statsRes, catStatsRes] = await Promise.all([
          api.getSubmissions().catch(() => ({ data: [] })),
          api.getSubmissionStats().catch(() => ({ data: null })),
          api.getSubmissionCategoryStats().catch(() => ({ data: [] })),
        ])
        if (!cancelled) {
          setSubmissions(Array.isArray(subsRes.data) ? subsRes.data : [])
          setStats(subsRes.data as any)
          setCategoryStats(Array.isArray(catStatsRes.data) ? catStatsRes.data : [])
        }
      } catch {}
      if (!cancelled) setLoading(false)
    }
    load()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    loadSubmissions()
  }, [categoryFilter, statusFilter])

  async function handleCreate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setCreateLoading(true)
    setCreateError('')
    const form = e.currentTarget
    const data = new FormData(form)
    try {
      await api.createSubmission({
        finding_id: String(data.get('finding_id') || ''),
        program_slug: String(data.get('program_slug') || ''),
        bug_category: String(data.get('bug_category') || ''),
        title: String(data.get('title') || ''),
        description: String(data.get('description') || ''),
        severity: String(data.get('severity') || 'medium'),
      })
      setCreateOpen(false)
      await loadSubmissions()
    } catch (err: any) {
      setCreateError(err?.message || 'Failed to create submission')
    } finally { setCreateLoading(false) }
  }

  async function handleGenerateDraft() {
    if (!draftFindingId.trim() || !draftMessage.trim()) return
    setDraftLoading(true)
    setDraftError('')
    setDraftResult(null)
    try {
      const res = await api.generateSubmissionDraft(draftFindingId, {
        immunefi_message: draftMessage,
      })
      setDraftResult(res.data)
    } catch (err: any) {
      setDraftError(err?.message || 'Failed to generate draft')
    } finally { setDraftLoading(false) }
  }

  async function handleViewDetail(findingId: string) {
    setDetailLoading(true)
    setDetailOpen(true)
    try {
      const res = await api.getSubmission(findingId)
      setDetailSubmission(res.data)
    } catch (err: any) {
      setDetailError(err?.message || 'Failed to load submission detail')
    } finally { setDetailLoading(false) }
  }

  if (loading) return <LoadingState message="Loading submissions..." />

  return (
    <div className="space-y-6">
      <PageHeader title="Submission" description="Immunefi submission assistant — create, draft, and respond to bug bounty programs" />

      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Total Submissions" value={stats.total_submissions ?? submissions.length} />
          {stats.by_status && Object.entries(stats.by_status).map(([status, count]: [string, any]) => (
            <StatCard key={status} label={status.charAt(0).toUpperCase() + status.slice(1)} value={count} />
          ))}
        </div>
      )}

      {/* Category Stats */}
      {categoryStats.length > 0 && (
        <Card>
          <h3 className="font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b]">Category Acceptance Rates</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {categoryStats.map((cs: any) => (
              <div key={cs.category} className="dark:bg-[#0a0a12] light:bg-gray-50 rounded-lg p-4 border dark:border-[#1a1a28] light:border-[#e4e4e7]">
                <div className="text-sm font-medium dark:text-[#d4d4dc] capitalize">{cs.category.replace(/_/g, ' ')}</div>
                <div className="text-xs dark:text-[#68687a] mt-1">{cs.total} submissions</div>
                <div className="text-lg font-semibold mt-1" style={{ color: cs.acceptance_rate >= 50 ? '#22c55e' : cs.acceptance_rate >= 25 ? '#eab308' : '#ef4444' }}>
                  {cs.acceptance_rate}%
                </div>
                <div className="text-xs dark:text-[#68687a]">
                  {cs.accepted} accepted / {cs.rejected} rejected
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Tabs defaultValue="submissions">
        <TabsList>
          <TabsTrigger value="submissions">Submissions</TabsTrigger>
          <TabsTrigger value="draft">Draft Generator</TabsTrigger>
        </TabsList>

        {/* Submissions Tab */}
        <TabsContent value="submissions">
          <div className="flex flex-wrap gap-4 items-center justify-between mb-4">
            <div className="flex gap-4 items-center">
              <Select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className="w-40">
                <option value="">All Categories</option>
                <option value="reentrancy">Reentrancy</option>
                <option value="access_control">Access Control</option>
                <option value="arithmetic">Arithmetic</option>
                <option value="oracle">Oracle</option>
                <option value="flash_loan">Flash Loan</option>
                <option value="logic_error">Logic Error</option>
                <option value="other">Other</option>
              </Select>
              <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="w-40">
                <option value="">All Status</option>
                <option value="draft">Draft</option>
                <option value="submitted">Submitted</option>
                <option value="accepted">Accepted</option>
                <option value="rejected">Rejected</option>
                <option value="paid">Paid</option>
              </Select>
            </div>
            <Button onClick={() => { setCreateOpen(true); setCreateError('') }}>
              <Plus className="w-4 h-4" /> New Submission
            </Button>
          </div>

          {submissions.length === 0 ? (
            <EmptyState message="No submissions yet." action={{ label: 'New Submission', onClick: () => setCreateOpen(true) }} />
          ) : (
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Finding ID</TableHead>
                    <TableHead>Title</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Program</TableHead>
                    <TableHead>Severity</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {submissions.map((s) => (
                    <TableRow key={s.id || s.finding_id}>
                      <TableCell className="font-mono text-xs">{shortId(s.finding_id)}</TableCell>
                      <TableCell className="max-w-[200px] truncate dark:text-[#d4d4dc]">{s.title}</TableCell>
                      <TableCell><Badge variant="secondary" className="text-[10px]">{s.bug_category}</Badge></TableCell>
                      <TableCell className="text-xs">{s.program_slug}</TableCell>
                      <TableCell><StatusBadge status={s.severity} /></TableCell>
                      <TableCell><StatusBadge status={s.status} /></TableCell>
                      <TableCell className="text-xs dark:text-[#68687a]">{formatDate(s.created_at)}</TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm" onClick={() => handleViewDetail(s.finding_id)}>
                          <Eye className="w-4 h-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}
        </TabsContent>

        {/* Draft Generator Tab */}
        <TabsContent value="draft">
          <Card>
            <h3 className="font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b] flex items-center gap-2">
              <FileText className="w-4 h-4 text-vyper-400" /> Generate Draft Response
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Finding ID</label>
                <Input
                  value={draftFindingId}
                  onChange={(e) => setDraftFindingId(e.target.value)}
                  placeholder="finding_..."
                  className="max-w-md font-mono"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Immunefi Message</label>
                <textarea
                  value={draftMessage}
                  onChange={(e) => setDraftMessage(e.target.value)}
                  placeholder="Paste the Immunefi message or question you want to respond to..."
                  rows={4}
                  className="w-full rounded-lg px-3 py-2 text-sm resize-none dark:bg-[#0a0a12] light:bg-gray-50 dark:border dark:border-[#1a1a28] light:border light:border-[#e4e4e7] dark:text-[#d4d4dc] placeholder:text-[#68687a] focus:outline-none focus:ring-2 focus:ring-vyper-500/40"
                />
              </div>
              <Button onClick={handleGenerateDraft} disabled={draftLoading || !draftFindingId.trim() || !draftMessage.trim()}>
                {draftLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
                {draftLoading ? 'Generating...' : 'Generate Draft'}
              </Button>
              {draftError && <p className="text-sm text-red-400">{draftError}</p>}
            </div>

            {draftResult && (
              <div className="mt-6 space-y-4">
                {draftResult.intent && (
                  <div className="flex items-center gap-2 text-sm">
                    <span className="dark:text-[#68687a]">Intent:</span>
                    <Badge variant="secondary">{draftResult.intent}</Badge>
                    {draftResult.confidence && (
                      <span className="text-xs dark:text-[#68687a]">
                        ({(draftResult.confidence * 100).toFixed(0)}% confidence)
                      </span>
                    )}
                  </div>
                )}

                {draftResult.bug_category && (
                  <div className="text-sm">
                    <span className="dark:text-[#68687a]">Category: </span>
                    <Badge variant="default" className="text-[10px]">{draftResult.bug_category}</Badge>
                  </div>
                )}

                <div>
                  <h4 className="text-sm font-medium mb-2 dark:text-[#d4d4dc]">Draft Response</h4>
                  <div className="p-4 rounded-lg dark:bg-[#0a0a12] light:bg-gray-100 border dark:border-[#1a1a28] light:border-[#e4e4e7] whitespace-pre-wrap text-sm font-mono max-h-[50vh] overflow-y-auto">
                    {draftResult.draft || JSON.stringify(draftResult, null, 2)}
                  </div>
                </div>

                {draftResult.suggested_evidence && draftResult.suggested_evidence.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium mb-2 dark:text-[#d4d4dc]">Suggested Evidence</h4>
                    <ul className="list-disc list-inside space-y-1 text-sm dark:text-[#68687a]">
                      {draftResult.suggested_evidence.map((ev: string, i: number) => (
                        <li key={i}>{ev}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </Card>
        </TabsContent>
      </Tabs>

      {/* Create Submission Modal */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>New Submission</DialogTitle>
            <DialogDescription>Create a new Immunefi bug submission.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate}>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Finding ID</label>
                <Input name="finding_id" placeholder="finding_..." required className="font-mono" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Program Slug</label>
                <Input name="program_slug" placeholder="e.g., project-name" required />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Bug Category</label>
                  <Select name="bug_category" required>
                    <option value="reentrancy">Reentrancy</option>
                    <option value="access_control">Access Control</option>
                    <option value="arithmetic">Arithmetic</option>
                    <option value="oracle">Oracle</option>
                    <option value="flash_loan">Flash Loan</option>
                    <option value="logic_error">Logic Error</option>
                    <option value="other">Other</option>
                  </Select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Severity</label>
                  <Select name="severity" required>
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </Select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Title</label>
                <Input name="title" placeholder="Brief bug title" required />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Description</label>
                <textarea
                  name="description"
                  rows={3}
                  placeholder="Describe the vulnerability..."
                  className="w-full rounded-lg px-3 py-2 text-sm resize-none dark:bg-[#0a0a12] light:bg-gray-50 dark:border dark:border-[#1a1a28] light:border light:border-[#e4e4e7] dark:text-[#d4d4dc] placeholder:text-[#68687a] focus:outline-none focus:ring-2 focus:ring-vyper-500/40"
                />
              </div>
            </div>
            {createError && <p className="mt-3 text-sm text-red-400">{createError}</p>}
            <DialogFooter className="mt-6">
              <Button type="button" variant="outline" onClick={() => setCreateOpen(false)} disabled={createLoading}>Cancel</Button>
              <Button type="submit" disabled={createLoading}>
                {createLoading ? <><Loader2 className="w-4 h-4 animate-spin" /> Creating...</> : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Detail Modal */}
      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Submission Detail</DialogTitle>
            <DialogDescription>Full submission data and message history.</DialogDescription>
          </DialogHeader>
          {detailLoading ? (
            <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin" /></div>
          ) : detailSubmission ? (
            <div className="space-y-4 max-h-[60vh] overflow-y-auto">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-xs dark:text-[#68687a]">Finding ID</div>
                  <div className="font-mono dark:text-[#d4d4dc]">{detailSubmission.finding_id}</div>
                </div>
                <div>
                  <div className="text-xs dark:text-[#68687a]">Program</div>
                  <div className="dark:text-[#d4d4dc]">{detailSubmission.program_slug}</div>
                </div>
                <div>
                  <div className="text-xs dark:text-[#68687a]">Category</div>
                  <Badge variant="secondary" className="text-[10px]">{detailSubmission.bug_category}</Badge>
                </div>
                <div>
                  <div className="text-xs dark:text-[#68687a]">Severity</div>
                  <StatusBadge status={detailSubmission.severity} />
                </div>
                <div>
                  <div className="text-xs dark:text-[#68687a]">Status</div>
                  <StatusBadge status={detailSubmission.status} />
                </div>
                <div>
                  <div className="text-xs dark:text-[#68687a]">Created</div>
                  <div className="text-xs dark:text-[#d4d4dc]">{formatDate(detailSubmission.created_at)}</div>
                </div>
              </div>
              <div>
                <div className="text-xs dark:text-[#68687a] mb-1">Title</div>
                <div className="text-sm font-medium dark:text-[#d4d4dc]">{detailSubmission.title}</div>
              </div>
              <div>
                <div className="text-xs dark:text-[#68687a] mb-1">Description</div>
                <p className="text-sm dark:text-[#d4d4dc]">{detailSubmission.description || '—'}</p>
              </div>
              {detailSubmission.messages && detailSubmission.messages.length > 0 && (
                <div>
                  <div className="text-xs dark:text-[#68687a] mb-2">Messages</div>
                  <div className="space-y-2">
                    {detailSubmission.messages.map((msg: any, i: number) => (
                      <div key={i} className="dark:bg-[#0a0a12] light:bg-gray-50 rounded-lg p-3 border dark:border-[#1a1a28]">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant={msg.role === 'us' ? 'default' : 'secondary'} className="text-[10px]">
                            {msg.role}
                          </Badge>
                          <span className="text-xs dark:text-[#68687a]">{formatDate(msg.created_at)}</span>
                        </div>
                        <p className="text-sm dark:text-[#d4d4dc]">{msg.content}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm dark:text-[#68687a] text-center py-4">{detailError || 'No data available.'}</p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDetailOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
