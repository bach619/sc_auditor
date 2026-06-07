import { useEffect, useState, useRef } from 'react'
import { api } from '../lib/api'
import { Card } from './ui/card'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { StatusBadge } from './StatusBadge'
import { Loader2, Brain, Activity, Users, CheckCircle2, XCircle, AlertTriangle, ChevronDown, ChevronRight } from 'lucide-react'

interface LeadStep {
  step: number
  thought: string
  action: string
  action_input?: Record<string, unknown>
  observation: string
  status: string
  duration_ms: number
}

interface SubAgentState {
  role: string
  status: string
  task: string
  summary: string
  steps: { step: number; action: string; status: string; observation: string; duration_ms: number }[]
  output: Record<string, unknown>
  error: string | null
}

interface SessionDetail {
  team_session_id: string
  task_type: string
  status: string
  goal: string
  lead_steps: LeadStep[]
  sub_agents: Record<string, SubAgentState>
  error: string | null
}

interface Props {
  sessionId: string
  goal: string
  onComplete: (session: SessionDetail) => void
  onDismiss: () => void
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  completed: <CheckCircle2 className="w-4 h-4 text-green-400" />,
  failed: <XCircle className="w-4 h-4 text-red-400" />,
  stopped: <AlertTriangle className="w-4 h-4 text-yellow-400" />,
  thinking: <Brain className="w-4 h-4 text-blue-400 animate-pulse" />,
  acting: <Activity className="w-4 h-4 text-vyper-400 animate-pulse" />,
  pending: <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />,
  observing: <Activity className="w-4 h-4 text-vyper-400" />,
}

function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    thinking: 'Lead is reasoning...',
    acting: 'Delegating to sub-agents...',
    observing: 'Processing results...',
    completed: 'Audit complete',
    failed: 'Audit failed',
    stopped: 'Audit stopped',
    pending: 'Starting...',
  }
  return labels[status] || status
}

