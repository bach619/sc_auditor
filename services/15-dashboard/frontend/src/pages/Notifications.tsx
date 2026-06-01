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
import { formatDate } from '../lib/utils'
import { Bell, Send, Mail, MessageSquare, Globe, Loader2, Check, X } from 'lucide-react'

const CHANNEL_ICONS: Record<string, any> = {
  discord: MessageSquare,
  slack: MessageSquare,
  email: Mail,
  webhook: Globe,
  telegram: Send,
}

const CHANNEL_COLORS: Record<string, string> = {
  discord: '#5865f2',
  slack: '#4a154b',
  email: '#ea4335',
  webhook: '#34a853',
  telegram: '#0088cc',
}

export default function Notifications() {
  const [channels, setChannels] = useState<Record<string, any>>({})
  const [logs, setLogs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [testChannel, setTestChannel] = useState('discord')
  const [testSending, setTestSending] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [channelsRes, logsRes] = await Promise.all([
          api.getNotifierChannels().catch(() => ({ data: {} })),
          api.getNotifierLogs(50).catch(() => ({ data: [] })),
        ])
        if (!cancelled) {
          setChannels((channelsRes.data as Record<string, any>) || {})
          setLogs(Array.isArray(logsRes.data) ? logsRes.data : [])
        }
      } catch {}
      if (!cancelled) setLoading(false)
    }
    load()
    return () => { cancelled = true }
  }, [])

  async function handleTestNotification() {
    setTestSending(true)
    setTestResult(null)
    try {
      await api.testNotification(testChannel)
      setTestResult({ success: true, message: `Test notification sent to ${testChannel}` })
    } catch (err: any) {
      setTestResult({ success: false, message: err?.message || 'Failed to send test notification' })
    } finally { setTestSending(false) }
  }

  if (loading) return <LoadingState message="Loading notification channels..." />

  return (
    <div className="space-y-6">
      <PageHeader title="Notifications" description="Manage notification channels and view delivery logs" />

      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      {/* Channel Status */}
      <Card>
        <h3 className="font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b] flex items-center gap-2">
          <Bell className="w-4 h-4 text-vyper-400" /> Notification Channels
        </h3>
        {Object.keys(channels).length === 0 ? (
          <p className="text-sm dark:text-[#68687a] text-center py-4">No channels configured.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {Object.entries(channels).map(([name, config]: [string, any]) => {
              const Icon = CHANNEL_ICONS[name] || Send
              const color = CHANNEL_COLORS[name] || '#68687a'
              const enabled = config.enabled !== false
              return (
                <div key={name} className="dark:bg-[#0a0a12] light:bg-gray-50 rounded-lg p-4 border dark:border-[#1a1a28] light:border-[#e4e4e7]">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: color + '20' }}>
                      <Icon className="w-4 h-4" style={{ color }} />
                    </div>
                    <div>
                      <div className="text-sm font-medium capitalize dark:text-[#d4d4dc]">{name}</div>
                      <StatusBadge status={enabled ? 'active' : 'disabled'} />
                    </div>
                  </div>
                  {config.type && <div className="text-xs dark:text-[#68687a] mt-1">Type: {config.type}</div>}
                  {config.last_sent && <div className="text-xs dark:text-[#68687a]">Last sent: {formatDate(config.last_sent)}</div>}
                </div>
              )
            })}
          </div>
        )}
      </Card>

      {/* Test Notification */}
      <Card>
        <h3 className="font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b]">Test Notification</h3>
        <div className="flex gap-3 items-end">
          <div className="flex-1 max-w-xs">
            <label className="block text-sm font-medium mb-1 dark:text-[#d4d4dc] light:text-[#09090b]">Channel</label>
            <Select value={testChannel} onChange={(e) => setTestChannel(e.target.value)}>
              {Object.keys(channels).length > 0
                ? Object.keys(channels).map((ch) => <option key={ch} value={ch}>{ch}</option>)
                : <option value="discord">Discord</option>
              }
              <option value="slack">Slack</option>
              <option value="email">Email</option>
              <option value="webhook">Webhook</option>
              <option value="telegram">Telegram</option>
            </Select>
          </div>
          <Button onClick={handleTestNotification} disabled={testSending}>
            {testSending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            {testSending ? 'Sending...' : 'Send Test'}
          </Button>
        </div>
        {testResult && (
          <div className={`mt-3 flex items-center gap-2 text-sm ${testResult.success ? 'text-green-400' : 'text-red-400'}`}>
            {testResult.success ? <Check className="w-4 h-4" /> : <X className="w-4 h-4" />}
            {testResult.message}
          </div>
        )}
      </Card>

      {/* Delivery Logs */}
      <Card>
        <h3 className="font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b]">Delivery Logs</h3>
        {logs.length === 0 ? (
          <EmptyState message="No delivery logs yet." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Channel</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Message</TableHead>
                <TableHead>Timestamp</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.map((log: any, i: number) => (
                <TableRow key={log.id || i}>
                  <TableCell className="capitalize">{log.channel || log.channel_name || '—'}</TableCell>
                  <TableCell>
                    <StatusBadge status={log.status || (log.success ? 'delivered' : 'failed')} />
                  </TableCell>
                  <TableCell className="max-w-xs truncate text-xs">{log.message || log.content || log.error || '—'}</TableCell>
                  <TableCell className="text-xs dark:text-[#68687a]">{formatDate(log.timestamp || log.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  )
}
