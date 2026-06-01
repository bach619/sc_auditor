import { createContext, useContext } from 'react'

export interface DaemonContextValue {
  /** Status string: 'running' | 'stopped' | 'paused' | 'error' */
  daemonStatus: string
  /** Update status dari komponen lain (misal Dashboard setelah toggle) */
  setDaemonStatus: (status: string) => void
}

export const DaemonContext = createContext<DaemonContextValue>({
  daemonStatus: 'running',
  setDaemonStatus: () => {},
})

export const useDaemon = () => useContext(DaemonContext)
