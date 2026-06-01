import { Badge } from "./ui/badge"

type StatusType = 'COMPLETED' | 'RUNNING' | 'PENDING' | 'FAILED' | 'SCANNING'
  | 'Critical' | 'High' | 'Medium' | 'Low' | 'Info'
  | 'OPEN' | 'CLOSED'
  | string

const statusVariantMap: Record<string, 'success' | 'warning' | 'destructive' | 'info' | 'default' | 'secondary'> = {
  COMPLETED: 'success',
  RUNNING: 'info',
  PENDING: 'warning',
  SCANNING: 'default',
  FAILED: 'destructive',
  Critical: 'destructive',
  High: 'warning',
  Medium: 'warning',
  Low: 'success',
  Info: 'info',
  OPEN: 'info',
  CLOSED: 'secondary',
}

interface StatusBadgeProps {
  status: StatusType
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const variant = statusVariantMap[status] || 'secondary'
  return <Badge variant={variant} className={className}>{status}</Badge>
}
