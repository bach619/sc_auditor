import { Moon, Sun } from 'lucide-react'
import { Button } from '../components/ui/button'

interface HeaderProps {
  title: string
  theme: 'dark' | 'light'
  onToggleTheme: () => void
  daemonStatus?: string
}

export function Header({ title, theme, onToggleTheme, daemonStatus }: HeaderProps) {
  const isOnline = daemonStatus === 'running'
  const isPaused = daemonStatus === 'paused'
  const statusDot = isOnline ? 'bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.5)]' 
    : isPaused ? 'bg-yellow-500 shadow-[0_0_6px_rgba(245,158,11,0.5)]' 
    : 'bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.5)]'

  return (
    <header className="h-14 flex-shrink-0 flex items-center justify-between px-6 border-b dark:bg-[#0a0a12] light:bg-white dark:border-[#1a1a28] light:border-[#e4e4e7]">
      <h1 className="text-lg font-semibold dark:text-[#d4d4dc] light:text-[#09090b]">{title}</h1>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-sm">
          <span className={`w-2 h-2 rounded-full ${statusDot}`} />
          <span className="dark:text-[#68687a] light:text-[#71717a]">{daemonStatus || 'Offline'}</span>
        </div>
        <Button variant="ghost" size="icon" onClick={onToggleTheme} title="Toggle theme">
          {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </Button>
      </div>
    </header>
  )
}
