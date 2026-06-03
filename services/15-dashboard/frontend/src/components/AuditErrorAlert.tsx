import { AlertTriangle, Server, X } from "lucide-react"

interface AuditErrorAlertProps {
  message: string
  onDismiss?: () => void
}

export function AuditErrorAlert({ message, onDismiss }: AuditErrorAlertProps) {
  if (!message) return null

  const isConnectionError = /connect|refused|unreachable|timeout|econn|enotfound|network/i.test(message)
  const isAgentError = /agent|backend|service|502|503/i.test(message)
  const showTroubleshooting = isConnectionError || isAgentError

  return (
    <div className="rounded-lg p-4 bg-red-500/10 border border-red-500/30 mt-3">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-0.5">
          {showTroubleshooting ? (
            <Server className="w-5 h-5 text-red-400" />
          ) : (
            <AlertTriangle className="w-5 h-5 text-red-400" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-red-300 mb-1">
            {showTroubleshooting ? 'Service Unavailable' : 'Audit Failed to Start'}
          </p>
          <p className="text-sm text-red-400/80 break-words">{message}</p>

          {showTroubleshooting && (
            <div className="mt-3 pt-3 border-t border-red-500/20">
              <p className="text-xs font-medium text-red-300 mb-2">Troubleshooting Steps:</p>
              <ol className="text-xs text-red-400/70 space-y-1 list-decimal list-inside">
                <li>
                  Ensure <code className="text-red-300 bg-red-500/10 px-1 rounded">14-agent</code> (Antonio) is running:
                  <code className="block mt-0.5 ml-5 text-red-300/80 bg-red-500/5 px-2 py-0.5 rounded">docker compose up -d 14-agent</code>
                </li>
                <li>
                  Check agent health endpoint:
                  <code className="block mt-0.5 ml-5 text-red-300/80 bg-red-500/5 px-2 py-0.5 rounded">curl http://localhost:8021/health</code>
                </li>
                <li>
                  Also verify <code className="text-red-300 bg-red-500/10 px-1 rounded">11-orchestrator</code> is running:
                  <code className="block mt-0.5 ml-5 text-red-300/80 bg-red-500/5 px-2 py-0.5 rounded">docker compose up -d 11-orchestrator</code>
                </li>
                <li>After starting services, wait ~10 seconds and try again.</li>
              </ol>
            </div>
          )}
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="text-red-400/60 hover:text-red-400 transition-colors flex-shrink-0"
            aria-label="Dismiss error"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  )
}
