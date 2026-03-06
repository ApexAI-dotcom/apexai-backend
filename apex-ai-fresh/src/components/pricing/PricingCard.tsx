import { motion } from "framer-motion";
import { Check, Loader2, Medal, Award, Trophy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { stripePromise } from "@/lib/stripe";
import { API_BASE_URL } from "@/lib/api";

interface PricingCardProps {
  name: string;
  price: string;
  period?: string;
  description: string;
  features: string[];
  variant: "free" | "pro" | "team";
  popular?: boolean;
  delay?: number;
  priceId?: string; // Stripe Price ID
}

const variantStyles = {
  free: {
    card: "border-white/10",
    badge: "bg-muted text-muted-foreground",
    Icon: Medal,
    button: "outline" as const,
  },
  pro: {
    card: "border-primary/30 glow-primary",
    badge: "gradient-pro text-primary-foreground",
    Icon: Award,
    button: "hero" as const,
  },
  team: {
    card: "border-gold/30",
    badge: "gradient-gold text-gold-foreground",
    Icon: Trophy,
    button: "gold" as const,
  },
};

export const PricingCard = ({
  name,
  price,
  period = "/mois",
  description,
  features,
  variant,
  popular,
  delay = 0,
  priceId,
}: PricingCardProps) => {
  const styles = variantStyles[variant];
  const TierIcon = styles.Icon;
  const { user } = useAuth();
  const [loading, setLoading] = useState(false);

  const handleCheckout = async () => {
    if (variant === "free") {
      // Rediriger vers l'inscription ou le dashboard
      window.location.href = "/login";
      return;
    }

    if (!user) {
      window.location.href = "/login?redirect=/pricing";
      return;
    }

    try {
      setLoading(true);
      console.log("Checkout", variant);
      const response = await fetch(`${API_BASE_URL}/api/create-checkout-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan: `${variant}_monthly` }), // pro_monthly, team_monthly
      });
      
      const data = await response.json();
      console.log("Response:", data);
      
      if (data.url) {
        window.location.href = data.url;
      } else {
        console.error("Checkout error:", data.error);
        alert("Erreur: " + data.error);
      }
    } catch (error) {
      console.error("Erreur checkout:", error);
      alert("Erreur réseau");
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className={`relative glass-card p-8 border-2 border-transparent transition-all duration-400 hover:border-orange-500 hover:bg-slate-900/50 ${styles.card} ${popular ? "scale-105 z-10" : ""}`}
    >
      {popular && (
        <div className="absolute -top-4 left-1/2 -translate-x-1/2">
          <span className="px-4 py-1 rounded-full text-xs font-bold gradient-primary text-primary-foreground">
            POPULAIRE
          </span>
        </div>
      )}

      <div className="text-center mb-6">
        <div className="mb-2 flex justify-center">
          <TierIcon className="w-8 h-8 text-primary" />
        </div>
        <h3 className="text-xl font-display font-bold text-foreground mb-2">{name}</h3>
        <p className="text-muted-foreground text-sm">{description}</p>
      </div>

      <div className="text-center mb-6">
        <span className="text-4xl font-display font-bold text-foreground">{price}</span>
        {period && <span className="text-muted-foreground text-sm">{period}</span>}
      </div>

      <ul className="space-y-3 mb-8">
        {features.map((feature, index) => (
          <li key={index} className="flex items-center gap-3 text-sm">
            <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
              <Check className="w-3 h-3 text-primary" />
            </div>
            <span className="text-foreground">{feature}</span>
          </li>
        ))}
      </ul>

      <Button
        variant={styles.button}
        className="w-full"
        size="lg"
        onClick={handleCheckout}
        disabled={loading}
      >
        {loading ? (
          <>
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            Chargement...
          </>
        ) : variant === "free" ? (
          "Commencer"
        ) : (
          "Essai gratuit 14 jours"
        )}
      </Button>
    </motion.div>
  );
};
