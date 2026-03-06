import { useState, useEffect } from 'react'
import { useUser } from './useAuth'
import { supabase } from '@/lib/supabase'
import { API_BASE_URL } from '@/lib/api'

export type SubscriptionPlan = 'free' | 'pro' | 'team'
export type SubscriptionStatus = 'active' | 'canceled' | 'past_due' | 'trialing'

interface SubscriptionData {
  plan: SubscriptionPlan
  status: SubscriptionStatus
  customerId: string | null
  currentPeriodEnd: string | null
  cancelAtPeriodEnd: boolean
}

interface SubscriptionLimits {
  maxAnalysesPerMonth: number
  canCompare: boolean
  canExportPDF: boolean
  canAccessAPI: boolean
}

const PLAN_LIMITS: Record<SubscriptionPlan, SubscriptionLimits> = {
  free: {
    maxAnalysesPerMonth: 3,
    canCompare: false,
    canExportPDF: false,
    canAccessAPI: false,
  },
  pro: {
    maxAnalysesPerMonth: Infinity,
    canCompare: true,
    canExportPDF: true,
    canAccessAPI: false,
  },
  team: {
    maxAnalysesPerMonth: Infinity,
    canCompare: true,
    canExportPDF: true,
    canAccessAPI: true,
  },
}

const API_CACHE_KEY = 'apex_subscription_cache'
const CACHE_DURATION = 30 * 1000

function getCachedSubscription(userId: string): SubscriptionData | null {
  try {
    const cached = localStorage.getItem(`${API_CACHE_KEY}_${userId}`)
    if (!cached) return null
    const { data, timestamp } = JSON.parse(cached)
    if (Date.now() - timestamp < CACHE_DURATION) return data
    localStorage.removeItem(`${API_CACHE_KEY}_${userId}`)
    return null
  } catch {
    return null
  }
}

function setCachedSubscription(userId: string, data: SubscriptionData) {
  try {
    localStorage.setItem(
      `${API_CACHE_KEY}_${userId}`,
      JSON.stringify({ data, timestamp: Date.now() })
    )
  } catch {
    // ignore
  }
}

/** Legacy hook: plan/status from subscription-status API + user_metadata. Use useSubscription() from useSubscription.ts for tier/limits from profiles. */
export function useSubscriptionLegacy() {
  const { user } = useUser()
  const [subscription, setSubscription] = useState<SubscriptionData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadSubscription = async () => {
      if (!user) {
        setSubscription(null)
        setLoading(false)
        return
      }
      try {
        setLoading(true)
        setError(null)
        const cached = getCachedSubscription(user.id)
        if (cached) {
          setSubscription(cached)
          setLoading(false)
        }
        try {
          const response = await fetch(
            `${API_BASE_URL}/api/subscription-status?user_id=${user.id}`,
            { cache: 'no-cache' }
          )
          if (response.ok) {
            const data = await response.json()
            if (data.plan && data.plan !== 'free') {
              const subscriptionData: SubscriptionData = {
                plan: data.plan as SubscriptionPlan,
                status: (data.status || 'active') as SubscriptionStatus,
                customerId: data.customer_id || null,
                currentPeriodEnd: null,
                cancelAtPeriodEnd: false,
              }
              setCachedSubscription(user.id, subscriptionData)
              setSubscription(subscriptionData)
              setLoading(false)
              return
            }
          }
        } catch {
          if (cached) {
            setLoading(false)
            return
          }
        }
        const plan = (user.user_metadata?.subscription?.plan as SubscriptionPlan) || (user.user_metadata?.subscription as SubscriptionPlan) || 'free'
        const status = (user.user_metadata?.subscription?.status as SubscriptionStatus) || (user.user_metadata?.subscription_status as SubscriptionStatus) || 'active'
        const subscriptionData: SubscriptionData = {
          plan,
          status,
          customerId: user.user_metadata?.stripe_customer_id || null,
          currentPeriodEnd: user.user_metadata?.subscription_period_end || null,
          cancelAtPeriodEnd: user.user_metadata?.cancel_at_period_end || false,
        }
        setCachedSubscription(user.id, subscriptionData)
        setSubscription(subscriptionData)
      } catch (err) {
        setError('Erreur lors du chargement de l\'abonnement')
        setSubscription({
          plan: 'free',
          status: 'active',
          customerId: null,
          currentPeriodEnd: null,
          cancelAtPeriodEnd: false,
        })
      } finally {
        setLoading(false)
      }
    }
    loadSubscription()
  }, [user])

  const limits = subscription ? PLAN_LIMITS[subscription.plan] : PLAN_LIMITS.free
  const isPro = subscription?.plan === 'pro' || subscription?.plan === 'team'
  const isActive = subscription?.status === 'active' || subscription?.status === 'trialing'

  return {
    subscription,
    limits,
    isPro,
    isActive,
    loading,
    error,
  }
}

export async function forceProSubscription() {
  try {
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) return
    await supabase.auth.updateUser({
      data: {
        subscription: { plan: "pro", status: "active" },
        subscription_status: "active",
      },
    })
    window.location.reload()
  } catch (error) {
    console.error("Error forcing PRO:", error)
  }
}
