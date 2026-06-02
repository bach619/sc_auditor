import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import { Send, Loader2 } from 'lucide-react'

interface Props {
  onSend: (message: string) => void
  disabled?: boolean
  placeholder?: string
  initialValue?: string
}

export function ChatInput({ onSend, disabled, placeholder, initialValue }: Props) {
  const [value, setValue] = useState(initialValue || '')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const prevInitialRef = useRef(initialValue)

  // Update value when initialValue changes (e.g. from navigation state)
  useEffect(() => {
    if (initialValue && initialValue !== prevInitialRef.current) {
      setValue(initialValue)
      prevInitialRef.current = initialValue
    }
  }, [initialValue])

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = Math.min(el.scrollHeight, 160) + 'px'
    }
  }, [value])

  const handleSend = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    // Reset height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex items-end gap-2">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder || "Chat with Antonio — e.g., 'audit 0x1234 on ethereum'..."}
        rows={1}
        disabled={disabled}
        className="flex-1 resize-none rounded-xl px-4 py-2.5 text-sm
          dark:bg-[#0a0a12] light:bg-gray-50
          dark:text-[#d4d4dc] text-gray-900
          border dark:border-[#1a1a28] light:border-[#e4e4e7]
          placeholder:dark:text-[#68687a] placeholder:text-gray-400
          focus:outline-none focus:ring-2 focus:ring-vyper-500/30 focus:border-vyper-500/50
          disabled:opacity-50 disabled:cursor-not-allowed
          transition-colors"
      />
      <button
        onClick={handleSend}
        disabled={disabled || !value.trim()}
        className="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center
          dark:bg-vyper-500 light:bg-vyper-600
          dark:hover:bg-vyper-400 light:hover:bg-vyper-700
          disabled:opacity-40 disabled:cursor-not-allowed
          transition-colors"
      >
        {disabled ? (
          <Loader2 className="w-4 h-4 text-white animate-spin" />
        ) : (
          <Send className="w-4 h-4 text-white" />
        )}
      </button>
    </div>
  )
}