export function TeamAuditProcess({ sessionId, goal, onComplete, onDismiss }: Props) {
  const [session, setSession] = useState<SessionDetail | null>(null)
  const [error, setError] = useState('')
  const [expandedSteps, setExpandedSteps] = useState<Record<number, boolean>>({})
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const doneRef = useRef(false)

  useEffect(() => {
    async function poll() {
      if (doneRef.current) return
      try {
        const res = await api.getTeamSession(sessionId)
        const data = res.data as unknown as SessionDetail
        setSession(data)
        if (data && (data.status === 'completed' || data.status === 'failed' || data.status === 'stopped')) {
          doneRef.current = true
          onComplete(data)
        }
      } catch (err) {
        setError((err as { message?: string })?.message || 'Failed to fetch session')
      }
    }

    poll() // immediate first poll
    pollRef.current = setInterval(poll, 2000)

    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [sessionId, onComplete])

  const toggleStep = (stepNum: number) => {
    setExpandedSteps(prev => ({ ...prev, [stepNum]: !prev[stepNum] }))
  }

  const isRunning = session && !['completed', 'failed', 'stopped'].includes(session.status)

  if (!session) {
    return (
      <Card className="border-vyper-400/30">
        <div className="flex items-center justify-center p-8">
          <Loader2 className="w-6 h-6 text-vyper-400 animate-spin" />
          <span className="ml-2 text-sm dark:text-[#68687a]">Loading session...</span>
        </div>
      </Card>
    )
  }

  return (
    <Card className="border-vyper-400/30">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {isRunning ? (
            <Loader2 className="w-5 h-5 text-vyper-400 animate-spin" />
          ) : (
            STATUS_ICON[session.status || ''] || <Activity className="w-5 h-5 text-vyper-400" />
          )}
          <h3 className="font-semibold dark:text-[#d4d4dc]">Team Audit</h3>
          {session && (
            <Badge className={`text-[10px] ${isRunning ? 'bg-blue-500/20 text-blue-400' : session.status === 'completed' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
              {getStatusLabel(session.status)}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono dark:text-[#68687a]">{sessionId.slice(0, 16)}...</span>
          {!isRunning && (
            <Button variant="ghost" size="sm" onClick={onDismiss}>Dismiss</Button>
          )}
        </div>
      </div>

      {/* Goal */}
      <div className="mb-4 p-3 dark:bg-[#0a0a12] rounded border dark:border-[#1a1a28]">
        <div className="text-xs dark:text-[#68687a] mb-1">Goal</div>
        <div className="text-sm dark:text-[#d4d4dc]">{goal || session.goal || '—'}</div>
      </div>

      {error && (
        <div className="mb-3 p-2 bg-red-500/10 border border-red-500/30 rounded text-xs text-red-400">{error}</div>
      )}

      {/* Lead Auditor Reasoning Steps */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Brain className="w-3.5 h-3.5 text-vyper-400" />
          <span className="text-xs font-medium dark:text-[#68687a] uppercase tracking-wide">Lead Auditor Steps</span>
          <Badge variant="secondary" className="text-[10px]">{session.lead_steps.length}</Badge>
        </div>
        {session.lead_steps.length === 0 ? (
          <div className="flex items-center gap-2 p-3 dark:bg-[#0a0a12] rounded border dark:border-[#1a1a28] text-xs dark:text-[#68687a]">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-vyper-400" />
            {session.status === 'thinking' ? 'Lead Auditor is analyzing the request...' :
             session.status === 'acting' ? 'Delegating first task to sub-agents...' :
             session.status === 'pending' ? 'Initializing audit...' :
             'Waiting for lead auditor...'}
          </div>
        ) : (
          <div className="space-y-2">
            {session.lead_steps.map((step) => (
              <div key={step.step} className="dark:bg-[#0a0a12] rounded border dark:border-[#1a1a28] overflow-hidden">
                <button
                  onClick={() => toggleStep(step.step)}
                  className="w-full flex items-center gap-2 p-2.5 text-left hover:dark:bg-[#1a1a28]/50 transition-colors"
                >
                  {expandedSteps[step.step] ? <ChevronDown className="w-3.5 h-3.5 dark:text-[#68687a]" /> : <ChevronRight className="w-3.5 h-3.5 dark:text-[#68687a]" />}
                  <span className="text-[10px] font-mono dark:text-[#68687a]">#{step.step}</span>
                  <span className="text-xs font-medium dark:text-[#d4d4dc] truncate">{step.action || 'Thinking...'}</span>
                  {STATUS_ICON[step.status] || null}
                  {step.duration_ms > 0 && <span className="text-[10px] dark:text-[#68687a] ml-auto">{(step.duration_ms / 1000).toFixed(1)}s</span>}
                </button>
                {expandedSteps[step.step] && (
                  <div className="px-3 pb-3 space-y-2 border-t dark:border-[#1a1a28]">
                    {step.thought && (
                      <div>
                        <div className="text-[10px] dark:text-[#68687a] mb-0.5">THOUGHT</div>
                        <div className="text-xs dark:text-[#a0a0b0] whitespace-pre-wrap">{step.thought}</div>
                      </div>
                    )}
                    {step.action_input && Object.keys(step.action_input).length > 0 && (
                      <div>
                        <div className="text-[10px] dark:text-[#68687a] mb-0.5">INPUT</div>
                        <pre className="text-[10px] dark:text-[#68687a] bg-black/20 p-1.5 rounded overflow-x-auto">{JSON.stringify(step.action_input, null, 1)}</pre>
                      </div>
                    )}
                    {step.observation && (
                      <div>
                        <div className="text-[10px] dark:text-[#68687a] mb-0.5">OBSERVATION</div>
                        <div className="text-xs dark:text-[#c0c0d0] whitespace-pre-wrap max-h-40 overflow-y-auto">{step.observation}</div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
          )}
        </div>

      {/* Sub-Agent Delegations */}
      {session && Object.keys(session.sub_agents).length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Users className="w-3.5 h-3.5 text-vyper-400" />
            <span className="text-xs font-medium dark:text-[#68687a] uppercase tracking-wide">Sub-Agent Delegations</span>
            <Badge variant="secondary" className="text-[10px]">{Object.keys(session.sub_agents).length}</Badge>
          </div>
          <div className="space-y-1.5">
            {Object.entries(session.sub_agents).map(([role, sub]) => (
              <div key={role} className="flex items-center gap-2 p-2 dark:bg-[#0a0a12] rounded border dark:border-[#1a1a28] text-xs">
                {STATUS_ICON[sub.status] || <Loader2 className="w-3 h-3 text-gray-400 animate-spin" />}
                <span className="font-medium dark:text-[#d4d4dc]">{role}</span>
                <span className="dark:text-[#68687a] truncate flex-1">{sub.task || sub.summary || 'Delegating...'}</span>
                <StatusBadge status={sub.status} />
                {sub.steps.length > 0 && <span className="text-[10px] dark:text-[#68687a]">{sub.steps.length} step{sub.steps.length !== 1 ? 's' : ''}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Final output summary */}
      {session && session.status === 'completed' && session.lead_steps.length > 1 && (
        <div className="mt-4 p-3 bg-green-500/5 border border-green-500/20 rounded">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle2 className="w-4 h-4 text-green-400" />
            <span className="text-sm font-medium text-green-400">Audit Complete</span>
          </div>
          <div className="text-xs dark:text-[#a0a0b0]">
            {session.lead_steps.length} reasoning steps, {Object.keys(session.sub_agents).length} sub-agent delegations.
          </div>
        </div>
      )}

      {session && session.error && (
        <div className="mt-4 p-3 bg-red-500/5 border border-red-500/20 rounded">
          <div className="flex items-center gap-2 mb-1">
            <XCircle className="w-4 h-4 text-red-400" />
            <span className="text-sm font-medium text-red-400">Error</span>
          </div>
          <div className="text-xs dark:text-[#e0a0a0]">{session.error}</div>
        </div>
      )}
    </Card>
  )
}
