import { useState, useRef, useEffect, useCallback } from 'react'
import { useLocation } from 'react-router-dom'
import { api } from '../../lib/api'
import type { ChatMessageData } from './ChatMessage'

const WELCOME_MESSAGE: ChatMessageData = {
  role: 'assistant',
  content:
    'Halo! Saya **Antonio**, AI Agent Controller platform Vyper. Saya bisa membantu:\n\n' +
    '- 🔍 **Audit kontrak**: `audit 0x1234 on ethereum`\n' +
    '- 📋 **Lihat program**: `show me programs`\n' +
    '- 🧠 **Cari memory**: `what did we find in last audit?`\n' +
    '- 📊 **Generate report**: `generate report for audit_xxx`\n\n' +
    'Ada yang bisa saya bantu?',
  timestamp: new Date().toISOString(),
}

const STORAGE_KEY = 'vyper:chat-history'

export interface ChatSession {
  id: string
  title: string
  updatedAt: string
  createdAt: string
  messages: ChatMessageData[]
  sessionId: string | null
}

function loadSessions(): ChatSession[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveSessions(sessions: ChatSession[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions))
  } catch { /* quota exceeded — silent */ }
}

export function useChat() {
  const location = useLocation()
  const navState = location.state as {
    suggestAudit?: string
    contractAddress?: string
    chain?: string
  } | null

  const [messages, setMessages] = useState<ChatMessageData[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [suggestedMessage, setSuggestedMessage] = useState(navState?.suggestAudit || '')
  const [sessions, setSessions] = useState<ChatSession[]>(loadSessions)
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // ── Helpers ─────────────────────────────────────────────

  const persistSessions = (updated: ChatSession[]) => {
    setSessions(updated)
    saveSessions(updated)
  }

  const generateTitle = (msgs: ChatMessageData[]): string => {
    const userMsg = msgs.find(m => m.role === 'user')
    if (!userMsg) return 'New Chat'
    const preview = userMsg.content.slice(0, 60)
    return preview.length < userMsg.content.length ? preview + '…' : preview
  }

  // Save current conversation to history
  const saveCurrentSession = useCallback(() => {
    if (messages.length <= 1 && sessionId === null) return // only welcome message, skip

    const now = new Date().toISOString()
    const sid = activeSessionId || `chat-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`

    const updated: ChatSession = {
      id: sid,
      title: generateTitle(messages),
      updatedAt: now,
      createdAt: now,
      messages,
      sessionId,
    }

    setActiveSessionId(sid)

    const existing = loadSessions()
    const idx = existing.findIndex(s => s.id === sid)
    if (idx >= 0) {
      existing[idx] = { ...updated, createdAt: existing[idx].createdAt }
    } else {
      existing.unshift(updated)
    }
    // Keep max 50 sessions
    const trimmed = existing.slice(0, 50)
    persistSessions(trimmed)
  }, [messages, sessionId, activeSessionId])

  // ── Effects ─────────────────────────────────────────────

  // Clear suggested message from navigation state
  useEffect(() => {
    if (navState?.suggestAudit) {
      setSuggestedMessage(navState.suggestAudit)
      window.history.replaceState({}, document.title)
    }
  }, [navState?.suggestAudit])

  // Listen for suggestion clicks
  useEffect(() => {
    const handler = (e: Event) => {
      const msg = (e as CustomEvent).detail
      if (typeof msg === 'string') {
        setSuggestedMessage(msg)
      }
    }
    window.addEventListener('vyper:chat-suggest', handler)
    return () => window.removeEventListener('vyper:chat-suggest', handler)
  }, [])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // Welcome message
  useEffect(() => {
    if (messages.length === 0) {
      setMessages([WELCOME_MESSAGE])
    }
  }, [])

  // Auto-save when messages change (debounce)
  useEffect(() => {
    if (messages.length === 0) return
    const timer = setTimeout(saveCurrentSession, 500)
    return () => clearTimeout(timer)
  }, [messages, saveCurrentSession])

  // ── Actions ─────────────────────────────────────────────

  const handleSend = useCallback(async (message: string) => {
    setError('')

    const userMsg: ChatMessageData = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMsg])
    setIsLoading(true)

    try {
      const res = await api.sendChatMessage(message, sessionId ?? undefined)
      const data = res.data as {
        session_id: string
        response: string
        steps_taken: number
        status: string
      }

      setSessionId(data.session_id)

      const assistantMsg: ChatMessageData = {
        role: 'assistant',
        content: data.response,
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (err: any) {
      const errorMsg: ChatMessageData = {
        role: 'assistant',
        content: `Maaf, terjadi error: ${err?.message || 'Gagal terhubung ke Antonio'}`,
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, errorMsg])
      setError(err?.message || 'Unknown error')
    } finally {
      setIsLoading(false)
    }
  }, [sessionId])

  const handleNewChat = () => {
    // Save current before clearing
    saveCurrentSession()
    setMessages([])
    setSessionId(null)
    setError('')
    setActiveSessionId(null)
  }

  const handleLoadSession = (session: ChatSession) => {
    // Save current before switching
    saveCurrentSession()
    setMessages(session.messages)
    setSessionId(session.sessionId)
    setError('')
    setActiveSessionId(session.id)
  }

  const handleDeleteSession = (sessionId: string) => {
    const updated = loadSessions().filter(s => s.id !== sessionId)
    persistSessions(updated)
    // If deleting the active session, unlink it
    if (activeSessionId === sessionId) {
      setActiveSessionId(null)
    }
  }

  const handleClearAllHistory = () => {
    persistSessions([])
    if (!activeSessionId) {
      // If we're not in an active saved session, just clear the reference
    }
  }

  return {
    // State
    messages,
    sessionId,
    isLoading,
    error,
    suggestedMessage,
    setSuggestedMessage,
    messagesEndRef,
    sessions,
    activeSessionId,

    // Actions
    handleSend,
    handleNewChat,
    handleLoadSession,
    handleDeleteSession,
    handleClearAllHistory,
  }
}
