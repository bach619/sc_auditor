import { Inbox } from "lucide-react"

interface EmptyStateProps {
  message: string
  action?: { label: string; onClick: () => void }
}

export function EmptyState({ message, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <Inbox className="w-12 h-12 dark:text-[#3a3a4a] light:text-[#d4d4d8] mb-4" />
      <p className="text-sm dark:text-[#68687a] light:text-[#71717a]">{message}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="mt-4 px-4 py-2 rounded-lg text-sm font-medium bg-vyper-500 text-white hover:bg-vyper-600 transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  )
}
