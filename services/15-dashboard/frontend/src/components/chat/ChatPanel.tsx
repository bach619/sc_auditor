import { Bot, Trash2, Loader2 } from 'lucide-react'
import { useChat } from './useChat'
import { ChatMessage } from './ChatMessage'
import { ChatInput } from './ChatInput'

interface ChatPanelProps {
  /** Tinggi panel. Default 420px, gunakan 'full' untuk dedicated chat page */
  height?: number | 'full'
  /** Sembunyikan header bar */
  hideHeader?: boolean
  /** Sembunyikan input box (parent akan render sendiri) */
  hideInput?: boolean
}

export function ChatPanel({ height = 420, hideHeader = false, hideInput = false }: ChatPanelProps) {
  const {
    messages,
    sessionId,
    isLoading,
    error,
    suggestedMessage,
    messagesEndRef,
    handleSend,
    handleNewChat,
  } = useChat()

  return (
    <div
      className={`flex flex-col ${height === 'full' ? 'flex-1 min-h-0' : ''}`}
      style={height === 'full' ? {} : { height: `${height}px` }}
    >
      {/* Header */}
      {!hideHeader && (
        <div className="flex items-center justify-between px-4 py-2.5 border-b dark:border-[#1a1a28] light:border-[#e4e4e7] flex-shrink-0">
          <div className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-vyper-400" />
            <span className="text-sm font-medium dark:text-[#d4d4dc] text-gray-900">
              Chat with Antonio
            </span>
            {sessionId && (
              <span className="text-[10px] dark:text-[#68687a] text-gray-400 font-mono">
                {sessionId.slice(0, 12)}...
              </span>
            )}
          </div>
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
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 scroll-smooth">
        {messages.map((msg, i) => (
          <ChatMessage key={i} message={msg} />
        ))}

        {/* Typing indicator */}
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
        <div className="px-4 py-1.5">
          <p className="text-xs text-red-400">{error}</p>
        </div>
      )}

      {/* Input */}
      {!hideInput && (
        <div className="px-4 py-3 border-t dark:border-[#1a1a28] light:border-[#e4e4e7] flex-shrink-0">
          <ChatInput
            onSend={handleSend}
            disabled={isLoading}
            initialValue={suggestedMessage}
          />
        </div>
      )}
    </div>
  )
}
