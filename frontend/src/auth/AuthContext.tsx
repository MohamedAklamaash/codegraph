import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import type { User } from '../types'
import { api } from '../api'

type AuthStatus = 'loading' | 'authed' | 'anon'

interface AuthContextValue {
  user: User | null
  status: AuthStatus
  refresh: () => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [status, setStatus] = useState<AuthStatus>('loading')

  const refresh = useCallback(async () => {
    try {
      const me = await api.getMe()
      setUser(me)
      setStatus('authed')
    } catch {
      setUser(null)
      setStatus('anon')
    }
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } finally {
      setUser(null)
      setStatus('anon')
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        await api.seedCsrf()
      } catch {
        // ignore — server may be down; getMe will fail too
      }
      if (cancelled) return
      await refresh()
    })()
    return () => { cancelled = true }
  }, [refresh])

  useEffect(() => {
    const handler = () => {
      setUser(null)
      setStatus('anon')
    }
    window.addEventListener('auth:unauthorized', handler)
    return () => window.removeEventListener('auth:unauthorized', handler)
  }, [])

  return (
    <AuthContext.Provider value={{ user, status, refresh, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
