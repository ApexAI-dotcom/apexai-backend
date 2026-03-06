import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { User, Session, AuthError } from '@supabase/supabase-js'
import { supabase } from '@/lib/supabase'
import { ADMIN_EMAIL } from '@/constants'

const GUEST_KEY = 'apex_guest_mode'
const GUEST_USED_KEY = 'apex_guest_used'
const TOKEN_KEY = 'apex-jwt'

function getStoredGuest(): boolean {
  try { return localStorage.getItem(GUEST_KEY) === '1' } catch { return false }
}
function getStoredGuestUsed(): boolean {
  try { return localStorage.getItem(GUEST_USED_KEY) === '1' } catch { return false }
}

interface AuthContextType {
  user: User | null
  session: Session | null
  loading: boolean
  isAuthenticated: boolean
  isGuest: boolean
  guestUsed: boolean
  canUploadFree: boolean
  guestUpload: () => void
  consumeGuestSlot: () => void
  signInEmail: (email: string, password: string) => Promise<{ error: AuthError | null }>
  signUpEmail: (email: string, password: string) => Promise<{ error: AuthError | null }>
  signInMagicLink: (email: string) => Promise<{ error: AuthError | null }>
  resetPasswordForEmail: (email: string) => Promise<{ error: AuthError | null }>
  signOut: () => Promise<{ error: AuthError | null }>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [isGuest, setIsGuest] = useState(getStoredGuest)
  const [guestUsed, setIsGuestUsed] = useState(getStoredGuestUsed)

  useEffect(() => {
    // Récupérer la session initiale
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    })

    // Écouter les changements d'authentification
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    })

    return () => subscription.unsubscribe()
  }, [])

  const guestUpload = () => {
    setIsGuest(true)
    try { localStorage.setItem(GUEST_KEY, '1') } catch {}
  }
  const consumeGuestSlot = () => {
    setIsGuestUsed(true)
    try { localStorage.setItem(GUEST_USED_KEY, '1') } catch {}
  }
  const canUploadFree = isGuest && !guestUsed

  useEffect(() => {
    if (session?.access_token) {
      try { localStorage.setItem(TOKEN_KEY, session.access_token) } catch {}
    }
  }, [session?.access_token])

  // Admin: moreauy58@gmail.com uniquement
  useEffect(() => {
    if (user?.email === ADMIN_EMAIL) {
      try {
        localStorage.setItem('userRole', 'admin')
        localStorage.setItem('isAdmin', 'true')
      } catch {}
    } else {
      try {
        localStorage.removeItem('userRole')
        localStorage.removeItem('isAdmin')
      } catch {}
    }
  }, [user?.email])

  // Auto-refresh de la session
  useEffect(() => {
    if (session) {
      const refreshInterval = setInterval(async () => {
        const { data: { session: refreshedSession }, error } = await supabase.auth.refreshSession()
        if (!error && refreshedSession) {
          setSession(refreshedSession)
          setUser(refreshedSession.user)
        }
      }, 30 * 60 * 1000) // Rafraîchir toutes les 30 minutes

      return () => clearInterval(refreshInterval)
    }
  }, [session])

  const signInEmail = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    })
    return { error }
  }

  const signUpEmail = async (email: string, password: string) => {
    const { error } = await supabase.auth.signUp({
      email,
      password,
    })
    return { error }
  }

  const signInMagicLink = async (email: string) => {
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${window.location.origin}/dashboard`,
      },
    })
    return { error }
  }

  const resetPasswordForEmail = async (email: string) => {
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`,
    })
    return { error }
  }

  const signOut = async () => {
    try {
      localStorage.removeItem('userRole')
      localStorage.removeItem('isAdmin')
    } catch {}
    const { error } = await supabase.auth.signOut()
    return { error }
  }

  const value: AuthContextType = {
    user,
    session,
    loading,
    isAuthenticated: !!user,
    isGuest,
    guestUsed,
    canUploadFree,
    guestUpload,
    consumeGuestSlot,
    signInEmail,
    signUpEmail,
    signInMagicLink,
    resetPasswordForEmail,
    signOut,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

// Hook pour obtenir uniquement la session
export function useSession() {
  const { session, loading } = useAuth()
  return { session, loading }
}

// Hook pour obtenir uniquement l'utilisateur
export function useUser() {
  const { user, loading } = useAuth()
  return { user, loading }
}
