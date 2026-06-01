import { NavLink, useLocation } from 'react-router-dom'
import { LayoutDashboard, FolderOpen, Scan, Bomb, FileText, Bot, Brain, Settings, Zap } from 'lucide-react'
import { cn } from '../lib/utils'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/programs', label: 'Programs', icon: FolderOpen },
  { to: '/scanning', label: 'Scanning', icon: Scan },
  { to: '/exploit', label: 'Exploit', icon: Bomb },
  { to: '/reports', label: 'Reports', icon: FileText },
  { to: '/agent', label: 'Agent', icon: Bot },
  { to: '/ai', label: 'AI Agent', icon: Brain },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function Sidebar({ daemonStatus }: { daemonStatus: string }) {
  const location = useLocation()

  const isOnline = daemonStatus === 'running'
  const isPaused = daemonStatus === 'paused'
  const statusDot = isOnline ? 'bg-green-500' : isPaused ? 'bg-yellow-500' : 'bg-red-500'

  return (
    <aside className="w-56 flex-shrink-0 dark:bg-[#0a0a12] light:bg-white border-r dark:border-[#1a1a28] light:border-[#e4e4e7] flex flex-col">
      <div className="h-14 flex items-center gap-2.5 px-5 border-b dark:border-[#1a1a28] light:border-[#e4e4e7]">
        <div className="w-8 h-8 rounded-lg bg-vyper-500 flex items-center justify-center text-white font-bold text-lg">
          <Zap className="w-4 h-4" />
        </div>
        <span className="font-semibold text-base dark:text-[#d4d4dc] light:text-[#09090b]">Vyper</span>
        <span className="text-[10px] dark:text-[#68687a] light:text-[#71717a] ml-auto font-mono">v1.0.0</span>
      </div>

      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const isActive = item.to === '/' 
            ? location.pathname === '/' 
            : location.pathname.startsWith(item.to)
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-200",
                isActive
                  ? "dark:bg-vyper-500/10 light:bg-vyper-500/5 dark:text-vyper-300 light:text-vyper-600 font-medium"
                  : "dark:text-[#68687a] light:text-[#71717a] hover:dark:bg-[#0f0f1a] hover:light:bg-gray-100"
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {item.label}
            </NavLink>
          )
        })}
      </nav>

      <div className="px-3 py-3 border-t dark:border-[#1a1a28] light:border-[#e4e4e7]">
        <div className="flex items-center gap-2 px-3 py-2 text-xs dark:text-[#68687a] light:text-[#71717a]">
          <span className={`w-2 h-2 rounded-full ${statusDot} shadow-[0_0_6px_rgba(34,197,94,0.5)]`} />
          <span>Daemon {daemonStatus}</span>
        </div>
      </div>
    </aside>
  )
}
