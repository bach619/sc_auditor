import { MessageSquareText, Trash2, Bot, Loader2, Copy } from 'lucide-react'
import { ChatMessage, ChatInput, ChatHistory } from '../components/chat'
import { useChat } from '../components/chat/useChat'

export default function ChatPage() {
  const {
    messages,
    sessionId,
    isLoading,
    error,
    suggestedMessage,
    setSuggestedMessage,
    messagesEndRef,
    handleSend,
    handleNewChat,
    sessions,
    activeSessionId,
    handleLoadSession,
    handleDeleteSession,
    handleClearAllHistory,
  } = useChat()

  return (
    <div className="flex h-full min-h-0 gap-4">
      {/* ── Main Chat Area ─────────────────────────────── */}
      <div className="flex-1 flex flex-col min-h-0 min-w-0">
        {/* Header */}
        <div className="flex items-center justify-between px-1 py-2 flex-shrink-0">
          <div className="flex items-center gap-2">
            <MessageSquareText className="w-5 h-5 text-vyper-400" />
            <div>
              <h1 className="text-lg font-semibold dark:text-[#d4d4dc] light:text-[#09090b]">
                Chat with Antonio
              </h1>
              <p className="text-xs dark:text-[#68687a] light:text-[#71717a]">
                AI Agent Controller — natural language interface untuk seluruh platform Vyper
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {sessionId && (
              <span className="text-[10px] dark:text-[#68687a] text-gray-400 font-mono">
                {sessionId.slice(0, 12)}…
              </span>
            )}
            <button
              onClick={() => {
                const text = messages
                  .map(m => `[${m.role === 'user' ? 'User' : 'Antonio'}] ${m.content}`)
                  .join('\n\n')
                navigator.clipboard.writeText(text).catch(() => {})
              }}
              title="Copy current chat"
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs
                dark:text-[#68687a] text-gray-500
                hover:dark:bg-[#1a1a28] hover:light:bg-gray-100
                transition-colors"
            >
              <Copy className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleNewChat}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs
                dark:text-[#68687a] text-gray-500
                hover:dark:bg-[#1a1a28] hover:light:bg-gray-100
                transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
              New Chat
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 min-h-0 overflow-y-auto rounded-xl border dark:border-[#1a1a28] light:border-[#e4e4e7] dark:bg-[#0a0a12] light:bg-white px-4 py-4 space-y-4 scroll-smooth">
          {messages.map((msg, i) => (
            <ChatMessage key={i} message={msg} />
          ))}

          {isLoading && (
            <div className="flex gap-3">
              <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center dark:bg-[#1a1a28] light:bg-gray-100">
                <Bot className="w-4 h-4 dark:text-[#d4d4dc] text-gray-600" />
              </div>
              <div className="flex items-center gap-1 px-4 py-3 rounded-2xl rounded-tl-sm dark:bg-[#0a0a12] light:bg-gray-50 border dark:border-[#1a1a28] light:border-[#e4e4e7]">
                <span className="w-2 h-2 dark:bg-[#68687a] bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 dark:bg-[#68687a] bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 dark:bg-[#68687a] bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Error */}
        {error && (
          <div className="pt-1.5 flex-shrink-0">
            <p className="text-xs text-red-400">{error}</p>
          </div>
        )}

        {/* Input */}
        <div className="flex-shrink-0 pt-3">
          <div className="rounded-xl border dark:border-[#1a1a28] light:border-[#e4e4e7] dark:bg-[#0a0a12] light:bg-white px-4 py-3">
            <ChatInput
              onSend={(msg) => {
                handleSend(msg)
                setSuggestedMessage('')
              }}
              disabled={isLoading}
              initialValue={suggestedMessage}
              placeholder="Type a message... (Enter to send, Shift+Enter for new line)"
            />
          </div>

          {/* Quick tips */}
          <div className="flex flex-wrap gap-2 mt-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s.label}
                onClick={() => {
                  setSuggestedMessage(s.message)
                  const ta = document.querySelector<HTMLTextAreaElement>('textarea')
                  ta?.focus()
                }}
                className="text-xs px-3 py-1.5 rounded-full
                  dark:bg-[#0a0a12] light:bg-gray-50
                  dark:text-[#68687a] light:text-[#71717a]
                  border dark:border-[#1a1a28] light:border-[#e4e4e7]
                  hover:dark:bg-[#1a1a28] hover:dark:text-[#d4d4dc]
                  hover:light:bg-gray-100 hover:light:text-[#09090b]
                  transition-colors"
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Chat History Sidebar ───────────────────────── */}
      <ChatHistory
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelect={handleLoadSession}
        onDelete={handleDeleteSession}
        onClearAll={handleClearAllHistory}
      />
    </div>
  )
}

const SUGGESTIONS = [
  { label: '🔍 Audit kontrak', message: 'audit 0x4c9edd5852cd905f086c759e8383e09bff1e68b3 on ethereum' },
  { label: '📋 Lihat program', message: 'show me programs' },
  { label: '🧠 Cari memory', message: 'what did we find in last audit?' },
  { label: '📊 Generate report', message: 'generate report for audit_xxx' },
  { label: '👥 Team structure', message: 'who is on the team?' },
  { label: '📈 Skill metrics', message: 'show skill metrics' },
]
