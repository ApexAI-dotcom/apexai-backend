import { motion } from "framer-motion";

interface ScoreCardProps {
  score: number;
  maxScore?: number;
  label: string;
  size?: "sm" | "md" | "lg";
}

const getScoreColor = (score: number) => {
  if (score >= 90) return "text-success";
  if (score >= 70) return "text-primary";
  if (score >= 50) return "text-warning";
  return "text-destructive";
};

const getScoreGradient = (score: number) => {
  if (score >= 90) return "from-success/20 to-success/5";
  if (score >= 70) return "from-primary/20 to-primary/5";
  if (score >= 50) return "from-warning/20 to-warning/5";
  return "from-destructive/20 to-destructive/5";
};

const getBadge = (score: number) => {
  if (score >= 90) return { text: "ELITE", className: "gradient-success" };
  if (score >= 70) return { text: "PRO", className: "gradient-primary" };
  if (score >= 50) return { text: "AMATEUR", className: "gradient-gold" };
  return { text: "ROOKIE", className: "bg-muted" };
};

export const ScoreCard = ({ score, maxScore = 100, label, size = "md" }: ScoreCardProps) => {
  const badge = getBadge(score);
  const percentage = (score / maxScore) * 100;

  const sizeClasses = {
    sm: "w-24 h-24",
    md: "w-32 h-32",
    lg: "w-40 h-40",
  };

  const textSizes = {
    sm: "text-2xl",
    md: "text-4xl",
    lg: "text-5xl",
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className="glass-card p-6 flex flex-col items-center"
    >
      <div className={`${sizeClasses[size]} relative flex items-center justify-center`}>
        {/* Background circle */}
        <svg className="absolute inset-0 w-full h-full -rotate-90">
          <circle
            cx="50%"
            cy="50%"
            r="45%"
            fill="none"
            stroke="hsl(var(--muted))"
            strokeWidth="8"
          />
          <motion.circle
            cx="50%"
            cy="50%"
            r="45%"
            fill="none"
            stroke="url(#scoreGradient)"
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={`${percentage * 2.83} 283`}
            initial={{ strokeDasharray: "0 283" }}
            animate={{ strokeDasharray: `${percentage * 2.83} 283` }}
            transition={{ duration: 1.5, ease: "easeOut" }}
          />
          <defs>
            <linearGradient id="scoreGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="hsl(var(--primary))" />
              <stop offset="100%" stopColor="hsl(var(--success))" />
            </linearGradient>
          </defs>
        </svg>

        {/* Score number */}
        <div className="text-center">
          <motion.span
            className={`${textSizes[size]} font-display font-bold ${getScoreColor(score)}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
          >
            {score}
          </motion.span>
          <span className="text-muted-foreground text-sm">/{maxScore}</span>
        </div>
      </div>

      {/* Badge */}
      <div
        className={`mt-4 px-3 py-1 rounded-full text-xs font-bold ${badge.className} text-primary-foreground`}
      >
        {badge.text}
      </div>

      <p className="text-muted-foreground text-sm mt-2">{label}</p>
    </motion.div>
  );
};
