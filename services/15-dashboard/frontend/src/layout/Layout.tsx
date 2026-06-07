import { useState, useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { api } from '../lib/api'
import { DaemonContext } from '../lib/daemon-context'

const NAV_LOOKUP: Record<string, string> = {
  '/': 'Dashboard',
  '/chat': 'Chat',
  '/programs': 'Programs',
  '/scanning': 'Scanning',
  '/exploit': 'Exploit',
  '/reports': 'Reports',
  '/agent': 'Agent',
  '/ai': 'AI Agent',
  '/settings': 'Settings',
}

export default function Layout() {
  const [daemonStatus, setDaemonStatus] = useState('running')
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')
  const location = useLocation()
  const currentTitle = NAV_LOOKUP[location.pathname] || 'Vyper'

  useEffect(() => {
    const saved = localStorage.getItem('vyper-theme')
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: sync localStorage theme on mount
    if (saved === 'light') setTheme('light')
  }, [])

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    localStorage.setItem('vyper-theme', theme)
  }, [theme])

  /* ── Daemon status — single source of truth ──────────────── */
  useEffect(() => {
    api.getDaemonStatus()
      .then(r => setDaemonStatus(r.data?.status || 'running'))
      .catch(() => {})
    const es = new EventSource('/events')
    es.addEventListener('daemon_status', (e: MessageEvent) => {
      try { setDaemonStatus(JSON.parse(e.data).status) } catch (err) { console.error('daemon event parse failed', err) }
    })
    return () => es.close()
  }, [])

  const toggleTheme = () => setTheme(t => t === 'dark' ? 'light' : 'dark')

  return (
    <DaemonContext.Provider value={{ daemonStatus, setDaemonStatus }}>
    <div className="flex h-screen overflow-hidden dark:bg-[#08080f] dark:text-[#d4d4dc] light:bg-[#f5f5f5] light:text-[#09090b]">
      <Sidebar daemonStatus={daemonStatus} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title={currentTitle} theme={theme} onToggleTheme={toggleTheme} daemonStatus={daemonStatus} />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
        <footer className="flex-shrink-0 px-6 py-2 text-xs dark:text-[#68687a] light:text-[#71717a] border-t dark:border-[#1a1a28] light:border-[#e4e4e7] flex items-center justify-between">
          <span>Vyper v1.0.0 — Smart Contract Bug Hunter</span>
          <FooterTime />
        </footer>
      </div>
    </div>
    </DaemonContext.Provider>
  )
}

function FooterTime() {
  const [time, setTime] = useState('')
  useEffect(() => {
    const update = () => setTime(
      new Date().toLocaleDateString('en-US', { 
        weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' 
      }) + ' — ' + new Date().toLocaleTimeString('en-US')
    )
    update()
    const id = setInterval(update, 1000)
    return () => clearInterval(id)
  }, [])
  return <span>{time}</span>
}
