import { Bot, User } from 'lucide-react'

export interface ChatMessageData {
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
}

interface Props {
  message: ChatMessageData
}

function formatTime(ts?: string): string {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

/** Simple markdown-like inline renderer for chat messages */
function renderContent(text: string): React.ReactNode {
  // Split by code blocks first
  const parts = text.split(/(```[\s\S]*?```)/g)
  return parts.map((part, i) => {
    if (part.startsWith('```') && part.endsWith('```')) {
      // Code block
      const inner = part.slice(3, -3).trim()
      const langEnd = inner.indexOf('\n')
      const lang = langEnd > 0 ? inner.slice(0, langEnd).trim() : ''
      const code = langEnd > 0 ? inner.slice(langEnd).trim() : inner
      return (
        <pre key={i} className="relative group my-2 rounded-lg overflow-hidden">
          {lang && (
            <div className="text-[10px] px-3 py-1 dark:bg-[#0d0d1a] light:bg-gray-100 dark:text-[#68687a] text-gray-500 border-b dark:border-[#1a1a28] light:border-[#e4e4e7] font-mono">
              {lang}
            </div>
          )}
          <code className="block p-3 text-xs font-mono dark:bg-[#0a0a12] light:bg-gray-50 dark:text-[#d4d4dc] text-gray-800 overflow-x-auto leading-relaxed">
            {code}
          </code>
        </pre>
      )
    }
    // Inline: render line breaks and simple formatting
    const lines = part.split('\n')
    return lines.map((line, li) => {
      if (line.trim() === '') {
        return <br key={`${i}-${li}`} />
      }
      // Bold **text**
      const withBold = line.split(/(\*\*.*?\*\*)/g).map((seg, si) => {
        if (seg.startsWith('**') && seg.endsWith('**')) {
          return <strong key={si} className="font-semibold">{seg.slice(2, -2)}</strong>
        }
        // Inline code `text`
        const withCode = seg.split(/(`.*?`)/g).map((codeSeg, ci) => {
          if (codeSeg.startsWith('`') && codeSeg.endsWith('`')) {
            return (
              <code key={ci} className="px-1 py-0.5 text-xs font-mono dark:bg-[#0a0a12] light:bg-gray-100 rounded dark:text-vyper-300 text-vyper-600">
                {codeSeg.slice(1, -1)}
              </code>
            )
          }
          return codeSeg
        })
        return withCode
      })
      return (
        <p key={`${i}-${li}`} className="mb-1 last:mb-0 leading-relaxed">
          {withBold}
        </p>
      )
    })
  })
}

export function ChatMessage({ message }: Props) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          isUser
            ? 'dark:bg-vyper-500/20 light:bg-vyper-100'
            : 'dark:bg-[#1a1a28] light:bg-gray-100'
        }`}
      >
        {isUser ? (
          <User className="w-4 h-4 dark:text-vyper-400 text-vyper-600" />
        ) : (
          <Bot className="w-4 h-4 dark:text-[#d4d4dc] text-gray-600" />
        )}
      </div>

      {/* Bubble */}
      <div className={`max-w-[80%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
            isUser
              ? 'dark:bg-vyper-500/20 light:bg-vyper-50 dark:text-[#d4d4dc] text-gray-900 rounded-tr-sm'
              : 'dark:bg-[#0a0a12] light:bg-gray-50 dark:text-[#d4d4dc] text-gray-900 rounded-tl-sm border dark:border-[#1a1a28] light:border-[#e4e4e7]'
          }`}
        >
          {renderContent(message.content)}
        </div>
        {message.timestamp && (
          <p className={`text-[10px] mt-1 dark:text-[#68687a] text-gray-400 ${isUser ? 'text-right' : 'text-left'}`}>
            {formatTime(message.timestamp)}
          </p>
        )}
      </div>
    </div>
  )
}
