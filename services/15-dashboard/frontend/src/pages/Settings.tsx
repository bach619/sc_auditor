import { useState, useEffect } from 'react'
import { api } from '../lib/api'
import { Card } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Select } from '../components/ui/select'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { StatusBadge } from '../components/StatusBadge'
import { LoadingState } from '../components/LoadingState'
import { ErrorBanner } from '../components/ErrorBanner'
import { PageHeader } from '../components/PageHeader'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/table'
import { Separator } from '../components/ui/separator'
import { Check, X, Save, Eye, EyeOff, Loader2, Key, Cpu, Sliders } from 'lucide-react'

const PROVIDERS = [
  { id: 'openai', name: 'OpenAI', icon: 'O', color: '#10a37f',
    docUrl: 'https://platform.openai.com/api-keys',
    apiKeyField: 'provider_openai_api_key', baseUrlField: 'provider_openai_base_url',
    variants: [
      { id: 'gpt-5.4-pro', name: 'GPT-5.4 Pro' },
      { id: 'gpt-5.4-pro-mini', name: 'GPT-5.4 Pro Mini' },
      { id: 'gpt-5.4-flash', name: 'GPT-5.4 Flash' },
    ] },
  { id: 'anthropic', name: 'Anthropic', icon: 'A', color: '#d97757',
    docUrl: 'https://console.anthropic.com/settings/keys',
    apiKeyField: 'provider_anthropic_api_key', baseUrlField: 'provider_anthropic_base_url',
    variants: [
      { id: 'claude-opus-4-7', name: 'Claude Opus 4.7' },
      { id: 'claude-sonnet-4-7', name: 'Claude Sonnet 4.7' },
      { id: 'claude-haiku-4-7', name: 'Claude Haiku 4.7' },
    ] },
  { id: 'google', name: 'Google AI', icon: 'G', color: '#4285f4',
    docUrl: 'https://aistudio.google.com/app/apikey',
    apiKeyField: 'provider_google_api_key', baseUrlField: 'provider_google_base_url',
    variants: [
      { id: 'gemini-3.1-pro', name: 'Gemini 3.1 Pro Preview' },
      { id: 'gemini-3.1-flash', name: 'Gemini 3.1 Flash' },
    ] },
  { id: 'deepseek', name: 'DeepSeek', icon: 'D', color: '#4f46e5',
    docUrl: 'https://platform.deepseek.com/api_keys',
    apiKeyField: 'provider_deepseek_api_key', baseUrlField: 'provider_deepseek_base_url',
    variants: [
      { id: 'deepseek-v4-pro', name: 'DeepSeek V4-Pro' },
      { id: 'deepseek-v4-flash', name: 'DeepSeek V4 Flash' },
    ] },
  { id: 'xai', name: 'xAI (Grok)', icon: 'X', color: '#1a1a2e',
    docUrl: 'https://console.x.ai/',
    apiKeyField: 'provider_xai_api_key', baseUrlField: 'provider_xai_base_url',
    variants: [
      { id: 'grok-4.20-expert', name: 'Grok-4.20 Expert' },
      { id: 'grok-4.20-base', name: 'Grok-4.20 Base' },
    ] },
]

const USE_CASES = [
  { id: 'ai_analysis_model', label: 'Analysis', default: 'claude-opus-4-7', recommendation: 'Smart Contract Audit' },
  { id: 'ai_classification_model', label: 'Classification', default: 'gpt-5.4-pro', recommendation: 'Fast General Intelligence' },
  { id: 'ai_exploit_model', label: 'Exploit Gen', default: 'deepseek-v4-pro', recommendation: 'Cost-effective Bulk' },
]

const ALL_VARIANTS = PROVIDERS.flatMap(p => p.variants.map(v => ({ ...v, providerId: p.id, providerName: p.name })))

