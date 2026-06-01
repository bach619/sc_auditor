import { Navigate } from 'react-router-dom'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import Layout from './layout/Layout'
import Dashboard from './pages/Dashboard'
import Programs from './pages/Programs'
import Scanning from './pages/Scanning'
import Exploit from './pages/Exploit'
import Reports from './pages/Reports'
import Agent from './pages/Agent'
import AIConfig from './pages/AIConfig'
import Settings from './pages/Settings'

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <Dashboard /> },
      { path: '/programs', element: <Programs /> },
      { path: '/scanning', element: <Scanning /> },
      { path: '/exploit', element: <Exploit /> },
      { path: '/reports', element: <Reports /> },
      { path: '/agent', element: <Agent /> },
      { path: '/ai', element: <AIConfig /> },
      { path: '/settings', element: <Settings /> },
      { path: '/dashboard', element: <Navigate to="/" replace /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
