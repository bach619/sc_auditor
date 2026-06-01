import { useEffect, useState } from 'react'
import { api, type Program } from '../lib/api'
import { Card } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Badge } from '../components/ui/badge'
import { StatusBadge } from '../components/StatusBadge'
import { LoadingState } from '../components/LoadingState'
import { EmptyState } from '../components/EmptyState'
import { ErrorBanner } from '../components/ErrorBanner'
import { PageHeader } from '../components/PageHeader'
import { Search } from 'lucide-react'

export default function Programs() {
  const [programs, setPrograms] = useState<Program[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      try {
        const params: any = {}
        if (search) params.search = search
        const res = await api.getPrograms(params)
        if (!cancelled) {
          if (Array.isArray(res.data)) {
            setPrograms(res.data)
            setError('')
          } else if (res.data === null || res.data === undefined) {
            setPrograms([])
            setError('')
          } else {
            setPrograms([])
            setError('API returned unexpected format — expected a list of programs')
          }
        }
      } catch (err: any) {
        if (!cancelled) {
          const msg = err?.message || ''
          if (msg.includes('502') || msg.includes('Failed to fetch')) {
            setError('Backend is offline — start the server with: python app.py')
          } else {
            setError(msg || 'Failed to load programs')
          }
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [search])

  return (
    <div className="space-y-6">
      <PageHeader title="Programs" description="Immunefi bug bounty programs — fetch and monitor" />

      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      <div className="flex gap-4 items-center">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 dark:text-[#68687a] light:text-[#71717a]" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search programs..."
            className="pl-9"
          />
        </div>
      </div>

      {loading ? (
        <LoadingState message="Loading programs..." />
      ) : programs.length === 0 ? (
        <EmptyState message={search ? 'No programs match your search.' : 'No programs available yet.'} />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {programs.map((p) => (
            <Card key={p.slug}>
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-semibold dark:text-[#d4d4dc] light:text-[#09090b]">{p.name || p.slug}</h3>
                  <p className="text-xs font-mono dark:text-[#68687a] light:text-[#71717a] mt-0.5">{p.slug}</p>
                </div>
                <StatusBadge status={p.status || 'active'} />
              </div>
              {p.max_bounty && (
                <div className="text-sm mb-2">
                  <span className="dark:text-[#68687a] light:text-[#71717a]">Max Bounty: </span>
                  <span className="font-medium text-green-400">{p.max_bounty}</span>
                </div>
              )}
              {Array.isArray(p.chains) && p.chains.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-3">
                  {p.chains.map((chain) => (
                    <Badge key={chain} variant="secondary" className="text-[10px]">{chain}</Badge>
                  ))}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
