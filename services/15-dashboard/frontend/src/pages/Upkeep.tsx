import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Card } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { StatusBadge } from '../components/StatusBadge'
import { StatCard } from '../components/StatCard'
import { LoadingState } from '../components/LoadingState'
import { EmptyState } from '../components/EmptyState'
import { ErrorBanner } from '../components/ErrorBanner'
import { PageHeader } from '../components/PageHeader'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/table'
import { formatDate } from '../lib/utils'
import { Timer, RefreshCw, Loader2, Calendar, Clock, Activity } from 'lucide-react'
import { Button } from '../components/ui/button'

export default function Upkeep() {
  const [status, setStatus] = useState<any>(null)
  const [logs, setLogs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  async function loadData() {
    try {
      const [statusRes, logsRes] = await Promise.all([
        api.getUpkeepStatus().catch(() => ({ data: null })),
        api.getUpkeepLogs(100).catch(() => ({ data: [] })),
      ])
      setStatus(statusRes.data)
      setLogs(Array.isArray(logsRes.data) ? logsRes.data : [])
      setError('')
    } catch (err: any) {
      setError(err?.message || 'Failed to load upkeep data')
    }
  }

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      await loadData()
      if (!cancelled) setLoading(false)
    }
    load()
    return () => { cancelled = true }
  }, [])

  async function handleRefresh() {
    setRefreshing(true)
    await loadData()
    setRefreshing(false)
  }

  if (loading) return <LoadingState message="Loading scheduler status..." />

  return (
    <div className="space-y-6">
      <PageHeader title="Upkeep" description="Scheduler, cron jobs, and recurring task management" />

      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      {/* Status Cards */}
      {status && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Status" value={status.running ? 'Running' : 'Stopped'}
            accent accentColor={status.running ? 'green' : 'yellow'} />
          <StatCard label="Interval" value={status.interval ? `${status.interval}s` : '—'}
            subtext={status.interval ? `Every ${status.interval}s` : undefined} />
          <StatCard label="Jobs Active" value={status.active_jobs ?? status.jobs_count ?? 0} />
          <StatCard label="Last Run" value={status.last_run_at ? formatDate(status.last_run_at) : '—'} />
        </div>
      )}

      {status && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <StatCard label="Total Runs" value={status.total_runs ?? status.total_executions ?? 0} />
          <StatCard label="Failed Runs" value={status.failed_runs ?? status.failures ?? 0} accent accentColor="red" />
          <StatCard label="Avg Duration" value={status.avg_duration_ms ? `${status.avg_duration_ms}ms` : '—'} />
        </div>
      )}

      <div className="flex justify-end">
        <Button variant="outline" onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </Button>
      </div>

      <Tabs defaultValue="jobs">
        <TabsList>
          <TabsTrigger value="jobs">Jobs</TabsTrigger>
          <TabsTrigger value="logs">Execution Logs</TabsTrigger>
        </TabsList>

        {/* Jobs Tab */}
        <TabsContent value="jobs">
          {status?.jobs && Array.isArray(status.jobs) && status.jobs.length > 0 ? (
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Job ID</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Schedule</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Last Run</TableHead>
                    <TableHead>Next Run</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {status.jobs.map((job: any, i: number) => (
                    <TableRow key={job.id || job.name || i}>
                      <TableCell className="font-mono text-xs">{job.id ? job.id.slice(0, 12) : '—'}</TableCell>
                      <TableCell className="font-medium dark:text-[#d4d4dc]">{job.name || 'Unknown'}</TableCell>
                      <TableCell className="text-xs font-mono">{job.schedule || job.cron || job.interval ? `every ${job.interval}s` : '—'}</TableCell>
                      <TableCell><StatusBadge status={job.enabled ? (job.running ? 'running' : 'idle') : 'disabled'} /></TableCell>
                      <TableCell className="text-xs dark:text-[#68687a]">{formatDate(job.last_run_at)}</TableCell>
                      <TableCell className="text-xs dark:text-[#68687a]">{formatDate(job.next_run_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          ) : (
            <Card><p className="text-sm dark:text-[#68687a] text-center py-8">No scheduled jobs configured.</p></Card>
          )}
        </TabsContent>

        {/* Logs Tab */}
        <TabsContent value="logs">
          {logs.length === 0 ? (
            <EmptyState message="No execution logs yet." />
          ) : (
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Job</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead>Details</TableHead>
                    <TableHead>Timestamp</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs.map((log: any, i: number) => (
                    <TableRow key={log.id || i}>
                      <TableCell className="text-sm">{log.job_name || log.job || log.task || '—'}</TableCell>
                      <TableCell>
                        <StatusBadge status={log.status || (log.error ? 'failed' : 'completed')} />
                      </TableCell>
                      <TableCell className="font-mono text-xs">{log.duration_ms ? `${log.duration_ms}ms` : log.duration ? `${log.duration}s` : '—'}</TableCell>
                      <TableCell className="max-w-xs truncate text-xs dark:text-[#68687a]">{log.message || log.result || log.error || '—'}</TableCell>
                      <TableCell className="text-xs dark:text-[#68687a]">{formatDate(log.timestamp || log.executed_at || log.created_at)}</TableCell>
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
