import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type ScopeContract } from '../lib/api'
import { Card } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { LoadingState } from '../components/LoadingState'
import { EmptyState } from '../components/EmptyState'
import { ErrorBanner } from '../components/ErrorBanner'
import { PageHeader } from '../components/PageHeader'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '../components/ui/table'
import { Search, ExternalLink, Bot, Play, Loader2, Shield, Globe, DollarSign } from 'lucide-react'

interface ScopeData {
  contracts: ScopeContract[]
  total: number
  offset: number
  limit: number
  stats: {
    total_scope_contracts: number
    unique_programs: number
    by_chain: Record<string, number>
  }
}

function shortAddr(addr: string): string {
  if (addr.length <= 16) return addr
  return `${addr.slice(0, 8)}...${addr.slice(-6)}`
}

function formatBounty(val?: number): string {
  if (val == null) return '—'
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(1)}M`
  if (val >= 1_000) return `$${(val / 1_000).toFixed(0)}K`
  return `$${val.toFixed(0)}`
}

export default function Programs() {
  const navigate = useNavigate()
  const [data, setData] = useState<ScopeData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [chainFilter, setChainFilter] = useState('')
  const [auditing, setAuditing] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.getScopeContracts({
        chain: chainFilter || undefined,
        limit: 500,
      })
      const d = res.data as ScopeData | null
      if (d && Array.isArray(d.contracts)) {
        // Apply local search filter
        if (search.trim()) {
          const q = search.toLowerCase()
          d.contracts = d.contracts.filter(
            (c) =>
              c.address.toLowerCase().includes(q) ||
              (c.name || '').toLowerCase().includes(q) ||
              (c.program_name || '').toLowerCase().includes(q) ||
              c.chain.toLowerCase().includes(q),
          )
        }
        setData(d)
      } else {
        setData(null)
        setError('Unexpected response format')
      }
    } catch (err: unknown) {
      setError((err as { message?: string })?.message || 'Failed to load contracts')
    } finally {
      setLoading(false)
    }
  }, [search, chainFilter])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: load contracts when search/filter changes
    load()
  }, [load])

  // Collect unique chains for filter
  const allChains = data?.contracts
    ? [...new Set(data.contracts.map((c) => c.chain).filter(Boolean))].sort()
    : []

  const handleAudit = async (contract: ScopeContract) => {
    setAuditing(contract.address)
    try {
      // Navigate to Antonio page with contract info — ChatPanel akan auto-suggest
      navigate('/agent', {
        state: {
          suggestAudit: `audit ${contract.address} on ${contract.chain}`,
          contractAddress: contract.address,
          chain: contract.chain,
          programName: contract.program_name,
        },
      })
    } finally {
      setAuditing(null)
    }
  }

  const handleOpenEtherscan = (address: string, chain: string) => {
    const explorers: Record<string, string> = {
      ethereum: 'https://etherscan.io/address/',
      bsc: 'https://bscscan.com/address/',
      polygon: 'https://polygonscan.com/address/',
      arbitrum: 'https://arbiscan.io/address/',
      optimism: 'https://optimistic.etherscan.io/address/',
      avalanche: 'https://snowtrace.io/address/',
    }
    const base = explorers[chain.toLowerCase()] || explorers.ethereum
    window.open(`${base}${address}`, '_blank', 'noopener')
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Smart Contracts"
        description={`${data?.total ?? 0} contracts siap audit dari ${data?.stats?.unique_programs ?? 0} program Immunefi`}
      />

      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      {/* Stats bar */}
      {data?.stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Card>
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-vyper-400" />
              <span className="text-xs dark:text-[#68687a]">Total Contracts</span>
            </div>
            <p className="text-xl font-bold mt-1 dark:text-[#d4d4dc]">{data.stats.total_scope_contracts}</p>
          </Card>
          <Card>
            <div className="flex items-center gap-2">
              <Bot className="w-4 h-4 text-vyper-400" />
              <span className="text-xs dark:text-[#68687a]">Programs</span>
            </div>
            <p className="text-xl font-bold mt-1 dark:text-[#d4d4dc]">{data.stats.unique_programs}</p>
          </Card>
          <Card>
            <div className="flex items-center gap-2">
              <Globe className="w-4 h-4 text-vyper-400" />
              <span className="text-xs dark:text-[#68687a]">Chains</span>
            </div>
            <p className="text-xl font-bold mt-1 dark:text-[#d4d4dc]">{Object.keys(data.stats.by_chain).length}</p>
          </Card>
          <Card>
            <div className="flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-green-400" />
              <span className="text-xs dark:text-[#68687a]">With Bounty</span>
            </div>
            <p className="text-xl font-bold mt-1 dark:text-[#d4d4dc]">
              {data.contracts.filter((c) => (c.program_max_bounty || 0) > 0).length}
            </p>
          </Card>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 items-center flex-wrap">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 dark:text-[#68687a] light:text-[#71717a]" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search address, name, program..."
            className="pl-9"
          />
        </div>
        <select
          value={chainFilter}
          onChange={(e) => setChainFilter(e.target.value)}
          className="h-10 rounded-lg px-3 text-sm dark:bg-[#0a0a12] light:bg-gray-50
            dark:border dark:border-[#1a1a28] light:border light:border-[#e4e4e7]
            dark:text-[#d4d4dc] light:text-gray-900"
        >
          <option value="">All Chains</option>
          {allChains.map((ch) => (
            <option key={ch} value={ch}>{ch}</option>
          ))}
        </select>
        <span className="text-xs dark:text-[#68687a]">
          {data?.contracts.length ?? 0} of {data?.total ?? 0}
        </span>
      </div>

      {/* Table */}
      {loading ? (
        <LoadingState message="Loading contracts..." />
      ) : !data || data.contracts.length === 0 ? (
        <EmptyState
          message={
            search || chainFilter
              ? 'No contracts match your filters.'
              : 'Belum ada smart contract yang di-fetch. Jalankan Immunefi sync dulu.'
          }
        />
      ) : (
        <Card className="overflow-hidden p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[140px]">Address</TableHead>
                <TableHead>Contract</TableHead>
                <TableHead className="w-[100px]">Chain</TableHead>
                <TableHead>Program</TableHead>
                <TableHead className="w-[100px] text-right">Max Bounty</TableHead>
                <TableHead className="w-[80px] text-center">Status</TableHead>
                <TableHead className="w-[100px] text-center">Audit</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.contracts.map((c, i) => (
                <TableRow key={`${c.address}-${i}`}>
                  {/* Address */}
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      <code className="text-xs font-mono dark:text-[#d4d4dc] text-gray-800">
                        {shortAddr(c.address)}
                      </code>
                      <button
                        onClick={() => handleOpenEtherscan(c.address, c.chain)}
                        className="dark:text-[#68687a] text-gray-400 hover:text-vyper-400 transition-colors"
                        title="Open in explorer"
                      >
                        <ExternalLink className="w-3 h-3" />
                      </button>
                    </div>
                  </TableCell>

                  {/* Contract name */}
                  <TableCell>
                    <span className="text-sm font-medium dark:text-[#d4d4dc]">
                      {c.name || '—'}
                    </span>
                  </TableCell>

                  {/* Chain */}
                  <TableCell>
                    <Badge variant="secondary" className="text-[10px]">
                      {c.chain}
                    </Badge>
                  </TableCell>

                  {/* Program */}
                  <TableCell>
                    <div>
                      <span className="text-sm dark:text-[#d4d4dc]">{c.program_name || c.program_slug}</span>
                      <div className="text-[10px] dark:text-[#68687a] font-mono">{c.program_slug}</div>
                    </div>
                  </TableCell>

                  {/* Max bounty */}
                  <TableCell className="text-right">
                    <span className="text-sm font-medium text-green-400">
                      {formatBounty(c.program_max_bounty)}
                    </span>
                  </TableCell>

                  {/* Status */}
                  <TableCell className="text-center">
                    <span
                      className={`inline-block w-2 h-2 rounded-full ${
                        c.program_status === 'active' || c.program_status === 'live'
                          ? 'bg-green-500'
                          : 'bg-gray-500'
                      }`}
                      title={c.program_status}
                    />
                  </TableCell>

                  {/* Audit button */}
                  <TableCell className="text-center">
                    <Button
                      size="sm"
                      variant="default"
                      disabled={auditing === c.address}
                      onClick={() => handleAudit(c)}
                      className="text-xs h-8"
                    >
                      {auditing === c.address ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <Play className="w-3 h-3" />
                      )}
                      Audit
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  )
}
