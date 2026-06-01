import { Loader2 } from "lucide-react"

interface LoadingStateProps {
  message?: string
  className?: string
}

export function LoadingState({ message = "Loading...", className = "" }: LoadingStateProps) {
  return (
    <div className={`flex items-center justify-center py-16 ${className}`}>
      <div className="flex items-center gap-3 text-sm dark:text-[#68687a] light:text-[#71717a]">
        <Loader2 className="h-5 w-5 animate-spin text-vyper-400" />
        <span>{message}</span>
      </div>
    </div>
  )
}
