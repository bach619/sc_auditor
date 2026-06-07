import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      variant: {
        default: "dark:bg-vyper-500/10 dark:text-vyper-400 light:bg-vyper-50 light:text-vyper-600",
        success: "bg-green-500/10 text-green-400",
        warning: "bg-yellow-500/10 text-yellow-400",
        destructive: "bg-red-500/10 text-red-400",
        info: "bg-blue-500/10 text-blue-400",
        secondary: "dark:bg-[#0a0a12] light:bg-gray-100 dark:text-[#68687a] light:text-[#71717a]",
        outline: "dark:border dark:border-[#1a1a28] light:border light:border-[#e4e4e7]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

// eslint-disable-next-line react-refresh/only-export-components
export { Badge, badgeVariants }
