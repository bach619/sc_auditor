import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-vyper-500/50 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-vyper-500 text-white hover:bg-vyper-600 active:scale-[0.97]",
        destructive: "bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500/20",
        outline: "border dark:border-[#1a1a28] light:border-[#e4e4e7] dark:text-[#68687a] light:text-[#71717a] hover:border-vyper-500 hover:text-vyper-500",
        secondary: "dark:bg-[#0a0a12] light:bg-gray-100 dark:text-[#d4d4dc] light:text-[#09090b] hover:dark:bg-[#0f0f1a]",
        ghost: "dark:text-[#68687a] light:text-[#71717a] hover:dark:bg-[#0f0f1a] hover:light:bg-gray-100",
        link: "text-vyper-400 underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-12 rounded-xl px-6",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

// eslint-disable-next-line react-refresh/only-export-components
export { Button, buttonVariants }
