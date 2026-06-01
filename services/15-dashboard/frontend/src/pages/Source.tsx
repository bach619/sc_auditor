import { useState } from 'react'
import { api } from '../lib/api'
import { Card } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Button } from '../components/ui/button'
import { PageHeader } from '../components/PageHeader'
import { ErrorBanner } from '../components/ErrorBanner'
import { Search, FileCode, Loader2, Copy, Check } from 'lucide-react'

export default function Source() {
  const [auditId, setAuditId] = useState('')
  const [source, setSource] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  async function handleSearch() {
    if (!auditId.trim()) return
    setLoading(true)
    setError('')
    setSource(null)
    try {
      const res = await api.getSourceCode(auditId)
      setSource(res.data || {})
    } catch (err: any) {
      setError(err?.message || 'Failed to load source code')
    } finally { setLoading(false) }
  }

  async function handleCopy() {
    if (!source?.content && !source?.source_code && !source?.code) return
    const text = source.content || source.source_code || source.code || JSON.stringify(source, null, 2)
    try {
      await navigator.clipboard.writeText(typeof text === 'string' ? text : JSON.stringify(text, null, 2))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {}
  }

  const codeContent = source?.content || source?.source_code || source?.code || ''
  const language = source?.language || source?.compiler_version || 'solidity'

  return (
    <div className="space-y-6">
      <PageHeader title="Source Code" description="View smart contract source code by audit ID" />

      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      <Card>
        <h3 className="font-semibold mb-3 dark:text-[#d4d4dc] light:text-[#09090b]">Source Code Lookup</h3>
        <div className="flex gap-3">
          <Input
            value={auditId}
            onChange={(e) => setAuditId(e.target.value)}
            placeholder="Enter Audit ID..."
            className="max-w-md font-mono"
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
          <Button onClick={handleSearch} disabled={loading || !auditId.trim()}>
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            Search
          </Button>
        </div>
      </Card>

      {source && (
        <Card>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <FileCode className="w-5 h-5 text-vyper-400" />
              <h3 className="font-semibold dark:text-[#d4d4dc] light:text-[#09090b]">Source Code</h3>
            </div>
            <Button variant="outline" size="sm" onClick={handleCopy} disabled={!codeContent}>
              {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
              {copied ? 'Copied' : 'Copy'}
            </Button>
          </div>

          {source.metadata && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4 text-sm">
              {Object.entries(source.metadata).map(([key, val]: [string, any]) => (
                <div key={key}>
                  <div className="text-xs dark:text-[#68687a] light:text-[#71717a] capitalize">{key.replace(/_/g, ' ')}</div>
                  <div className="font-medium dark:text-[#d4d4dc] mt-0.5 truncate">{String(val)}</div>
                </div>
              ))}
            </div>
          )}

          {source.contract_name && (
            <div className="mb-4 text-sm">
              <span className="dark:text-[#68687a] light:text-[#71717a]">Contract: </span>
              <span className="font-mono dark:text-[#d4d4dc]">{source.contract_name}</span>
              {source.address && (
                <><span className="dark:text-[#68687a] light:text-[#71717a]"> at </span>
                <span className="font-mono text-xs dark:text-[#d4d4dc]">{source.address}</span></>
              )}
            </div>
          )}

          {codeContent ? (
            <pre className="p-4 rounded-lg dark:bg-[#0a0a12] light:bg-gray-100 border dark:border-[#1a1a28] light:border-[#e4e4e7] overflow-x-auto text-xs font-mono max-h-[70vh] whitespace-pre-wrap">
              {typeof codeContent === 'string' ? codeContent : JSON.stringify(codeContent, null, 2)}
            </pre>
          ) : (
            <pre className="p-4 rounded-lg dark:bg-[#0a0a12] light:bg-gray-100 text-xs font-mono overflow-x-auto">
              {JSON.stringify(source, null, 2)}
            </pre>
          )}

          {language && (
            <div className="mt-3 flex gap-2">
              <span className="text-xs px-2 py-0.5 rounded dark:bg-[#0a0a12] light:bg-gray-100 font-mono dark:text-[#68687a]">
                {language}
              </span>
              {source.chain && (
                <span className="text-xs px-2 py-0.5 rounded dark:bg-[#0a0a12] light:bg-gray-100 font-mono dark:text-[#68687a]">
                  {source.chain}
                </span>
              )}
            </div>
          )}
        </Card>
      )}

      {!source && !loading && (
        <Card>
          <div className="text-center py-8">
            <FileCode className="w-12 h-12 mx-auto mb-3 dark:text-[#3a3a4a] light:text-[#d4d4d8]" />
            <p className="text-sm dark:text-[#68687a] light:text-[#71717a]">Enter an Audit ID to view source code</p>
          </div>
        </Card>
      )}
    </div>
  )
}
