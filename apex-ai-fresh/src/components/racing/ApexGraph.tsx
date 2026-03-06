import { motion } from "framer-motion";
import { Star } from "lucide-react";

interface ApexPoint {
  id: number;
  x: number;
  y: number;
  speed: number;
  radius: number;
  optimal: boolean;
}

const mockApexPoints: ApexPoint[] = [
  { id: 1, x: 15, y: 25, speed: 78, radius: 12, optimal: true },
  { id: 2, x: 35, y: 40, speed: 65, radius: 18, optimal: false },
  { id: 3, x: 55, y: 30, speed: 82, radius: 10, optimal: true },
  { id: 4, x: 75, y: 55, speed: 71, radius: 15, optimal: true },
  { id: 5, x: 85, y: 35, speed: 68, radius: 20, optimal: false },
];

// Generate smooth path through apex points
const generatePath = (points: ApexPoint[]) => {
  if (points.length < 2) return "";

  let path = `M ${points[0].x} ${points[0].y}`;

  for (let i = 1; i < points.length; i++) {
    const prev = points[i - 1];
    const curr = points[i];
    const cpX = (prev.x + curr.x) / 2;
    path += ` Q ${cpX} ${prev.y} ${curr.x} ${curr.y}`;
  }

  return path;
};

export const ApexGraph = () => {
  const pathD = generatePath(mockApexPoints);

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass-card p-6 h-full">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-display font-semibold text-lg text-foreground">Analyse des Virages</h3>
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-primary" />
            <span className="text-muted-foreground">Trajectoire</span>
          </div>
          <div className="flex items-center gap-2">
            <Star className="w-4 h-4 text-primary fill-primary" />
            <span className="text-muted-foreground">Apex optimal</span>
          </div>
        </div>
      </div>

      <div className="relative aspect-video bg-secondary/30 rounded-xl overflow-hidden">
        {/* Grid background */}
        <svg className="absolute inset-0 w-full h-full" preserveAspectRatio="none">
          <defs>
            <pattern id="grid" width="10%" height="10%" patternUnits="userSpaceOnUse">
              <path
                d="M 100 0 L 0 0 0 100"
                fill="none"
                stroke="hsl(var(--border))"
                strokeWidth="0.5"
                opacity="0.3"
              />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>

        {/* Racing line */}
        <svg
          className="absolute inset-0 w-full h-full"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
        >
          {/* Shadow path */}
          <motion.path
            d={pathD}
            fill="none"
            stroke="hsl(var(--primary) / 0.3)"
            strokeWidth="6"
            strokeLinecap="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 2, ease: "easeInOut" }}
          />

          {/* Main path */}
          <motion.path
            d={pathD}
            fill="none"
            stroke="url(#lineGradient)"
            strokeWidth="3"
            strokeLinecap="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 2, ease: "easeInOut" }}
          />

          <defs>
            <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="hsl(var(--primary))" />
              <stop offset="50%" stopColor="hsl(var(--success))" />
              <stop offset="100%" stopColor="hsl(var(--primary))" />
            </linearGradient>
          </defs>
        </svg>

        {/* Apex points */}
        {mockApexPoints.map((point, index) => (
          <motion.div
            key={point.id}
            className="absolute cursor-pointer group"
            style={{
              left: `${point.x}%`,
              top: `${point.y}%`,
              transform: "translate(-50%, -50%)",
            }}
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.5 + index * 0.2 }}
          >
            {point.optimal ? (
              <div className="relative">
                <Star className="w-6 h-6 text-primary fill-primary animate-pulse-glow" />
                <div className="absolute inset-0 blur-md bg-primary/50 rounded-full" />
              </div>
            ) : (
              <div className="w-4 h-4 rounded-full bg-warning border-2 border-warning/50" />
            )}

            {/* Tooltip */}
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              <div className="glass-card px-3 py-2 text-xs whitespace-nowrap">
                <div className="font-semibold text-foreground">Virage {point.id}</div>
                <div className="text-muted-foreground">
                  {point.speed} km/h · R{point.radius}m
                </div>
                <div className={point.optimal ? "text-success" : "text-warning"}>
                  {point.optimal ? "Apex optimal" : "À améliorer"}
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Mini stats */}
      <div className="grid grid-cols-4 gap-4 mt-4">
        {[
          { label: "Virages", value: "12" },
          { label: "Apex parfaits", value: "8/12" },
          { label: "Vitesse moy.", value: "72 km/h" },
          { label: "Temps perdu", value: "-2.3s" },
        ].map((stat) => (
          <div key={stat.label} className="text-center">
            <div className="text-lg font-display font-bold text-foreground">{stat.value}</div>
            <div className="text-xs text-muted-foreground">{stat.label}</div>
          </div>
        ))}
      </div>
    </motion.div>
  );
};
