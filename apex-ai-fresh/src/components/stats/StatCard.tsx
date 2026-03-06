import { motion } from "framer-motion";
import { LucideIcon } from "lucide-react";

interface StatCardProps {
  icon: LucideIcon;
  value: string;
  label: string;
  trend?: string;
  variant?: "default" | "primary" | "success" | "warning";
}

const variantStyles = {
  default: "border-white/5",
  primary: "border-primary/30 glow-primary",
  success: "border-success/30 glow-success",
  warning: "border-warning/30",
};

const iconVariantStyles = {
  default: "bg-secondary text-muted-foreground",
  primary: "gradient-primary text-primary-foreground",
  success: "gradient-success text-success-foreground",
  warning: "gradient-gold text-gold-foreground",
};

export const StatCard = ({
  icon: Icon,
  value,
  label,
  trend,
  variant = "default",
}: StatCardProps) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={`stat-card ${variantStyles[variant]}`}
    >
      <div className="flex items-start justify-between">
        <div
          className={`w-12 h-12 rounded-xl flex items-center justify-center ${iconVariantStyles[variant]}`}
        >
          <Icon className="w-6 h-6" />
        </div>
        {trend && (
          <span className="text-xs font-medium text-success bg-success/10 px-2 py-1 rounded-full">
            {trend}
          </span>
        )}
      </div>
      <div className="mt-4">
        <div className="text-3xl font-display font-bold text-foreground">{value}</div>
        <div className="text-sm text-muted-foreground mt-1">{label}</div>
      </div>
    </motion.div>
  );
};
