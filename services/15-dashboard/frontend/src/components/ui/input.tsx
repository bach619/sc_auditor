import * as React from "react"
import { cn } from "../../lib/utils"

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-10 w-full rounded-lg px-3 py-2 text-sm outline-none transition-all",
          "dark:bg-[#0a0a12] light:bg-gray-50",
          "dark:border dark:border-[#1a1a28] light:border light:border-[#e4e4e7]",
          "dark:text-[#d4d4dc] light:text-[#09090b]",
          "placeholder:dark:text-[#3a3a4a] placeholder:light:text-[#a1a1aa]",
          "focus:border-vyper-500 focus:shadow-[0_0_0_2px_rgba(108,92,231,0.2)]",
          "file:border-0 file:bg-transparent file:text-sm file:font-medium file:dark:text-[#d4d4dc]",
          "disabled:cursor-not-allowed disabled:opacity-50",
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = "Input"

export { Input }
