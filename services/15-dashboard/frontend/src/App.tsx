import { lazy, Suspense } from 'react'
import { Navigate } from 'react-router-dom'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import Layout from './layout/Layout'
import { LoadingState } from './components/LoadingState'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Programs = lazy(() => import('./pages/Programs'))
const Reports = lazy(() => import('./pages/Reports'))
const Antonio = lazy(() => import('./pages/Antonio'))
const ChatPage = lazy(() => import('./pages/Chat'))
const Settings = lazy(() => import('./pages/Settings'))

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <Suspense fallback={<LoadingState message="Loading page..." />}><Dashboard /></Suspense> },
      { path: '/programs', element: <Suspense fallback={<LoadingState message="Loading page..." />}><Programs /></Suspense> },
      { path: '/reports', element: <Suspense fallback={<LoadingState message="Loading page..." />}><Reports /></Suspense> },
      { path: '/agent', element: <Suspense fallback={<LoadingState message="Loading page..." />}><Antonio /></Suspense> },
      { path: '/chat', element: <Suspense fallback={<LoadingState message="Loading page..." />}><ChatPage /></Suspense> },
      { path: '/settings', element: <Suspense fallback={<LoadingState message="Loading page..." />}><Settings /></Suspense> },
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
