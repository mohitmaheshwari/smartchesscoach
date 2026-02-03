import { motion } from "framer-motion";

/**
 * Apple Fitness-style progress ring
 */
export const ProgressRing = ({ 
  progress = 0, 
  size = 80, 
  strokeWidth = 8,
  color = "stroke-emerald-500",
  bgColor = "stroke-muted",
  label,
  sublabel
}) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (progress / 100) * circumference;
  
  return (
    <div className="relative inline-flex items-center justify-center" data-testid="progress-ring">
      <svg width={size} height={size} className="progress-ring">
        {/* Background ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          className={bgColor}
        />
        {/* Progress ring */}
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          className={color}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          style={{
            strokeDasharray: circumference,
          }}
        />
      </svg>
      {(label || sublabel) && (
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {label && <span className="text-lg font-semibold font-heading">{label}</span>}
          {sublabel && <span className="text-xs text-muted-foreground">{sublabel}</span>}
        </div>
      )}
    </div>
  );
};

/**
 * Status badge with directional indicator
 * Types: improving, stable, needs_attention
 */
export const StatusBadge = ({ status, label }) => {
  const configs = {
    improving: {
      bg: "bg-emerald-500/10",
      text: "text-emerald-600 dark:text-emerald-400",
      icon: "↑",
      label: label || "Improving"
    },
    stable: {
      bg: "bg-zinc-500/10",
      text: "text-zinc-600 dark:text-zinc-400",
      icon: "→",
      label: label || "Stable"
    },
    needs_attention: {
      bg: "bg-amber-500/10",
      text: "text-amber-600 dark:text-amber-400",
      icon: "↓",
      label: label || "Focus"
    }
  };
  
  const config = configs[status] || configs.stable;
  
  return (
    <motion.span
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium ${config.bg} ${config.text}`}
      data-testid={`status-badge-${status}`}
    >
      <span className="font-mono">{config.icon}</span>
      {config.label}
    </motion.span>
  );
};

/**
 * Trend indicator arrow with value
 */
export const TrendIndicator = ({ trend, value }) => {
  const configs = {
    improving: { icon: "↓", color: "text-emerald-500", label: "Better" },
    worsening: { icon: "↑", color: "text-amber-500", label: "Watch" },
    stable: { icon: "→", color: "text-muted-foreground", label: "Steady" }
  };
  
  const config = configs[trend] || configs.stable;
  
  return (
    <div className={`flex items-center gap-1 text-sm ${config.color}`} data-testid={`trend-${trend}`}>
      <span className="font-mono text-lg">{config.icon}</span>
      {value && <span className="font-medium">{value}</span>}
    </div>
  );
};

/**
 * Stat card with optional trend
 */
export const StatCard = ({ 
  label, 
  value, 
  sublabel, 
  trend,
  icon: Icon 
}) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="surface p-4 card-hover"
      data-testid="stat-card"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="label-caps mb-1">{label}</p>
          <p className="text-2xl font-heading font-semibold tracking-tight">{value}</p>
          {sublabel && (
            <p className="text-sm text-muted-foreground mt-1">{sublabel}</p>
          )}
        </div>
        <div className="flex flex-col items-end gap-2">
          {Icon && <Icon className="w-5 h-5 text-muted-foreground" />}
          {trend && <TrendIndicator trend={trend} />}
        </div>
      </div>
    </motion.div>
  );
};

/**
 * Coach message card
 */
export const CoachMessage = ({ message, title }) => {
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      className="coach-message"
      data-testid="coach-message"
    >
      {title && (
        <p className="label-caps mb-2">{title}</p>
      )}
      <p className="text-foreground leading-relaxed">{message}</p>
    </motion.div>
  );
};

/**
 * Section header with uppercase label
 */
export const SectionHeader = ({ label, action }) => {
  return (
    <div className="flex items-center justify-between mb-4">
      <h3 className="label-caps">{label}</h3>
      {action}
    </div>
  );
};

/**
 * Animated list container
 */
export const AnimatedList = ({ children, className = "" }) => {
  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={{
        visible: {
          transition: {
            staggerChildren: 0.05
          }
        }
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
};

/**
 * Animated list item
 */
export const AnimatedItem = ({ children, className = "" }) => {
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: 10 },
        visible: { opacity: 1, y: 0 }
      }}
      transition={{ duration: 0.2 }}
      className={className}
    >
      {children}
    </motion.div>
  );
};
