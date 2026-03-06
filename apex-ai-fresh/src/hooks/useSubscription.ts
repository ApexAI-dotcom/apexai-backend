import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/hooks/useAuth";
import { API_BASE_URL } from "@/lib/api";

export type SubscriptionTier = "rookie" | "racer" | "team";
export type SubscriptionStatus = "active" | "canceled" | "past_due" | "trialing" | null;

export interface SubscriptionLimits {
  tier: SubscriptionTier;
  analyses_per_month: number | null;
  analyses_used: number;
  can_export_csv: boolean;
  can_export_pdf: boolean;
  can_compare: boolean;
  max_members: number;
  max_circuits: number | null;
  max_cars: number | null;
}

export type BillingPeriod = "monthly" | "annual" | null;

export interface SubscriptionResponse {
  tier: SubscriptionTier;
  status: SubscriptionStatus;
  billing_period: BillingPeriod;
  subscription_end_date: string | null;
  limits: SubscriptionLimits;
}

/** Plan pour compatibilité affichage (free/pro/team) */
export type SubscriptionPlan = "free" | "pro" | "team";

function tierToPlan(tier: SubscriptionTier): SubscriptionPlan {
  if (tier === "racer") return "pro";
  if (tier === "team") return "team";
  return "free";
}

export function useSubscription() {
  const { user, session } = useAuth();
  const [tier, setTier] = useState<SubscriptionTier>("rookie");
  const [status, setStatus] = useState<SubscriptionStatus>(null);
  const [billingPeriod, setBillingPeriod] = useState<BillingPeriod>(null);
  const [subscriptionEndDate, setSubscriptionEndDate] = useState<string | null>(null);
  const [limits, setLimits] = useState<SubscriptionLimits | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchSubscription = useCallback(async () => {
    const token = session?.access_token;
    if (!user?.id || !token) {
      setTier("rookie");
      setStatus(null);
      setBillingPeriod(null);
      setSubscriptionEndDate(null);
      setLimits(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/user/subscription`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        setTier("rookie");
        setStatus(null);
        setBillingPeriod(null);
        setSubscriptionEndDate(null);
        setLimits(null);
        return;
      }
      const data: SubscriptionResponse = await res.json();
      setTier(data.tier ?? "rookie");
      setStatus(data.status ?? null);
      setBillingPeriod(data.billing_period ?? null);
      setSubscriptionEndDate(data.subscription_end_date ?? null);
      setLimits(data.limits ?? null);
    } catch {
      setTier("rookie");
      setStatus(null);
      setBillingPeriod(null);
      setSubscriptionEndDate(null);
      setLimits(null);
    } finally {
      setIsLoading(false);
    }
  }, [user?.id, session?.access_token]);

  useEffect(() => {
    fetchSubscription();
  }, [fetchSubscription]);

  const plan = tierToPlan(tier);
  return {
    tier,
    status,
    billingPeriod,
    subscriptionEndDate,
    limits,
    isLoading,
    plan,
  };
}
