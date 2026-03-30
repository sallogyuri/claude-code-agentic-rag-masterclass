import type { ReactNode } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { LoginForm } from './LoginForm'

export function AuthGuard({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth()
  if (loading) return <div className="flex min-h-screen items-center justify-center">Loading...</div>
  if (!session) return <LoginForm />
  return <>{children}</>
}
