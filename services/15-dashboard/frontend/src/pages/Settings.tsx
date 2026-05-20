import { useState, useEffect } from 'react';
import { api } from '../lib/api';

const PROVIDERS = [
  { id: 'openai', name: 'OpenAI', icon: 'O', color: '#10a37f',
    docUrl: 'https://platform.openai.com/api-keys',
    apiKeyField: 'provider_openai_api_key', baseUrlField: 'provider_openai_base_url',
    variants: [
      { id: 'gpt-5.4-pro', name: 'GPT-5.4 Pro (Vision)' },
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
      { id: 'deepseek-v4-pro', name: 'DeepSeek V4-Pro (1.6T)' },
      { id: 'deepseek-v4-flash', name: 'DeepSeek V4 Flash' },
    ] },
  { id: 'xai', name: 'xAI (Grok)', icon: 'X', color: '#1a1a2e',
    docUrl: 'https://console.x.ai/',
    apiKeyField: 'provider_xai_api_key', baseUrlField: 'provider_xai_base_url',
    variants: [
      { id: 'grok-4.20-expert', name: 'Grok-4.20 Expert Mode' },
      { id: 'grok-4.20-base', name: 'Grok-4.20 Base' },
    ] },
];

const USE_CASES = [
  { id: 'ai_analysis_model', label: 'Analysis', default: 'claude-opus-4-7', recommendation: 'Coding & Smart Contract Audit' },
  { id: 'ai_classification_model', label: 'Classification', default: 'gpt-5.4-pro', recommendation: 'Fast General Intelligence' },
  { id: 'ai_exploit_model', label: 'Exploit Gen', default: 'deepseek-v4-pro', recommendation: 'Cost-effective Bulk' },
];

const ALL_VARIANTS = PROVIDERS.flatMap(p => p.variants.map(v => ({ ...v, providerId: p.id, providerName: p.name })));

