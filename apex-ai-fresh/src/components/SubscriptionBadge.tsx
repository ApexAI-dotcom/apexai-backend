import { useSubscription } from "@/hooks/useSubscription";
import type { SubscriptionTier } from "@/hooks/useSubscription";

const TIER_CONFIG: Record<
  SubscriptionTier,
  { emoji: string; label: string; className: string }
> = {
  rookie: {
    emoji: "🏁",
    label: "Rookie",
    className:
      "bg-slate-700/80 text-slate-300 border-slate-600/60 hover:bg-slate-700",
  },
  racer: {
    emoji: "🏎️",
    label: "Racer",
    className:
      "bg-blue-600/80 text-blue-100 border-blue-500/60 hover:bg-blue-600",
  },
  team: {
    emoji: "🏆",
    label: "Team",
    className:
      "bg-violet-600/80 text-violet-100 border-violet-500/60 hover:bg-violet-600",
  },
};

export function SubscriptionBadge() {
  const { tier, isLoading } = useSubscription();
  const config = TIER_CONFIG[tier];

  if (isLoading) {
    return (
      <span
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border border-transparent bg-slate-800/60 text-slate-500 animate-pulse"
        aria-hidden
      >
        <span className="inline-block w-3 h-3 rounded-full bg-slate-600" />
        …
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${config.className}`}
      title={`Plan ${config.label}`}
    >
      <span aria-hidden>{config.emoji}</span>
      <span>{config.label}</span>
    </span>
  );
}
