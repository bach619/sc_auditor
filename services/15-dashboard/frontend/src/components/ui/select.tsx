import * as React from "react"
import { cn } from "../../lib/utils"

const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => {
    return (
      <select
        className={cn(
          "flex h-10 w-full rounded-lg px-3 py-2 text-sm outline-none transition-all appearance-none cursor-pointer",
          "dark:bg-[#0a0a12] light:bg-gray-50",
          "dark:border dark:border-[#1a1a28] light:border light:border-[#e4e4e7]",
          "dark:text-[#d4d4dc] light:text-[#09090b]",
          "focus:border-vyper-500 focus:shadow-[0_0_0_2px_rgba(108,92,231,0.2)]",
          "disabled:cursor-not-allowed disabled:opacity-50",
          className
        )}
        ref={ref}
        {...props}
      >
        {children}
      </select>
    )
  }
)
Select.displayName = "Select"

export { Select }
