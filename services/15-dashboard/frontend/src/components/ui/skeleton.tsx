import * as React from "react"
import { cn } from "../../lib/utils"

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-md dark:bg-[#0a0a12] light:bg-gray-200", className)}
      {...props}
    />
  )
}

export { Skeleton }