export default function Settings() {
  const [config, setConfig] = useState<Record<string, any>>({})
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({})
  const [baseUrls, setBaseUrls] = useState<Record<string, string>>({})
  const [useCaseSelections, setUseCaseSelections] = useState<Record<string, string>>({})
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  useEffect(() => {
    (async () => {
      try {
        const res = await api.getConfig()
        const cfg = res.data || {}
        setConfig(cfg)
        const initialKeys: Record<string, string> = {}
        const initialUrls: Record<string, string> = {}
        for (const p of PROVIDERS) {
          initialKeys[p.id] = cfg[p.apiKeyField] || ''
          initialUrls[p.id] = cfg[p.baseUrlField] || ''
        }
        setApiKeys(initialKeys)
        setBaseUrls(initialUrls)
        const initialSelections: Record<string, string> = {}
        for (const uc of USE_CASES) {
          initialSelections[uc.id] = cfg[uc.id] || uc.default
        }
        setUseCaseSelections(initialSelections)
      } catch (err: any) {
        setStatus({ type: 'error', message: `Failed to load config: ${err.message}` })
      } finally { setLoading(false) }
    })()
  }, [])

  useEffect(() => {
    if (!status) return
    const id = setTimeout(() => setStatus(null), 5000)
    return () => clearTimeout(id)
  }, [status])

  const hasKey = (providerId: string) => {
    const val = apiKeys[providerId] || ''
    return val.trim().length > 0 && !val.startsWith('${')
  }

  const hasChanges = () => {
    for (const p of PROVIDERS) {
      if ((apiKeys[p.id] || '') !== (config[p.apiKeyField] || '')) return true
      if ((baseUrls[p.id] || '') !== (config[p.baseUrlField] || '')) return true
    }
    for (const uc of USE_CASES) {
      if ((useCaseSelections[uc.id] || uc.default) !== (config[uc.id] || uc.default)) return true
    }
    return false
  }

  const handleSave = async () => {
    setSaving(true)
    setStatus(null)
    try {
      const payload: Record<string, any> = {}
      for (const p of PROVIDERS) {
        payload[p.apiKeyField] = apiKeys[p.id] || ''
        payload[p.baseUrlField] = baseUrls[p.id] || ''
      }
      for (const uc of USE_CASES) payload[uc.id] = useCaseSelections[uc.id] || uc.default
      await api.setBulkConfig(payload)
      setStatus({ type: 'success', message: 'Settings saved successfully.' })
      setConfig(prev => ({ ...prev, ...payload }))
    } catch (err: any) {
      setStatus({ type: 'error', message: `Failed to save: ${err.message}` })
    } finally { setSaving(false) }
  }

  if (loading) return <LoadingState message="Loading configuration..." />

  return (
    <div className="space-y-8 max-w-4xl">
      <PageHeader title="Settings" description="AI model configuration and provider API keys" />

      {/* Status */}
      {status && (
        <div className={`flex items-center gap-2.5 px-4 py-3 rounded-lg text-sm border ${
          status.type === 'success'
            ? 'dark:bg-green-500/10 light:bg-green-500/5 dark:border-green-500/30 light:border-green-500/20 dark:text-green-400 light:text-green-700'
            : 'dark:bg-red-500/10 light:bg-red-500/5 dark:border-red-500/30 light:border-red-500/20 dark:text-red-400 light:text-red-700'
        }`}>
          {status.type === 'success' ? <Check className="w-4 h-4" /> : <X className="w-4 h-4" />}
          <span>{status.message}</span>
          <button onClick={() => setStatus(null)} className="ml-auto opacity-60 hover:opacity-100">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Provider API Keys */}
      <section>
        <h2 className="text-base font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b] flex items-center gap-2.5">
          <Key className="w-5 h-5 text-vyper-400" /> Provider API Keys
        </h2>
        <Card className="p-0 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Provider</TableHead>
                <TableHead>API Key</TableHead>
                <TableHead>Base URL</TableHead>
                <TableHead className="text-center w-20">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {PROVIDERS.map(p => (
                <TableRow key={p.id}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-sm font-bold flex-shrink-0"
                        style={{ backgroundColor: p.color }}>{p.icon}</div>
                      <span className="font-medium dark:text-[#d4d4dc]">{p.name}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="relative max-w-xs">
                      <Input
                        type={visibleKeys.has(p.id) ? 'text' : 'password'}
                        value={apiKeys[p.id] || ''}
                        onChange={e => setApiKeys(prev => ({ ...prev, [p.id]: e.target.value }))}
                        placeholder="sk-..."
                        className="pr-8 font-mono text-xs"
                      />
                      <button onClick={() => setVisibleKeys(prev => { const n = new Set(prev); n.has(p.id) ? n.delete(p.id) : n.add(p.id); return n })}
                        className="absolute right-2 top-1/2 -translate-y-1/2 dark:text-[#3a3a4a] light:text-[#a1a1aa] hover:dark:text-[#68687a]">
                        {visibleKeys.has(p.id) ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Input
                      value={baseUrls[p.id] || ''}
                      onChange={e => setBaseUrls(prev => ({ ...prev, [p.id]: e.target.value }))}
                      placeholder="https://api.openai.com"
                      className="font-mono text-xs max-w-xs"
                    />
                  </TableCell>
                  <TableCell className="text-center">
                    {hasKey(p.id)
                      ? <span className="inline-flex items-center gap-1 text-xs text-green-400"><Check className="w-3 h-3" /> Ready</span>
                      : <span className="inline-flex items-center gap-1 text-xs dark:text-[#3a3a4a]"><X className="w-3 h-3" /> Missing</span>}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </section>

      {/* Model Variants */}
      <section>
        <h2 className="text-base font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b] flex items-center gap-2.5">
          <Cpu className="w-5 h-5 text-vyper-400" /> Available Models
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
          {ALL_VARIANTS.map(v => {
            const provider = PROVIDERS.find(p => p.id === v.providerId)
            const configured = provider ? hasKey(provider.id) : false
            return (
              <div key={v.id}
                className={`flex items-center gap-3 dark:bg-[#0a0a12] light:bg-white rounded-lg border dark:border-[#1a1a28] light:border-[#e4e4e7] px-3.5 py-2.5 transition-all ${configured ? '' : 'opacity-50'}`}>
                <div className="w-7 h-7 rounded-md flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
                  style={{ backgroundColor: provider?.color || '#3a3a4a' }}>
                  {v.providerId.charAt(0).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate dark:text-[#d4d4dc]">{v.name}</div>
                  <div className="text-xs dark:text-[#68687a] truncate">{v.providerName}</div>
                </div>
                {!configured && <X className="w-3.5 h-3.5 flex-shrink-0 ml-auto dark:text-[#3a3a4a]" />}
              </div>
            )
          })}
        </div>
      </section>

      {/* Use Case Assignment */}
      <section>
        <h2 className="text-base font-semibold mb-4 dark:text-[#d4d4dc] light:text-[#09090b] flex items-center gap-2.5">
          <Sliders className="w-5 h-5 text-vyper-400" /> Use Case Assignment
        </h2>
        <Card className="p-0 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Task</TableHead>
                <TableHead>Assigned Model</TableHead>
                <TableHead>Recommendation</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {USE_CASES.map(uc => (
                <TableRow key={uc.id}>
                  <TableCell><span className="font-medium dark:text-[#d4d4dc]">{uc.label}</span></TableCell>
                  <TableCell>
                    <Select
                      value={useCaseSelections[uc.id] || uc.default}
                      onChange={e => setUseCaseSelections(prev => ({ ...prev, [uc.id]: e.target.value }))}
                      className="max-w-xs">
                      {ALL_VARIANTS.map(v => (
                        <option key={v.id} value={v.id} disabled={!hasKey(v.providerId)}>
                          {v.name} — {v.providerName}{!hasKey(v.providerId) ? ' (requires key)' : ''}
                        </option>
                      ))}
                    </Select>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <span className="text-xs dark:text-[#68687a]">{uc.recommendation}</span>
                      {useCaseSelections[uc.id] === uc.default && (
                        <Badge variant="default" className="text-[10px]">Default</Badge>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </section>

      {/* Save */}
      <div className="flex items-center justify-between pb-6">
        <div className="text-xs dark:text-[#68687a]">
          {hasChanges()
            ? <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-yellow-400" /> Unsaved changes</span>
            : <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-green-400" /> All saved</span>}
        </div>
        <Button onClick={handleSave} disabled={saving || !hasChanges()}>
          {saving ? <><Loader2 className="w-4 h-4 animate-spin" /> Saving...</> : <><Save className="w-4 h-4" /> Save Settings</>}
        </Button>
      </div>
    </div>
  )
}
