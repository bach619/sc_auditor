import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Card } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { StatusBadge } from '../components/StatusBadge'
import { LoadingState } from '../components/LoadingState'
import { EmptyState } from '../components/EmptyState'
import { ErrorBanner } from '../components/ErrorBanner'
import { PageHeader } from '../components/PageHeader'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/table'
import { formatDate } from '../lib/utils'
import { Webhook, RefreshCw, Loader2 } from 'lucide-react'
import { Button } from '../components/ui/button'

export default function Webhooks() {
  const [logs, setLogs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [expandedLog, setExpandedLog] = useState<string | null>(null)

  async function loadLogs() {
    try {
      const res = await api.getWebhookLogs(100)
      setLogs(Array.isArray(res.data) ? res.data : [])
      setError('')
    } catch (err: any) {
      setError(err?.message || 'Failed to load webhook logs')
    }
  }

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      await loadLogs()
      if (!cancelled) setLoading(false)
    }
    load()
    return () => { cancelled = true }
  }, [])

  async function handleRefresh() {
    setRefreshing(true)
    await loadLogs()
    setRefreshing(false)
  }

  if (loading) return <LoadingState message="Loading webhook logs..." />

  return (
    <div className="space-y-6">
      <PageHeader title="Webhooks" description="Incoming webhook events and payload logs" />

      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      <div className="flex justify-end">
        <Button variant="outline" onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </Button>
      </div>

      <Card>
        <h3 className="font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b] flex items-center gap-2">
          <Webhook className="w-4 h-4 text-vyper-400" /> Event Logs
        </h3>
        {logs.length === 0 ? (
          <EmptyState message="No webhook events received yet." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Event ID</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Event Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Timestamp</TableHead>
                <TableHead>Payload</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.map((log: any, i: number) => {
                const rowId = log.id || log.event_id || String(i)
                const isExpanded = expandedLog === rowId
                return (
                  <TableRow key={rowId}>
                    <TableCell className="font-mono text-xs">{rowId.slice(0, 16)}</TableCell>
                    <TableCell className="text-xs">{log.source || log.service || '—'}</TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="text-[10px]">{log.event_type || log.type || log.event || 'unknown'}</Badge>
                    </TableCell>
                    <TableCell><StatusBadge status={log.status || (log.error ? 'error' : 'received')} /></TableCell>
                    <TableCell className="text-xs dark:text-[#68687a]">{formatDate(log.timestamp || log.received_at || log.created_at)}</TableCell>
                    <TableCell>
                      <button
                        onClick={() => setExpandedLog(isExpanded ? null : rowId)}
                        className="text-xs text-vyper-400 hover:text-vyper-300 transition-colors"
                      >
                        {isExpanded ? 'Hide' : 'View'}
                      </button>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
      </Card>

      {/* Expanded Payload */}
      {expandedLog && (
        <Card>
          <h3 className="font-semibold mb-3 dark:text-[#d4d4dc] light:text-[#09090b]">Payload Details</h3>
          {(() => {
            const log = logs.find((l: any) => (l.id || l.event_id || '') === expandedLog)
            if (!log) return <p className="text-sm dark:text-[#68687a]">Log not found.</p>
            return (
              <pre className="p-4 rounded-lg dark:bg-[#0a0a12] light:bg-gray-100 border dark:border-[#1a1a28] light:border-[#e4e4e7] overflow-x-auto text-xs font-mono max-h-[50vh] whitespace-pre-wrap">
                {JSON.stringify(log.payload || log.data || log, null, 2)}
              </pre>
            )
          })()}
        </Card>
      )}
    </div>
  )
}