export default function Settings() {
  const [config, setConfig] = useState<Record<string, any>>({});
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [baseUrls, setBaseUrls] = useState<Record<string, string>>({});
  const [useCaseSelections, setUseCaseSelections] = useState<Record<string, string>>({});
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.getConfig();
        const cfg = res.data || {};
        setConfig(cfg);

        const initialKeys: Record<string, string> = {};
        const initialUrls: Record<string, string> = {};
        for (const p of PROVIDERS) {
          initialKeys[p.id] = cfg[p.apiKeyField] || '';
          initialUrls[p.id] = cfg[p.baseUrlField] || '';
        }
        setApiKeys(initialKeys);
        setBaseUrls(initialUrls);

        const initialSelections: Record<string, string> = {};
        for (const uc of USE_CASES) {
          initialSelections[uc.id] = cfg[uc.id] || uc.default;
        }
        setUseCaseSelections(initialSelections);
      } catch (err: any) {
        setStatus({ type: 'error', message: `Failed to load config: ${err.message}` });
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!status) return;
    const id = setTimeout(() => setStatus(null), 5000);
    return () => clearTimeout(id);
  }, [status]);

  const hasKey = (providerId: string) => {
    const val = apiKeys[providerId] || '';
    return val.trim().length > 0 && !val.startsWith('${');
  };

  const toggleKeyVisibility = (providerId: string) => {
    setVisibleKeys(prev => {
      const next = new Set(prev);
      if (next.has(providerId)) next.delete(providerId);
      else next.add(providerId);
      return next;
    });
  };

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    try {
      const payload: Record<string, any> = {};
      for (const p of PROVIDERS) {
        payload[p.apiKeyField] = apiKeys[p.id] || '';
        payload[p.baseUrlField] = baseUrls[p.id] || '';
      }
      for (const uc of USE_CASES) {
        payload[uc.id] = useCaseSelections[uc.id] || uc.default;
      }
      await api.setBulkConfig(payload);
      setStatus({ type: 'success', message: 'Settings saved successfully.' });
      setConfig(prev => ({ ...prev, ...payload }));
    } catch (err: any) {
      setStatus({ type: 'error', message: `Failed to save: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = () => {
    for (const p of PROVIDERS) {
      if ((apiKeys[p.id] || '') !== (config[p.apiKeyField] || '')) return true;
      if ((baseUrls[p.id] || '') !== (config[p.baseUrlField] || '')) return true;
    }
    for (const uc of USE_CASES) {
      if ((useCaseSelections[uc.id] || uc.default) !== (config[uc.id] || uc.default)) return true;
    }
    return false;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-sm dark:text-[#a1a1aa] light:text-[#71717a]">
          <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading configuration...
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-4xl">
      {/* Status bar */}
      {status && (
        <div
          className={`flex items-center gap-2.5 px-4 py-3 rounded-lg text-sm border ${
            status.type === 'success'
              ? 'dark:bg-green-500/10 light:bg-green-500/5 dark:border-green-500/30 light:border-green-500/20 dark:text-green-400 light:text-green-700'
              : 'dark:bg-red-500/10 light:bg-red-500/5 dark:border-red-500/30 light:border-red-500/20 dark:text-red-400 light:text-red-700'
          }`}
        >
          {status.type === 'success' ? (
            <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
          ) : (
            <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
          )}
          <span>{status.message}</span>
          <button onClick={() => setStatus(null)} className="ml-auto opacity-60 hover:opacity-100 transition-opacity">
            <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        </div>
      )}

      {/* Section A: Provider API Keys */}
      <section>
        <h2 className="text-base font-semibold mb-4 flex items-center gap-2.5">
          <svg className="w-5 h-5 dark:text-vyper-400 light:text-vyper-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0110 0v4" />
          </svg>
          Provider API Keys
        </h2>
        <div className="dark:bg-[#18181b] light:bg-white rounded-lg border dark:border-[#27272a] light:border-[#e4e4e7] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="dark:bg-[#1f1f23] light:bg-[#fafafa] dark:border-b dark:border-[#27272a] light:border-b light:border-[#e4e4e7]">
                <th className="text-left px-4 py-2.5 font-medium dark:text-[#a1a1aa] light:text-[#71717a] text-xs uppercase tracking-wider">Provider</th>
                <th className="text-left px-4 py-2.5 font-medium dark:text-[#a1a1aa] light:text-[#71717a] text-xs uppercase tracking-wider">API Key</th>
                <th className="text-left px-4 py-2.5 font-medium dark:text-[#a1a1aa] light:text-[#71717a] text-xs uppercase tracking-wider">Base URL (optional)</th>
                <th className="text-center px-4 py-2.5 font-medium dark:text-[#a1a1aa] light:text-[#71717a] text-xs uppercase tracking-wider w-16">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-[#27272a] light:divide-[#e4e4e7]">
              {PROVIDERS.map(p => (
                <tr key={p.id} className="dark:hover:bg-[#1f1f23] light:hover:bg-[#fafafa] transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-sm font-bold flex-shrink-0"
                        style={{ backgroundColor: p.color }}
                      >
                        {p.icon}
                      </div>
                      <span className="font-medium">{p.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="relative flex-1 max-w-xs">
                        <input
                          type={visibleKeys.has(p.id) ? 'text' : 'password'}
                          value={apiKeys[p.id] || ''}
                          onChange={e => setApiKeys(prev => ({ ...prev, [p.id]: e.target.value }))}
                          placeholder="sk-..."
                          className="w-full dark:bg-[#0f0f13] light:bg-[#f5f5f5] border dark:border-[#27272a] light:border-[#e4e4e7] rounded-lg px-3 py-1.5 text-sm font-mono
                            dark:text-[#f4f4f5] light:text-[#09090b] placeholder:dark:text-[#52525b] placeholder:light:text-[#a1a1aa]
                            focus:outline-none focus:ring-2 focus:ring-vyper-500/40 focus:border-vyper-500 transition-all pr-8"
                        />
                        <button
                          onClick={() => toggleKeyVisibility(p.id)}
                          className="absolute right-2 top-1/2 -translate-y-1/2 dark:text-[#52525b] light:text-[#a1a1aa] hover:dark:text-[#a1a1aa] hover:light:text-[#52525b] transition-colors"
                          tabIndex={-1}
                        >
                          {visibleKeys.has(p.id) ? (
                            <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                              <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
                              <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
                            </svg>
                          ) : (
                            <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                              <path fillRule="evenodd" d="M3.707 2.293a1 1 0 00-1.414 1.414l14 14a1 1 0 001.414-1.414l-1.473-1.473A10.014 10.014 0 0019.542 10C18.268 5.943 14.478 3 10 3a9.958 9.958 0 00-4.512 1.074l-1.78-1.781zm4.261 4.26l1.514 1.515a2.003 2.003 0 012.45 2.45l1.514 1.514a4 4 0 00-5.478-5.478z" clipRule="evenodd" />
                              <path d="M12.454 16.697L9.75 13.992a4 4 0 01-3.742-3.741L2.335 6.578A9.98 9.98 0 00.458 10c1.274 4.057 5.065 7 9.542 7 .847 0 1.669-.105 2.454-.303z" />
                            </svg>
                          )}
                        </button>
                      </div>
                      <a
                        href={p.docUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs dark:text-vyper-400 light:text-vyper-600 hover:underline flex-shrink-0"
                      >
                        Get
                      </a>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <input
                      type="text"
                      value={baseUrls[p.id] || ''}
                      onChange={e => setBaseUrls(prev => ({ ...prev, [p.id]: e.target.value }))}
                      placeholder="https://api.openai.com"
                      className="w-full max-w-xs dark:bg-[#0f0f13] light:bg-[#f5f5f5] border dark:border-[#27272a] light:border-[#e4e4e7] rounded-lg px-3 py-1.5 text-sm font-mono
                        dark:text-[#f4f4f5] light:text-[#09090b] placeholder:dark:text-[#52525b] placeholder:light:text-[#a1a1aa]
                        focus:outline-none focus:ring-2 focus:ring-vyper-500/40 focus:border-vyper-500 transition-all"
                    />
                  </td>
                  <td className="px-4 py-3 text-center">
                    {hasKey(p.id) ? (
                      <span className="inline-flex items-center gap-1 text-xs dark:text-green-400 light:text-green-600 font-medium" title="Key configured">
                        <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                        Ready
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs dark:text-[#52525b] light:text-[#a1a1aa]" title="No key configured">
                        <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM7 9H5v2h2V9zm8 0h-2v2h2V9z" clipRule="evenodd" />
                        </svg>
                        Missing
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Section B: Model Variants Grid */}
      <section>
        <h2 className="text-base font-semibold mb-4 flex items-center gap-2.5">
          <svg className="w-5 h-5 dark:text-vyper-400 light:text-vyper-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
          Available Model Variants
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
          {ALL_VARIANTS.map(v => {
            const provider = PROVIDERS.find(p => p.id === v.providerId);
            const configured = provider ? hasKey(provider.id) : false;
            return (
              <div
                key={v.id}
                className={`flex items-center gap-3 dark:bg-[#18181b] light:bg-white rounded-lg border dark:border-[#27272a] light:border-[#e4e4e7] px-3.5 py-2.5 transition-all ${
                  configured ? '' : 'opacity-50'
                }`}
                title={configured ? `${v.providerName} — ${v.name}` : `${v.providerName} — requires API key`}
              >
                <div
                  className="w-7 h-7 rounded-md flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
                  style={{ backgroundColor: provider?.color || '#52525b' }}
                >
                  {v.providerId.charAt(0).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{v.name}</div>
                  <div className="text-xs dark:text-[#a1a1aa] light:text-[#71717a] truncate">{v.providerName}</div>
                </div>
                {!configured && (
                  <svg className="w-3.5 h-3.5 flex-shrink-0 ml-auto dark:text-[#52525b] light:text-[#a1a1aa]" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
                  </svg>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* Section C: Use Case Assignment */}
      <section>
        <h2 className="text-base font-semibold mb-4 flex items-center gap-2.5">
          <svg className="w-5 h-5 dark:text-vyper-400 light:text-vyper-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
          Use Case Assignment
        </h2>
        <div className="dark:bg-[#18181b] light:bg-white rounded-lg border dark:border-[#27272a] light:border-[#e4e4e7] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="dark:bg-[#1f1f23] light:bg-[#fafafa] dark:border-b dark:border-[#27272a] light:border-b light:border-[#e4e4e7]">
                <th className="text-left px-4 py-2.5 font-medium dark:text-[#a1a1aa] light:text-[#71717a] text-xs uppercase tracking-wider">Task</th>
                <th className="text-left px-4 py-2.5 font-medium dark:text-[#a1a1aa] light:text-[#71717a] text-xs uppercase tracking-wider">Assigned Model</th>
                <th className="text-left px-4 py-2.5 font-medium dark:text-[#a1a1aa] light:text-[#71717a] text-xs uppercase tracking-wider">Recommendation</th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-[#27272a] light:divide-[#e4e4e7]">
              {USE_CASES.map(uc => (
                <tr key={uc.id} className="dark:hover:bg-[#1f1f23] light:hover:bg-[#fafafa] transition-colors">
                  <td className="px-4 py-3">
                    <span className="font-medium">{uc.label}</span>
                  </td>
                  <td className="px-4 py-3">
                    <select
                      value={useCaseSelections[uc.id] || uc.default}
                      onChange={e => setUseCaseSelections(prev => ({ ...prev, [uc.id]: e.target.value }))}
                      className="w-full max-w-xs dark:bg-[#0f0f13] light:bg-[#f5f5f5] border dark:border-[#27272a] light:border-[#e4e4e7] rounded-lg px-3 py-1.5 text-sm
                        dark:text-[#f4f4f5] light:text-[#09090b] focus:outline-none focus:ring-2 focus:ring-vyper-500/40 focus:border-vyper-500 transition-all"
                    >
                      {ALL_VARIANTS.map(v => {
                        const providerConfigured = hasKey(v.providerId);
                        return (
                          <option
                            key={v.id}
                            value={v.id}
                            disabled={!providerConfigured}
                            className={providerConfigured ? '' : 'dark:text-[#52525b] light:text-[#a1a1aa]'}
                          >
                            {v.name} — {v.providerName}{!providerConfigured ? ' (requires key)' : ''}
                          </option>
                        );
                      })}
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="text-xs dark:text-[#a1a1aa] light:text-[#71717a]">{uc.recommendation}</span>
                      {useCaseSelections[uc.id] === uc.default && (
                        <span className="text-[10px] dark:text-vyper-400 light:text-vyper-600 font-medium bg-vyper-500/10 px-1.5 py-0.5 rounded">Default</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Save Button */}
      <div className="flex items-center justify-between pb-6">
        <div className="text-xs dark:text-[#52525b] light:text-[#a1a1aa]">
          {hasChanges() ? (
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full dark:bg-yellow-400 light:bg-yellow-500" />
              Unsaved changes
            </span>
          ) : (
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full dark:bg-green-400 light:bg-green-500" />
              All saved
            </span>
          )}
        </div>
        <button
          onClick={handleSave}
          disabled={saving || !hasChanges()}
          className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium transition-all
            dark:bg-vyper-500 light:bg-vyper-600 text-white
            hover:dark:bg-vyper-400 hover:light:bg-vyper-700
            disabled:opacity-40 disabled:cursor-not-allowed
            focus:outline-none focus:ring-2 focus:ring-vyper-500/50"
        >
          {saving ? (
            <>
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Saving...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
              Save Settings
            </>
          )}
        </button>
      </div>
    </div>
  );
}

