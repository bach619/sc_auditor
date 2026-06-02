import { Navigate } from 'react-router-dom'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import Layout from './layout/Layout'
import Dashboard from './pages/Dashboard'
import Programs from './pages/Programs'
import Reports from './pages/Reports'
import Antonio from './pages/Antonio'
import Settings from './pages/Settings'
import ChatPage from './pages/Chat'

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <Dashboard /> },
      { path: '/programs', element: <Programs /> },
      { path: '/reports', element: <Reports /> },
      { path: '/agent', element: <Antonio /> },
      { path: '/chat', element: <ChatPage /> },
      { path: '/settings', element: <Settings /> },
      { path: '/dashboard', element: <Navigate to="/" replace /> },
      // Aliases for deep-links that redirect to Antonio
      { path: '/ai', element: <Navigate to="/agent" replace /> },
      { path: '/scanning', element: <Navigate to="/agent" replace /> },
      { path: '/source', element: <Navigate to="/agent" replace /> },
      { path: '/exploit', element: <Navigate to="/agent" replace /> },
      { path: '/classifier', element: <Navigate to="/agent" replace /> },
      { path: '/notifications', element: <Navigate to="/agent" replace /> },
      { path: '/webhooks', element: <Navigate to="/agent" replace /> },
      { path: '/upkeep', element: <Navigate to="/agent" replace /> },
      { path: '/submission', element: <Navigate to="/agent" replace /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
