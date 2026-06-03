import { Trash2, MessageSquareText, Clock, History, Trash, Copy } from 'lucide-react'
import type { ChatSession } from './useChat'

interface Props {
  sessions: ChatSession[]
  activeSessionId: string | null
  onSelect: (session: ChatSession) => void
  onDelete: (sessionId: string) => void
  onClearAll: () => void
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMin = Math.floor(diffMs / 60000)
    const diffHour = Math.floor(diffMs / 3600000)
    const diffDay = Math.floor(diffMs / 86400000)

    if (diffMin < 1) return 'baru saja'
    if (diffMin < 60) return `${diffMin}m lalu`
    if (diffHour < 24) return `${diffHour}j lalu`
    if (diffDay < 7) return `${diffDay}h lalu`
    return d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' })
  } catch {
    return ''
  }
}

function formatSessionForExport(session: ChatSession): string {
  const lines: string[] = []
  lines.push(`=== ${session.title} (${session.messages.length} messages) ===`)
  lines.push(`   Session: ${session.sessionId || session.id}`)
  lines.push(`   Created: ${session.createdAt}`)
  lines.push('')
  for (const msg of session.messages) {
    const role = msg.role === 'user' ? 'User' : 'Antonio'
    lines.push(`[${role}] ${msg.content}`)
  }
  return lines.join('\n')
}

function handleCopyAll(sessions: ChatSession[]) {
  const header = [
    '╔═══════════════════════════════════════╗',
    '║  VYPER — Chat Sessions Export         ║',
    `║  ${new Date().toISOString().slice(0, 16).replace('T', ' ')}              ║`,
    '╚═══════════════════════════════════════╝',
    '',
  ].join('\n')

  const body = sessions
    .map((s) => formatSessionForExport(s))
    .join('\n\n' + '─'.repeat(40) + '\n\n')

  const full = header + body

  navigator.clipboard.writeText(full).catch(() => {
    // Fallback: select text method
    const ta = document.createElement('textarea')
    ta.value = full
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  })
}

export function ChatHistory({ sessions, activeSessionId, onSelect, onDelete, onClearAll }: Props) {
  return (
    <div className="w-72 flex-shrink-0 flex flex-col min-h-0 dark:bg-[#0a0a12] light:bg-white rounded-xl border dark:border-[#1a1a28] light:border-[#e4e4e7] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b dark:border-[#1a1a28] light:border-[#e4e4e7] flex-shrink-0">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-vyper-400" />
          <span className="text-sm font-medium dark:text-[#d4d4dc] light:text-[#09090b]">History</span>
          <span className="text-[10px] dark:text-[#68687a] text-gray-400">{sessions.length}</span>
        </div>
        <div className="flex items-center gap-1">
          {sessions.length > 0 && (
            <>
              <button
                onClick={() => handleCopyAll(sessions)}
                title="Copy all sessions"
                className="p-1 rounded-lg dark:text-[#68687a] text-gray-400 hover:dark:bg-[#1a1a28] hover:light:bg-gray-100 transition-colors"
              >
                <Copy className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={onClearAll}
                title="Clear all history"
                className="p-1 rounded-lg dark:text-[#68687a] text-gray-400 hover:dark:bg-[#1a1a28] hover:light:bg-gray-100 transition-colors"
              >
                <Trash className="w-3.5 h-3.5" />
              </button>
            </>
          )}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {sessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
            <MessageSquareText className="w-8 h-8 dark:text-[#1a1a28] text-gray-200 mb-3" />
            <p className="text-xs dark:text-[#68687a] text-gray-400">Belum ada histori percakapan.</p>
            <p className="text-[10px] dark:text-[#68687a] text-gray-400 mt-1">
              Mulai chat untuk menyimpan riwayat.
            </p>
          </div>
        ) : (
          <div className="divide-y dark:divide-[#1a1a28] light:divide-[#e4e4e7]">
            {sessions.map((s) => {
              const isActive = s.id === activeSessionId
              return (
                <button
                  key={s.id}
                  onClick={() => onSelect(s)}
                  className={`group w-full text-left px-4 py-3 transition-colors hover:dark:bg-[#1a1a28] hover:light:bg-gray-50 ${
                    isActive
                      ? 'dark:bg-vyper-500/10 light:bg-vyper-500/5 dark:border-l-2 dark:border-l-vyper-500 light:border-l-2 light:border-l-vyper-500'
                      : ''
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className={`text-sm truncate ${isActive ? 'dark:text-vyper-300 light:text-vyper-600 font-medium' : 'dark:text-[#d4d4dc] light:text-[#09090b]'}`}>
                        {s.title}
                      </p>
                      <div className="flex items-center gap-1 mt-1">
                        <Clock className="w-3 h-3 dark:text-[#68687a] text-gray-400" />
                        <span className="text-[10px] dark:text-[#68687a] text-gray-400">
                          {formatTime(s.updatedAt)}
                        </span>
                        <span className="text-[10px] dark:text-[#68687a] text-gray-400">
                          · {s.messages.length} pesan
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-0.5 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          const text = formatSessionForExport(s)
                          navigator.clipboard.writeText(text).catch(() => {})
                        }}
                        title="Copy session"
                        className="p-1 rounded hover:dark:bg-[#1a1a28] hover:light:bg-gray-100 dark:text-[#68687a] text-gray-400"
                      >
                        <Copy className="w-3 h-3" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          onDelete(s.id)
                        }}
                        title="Hapus"
                        className="p-1 rounded hover:dark:bg-[#1a1a28] hover:light:bg-gray-100 dark:text-[#68687a] text-gray-400"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
