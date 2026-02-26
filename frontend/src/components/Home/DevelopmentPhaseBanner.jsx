/**
 * DevelopmentPhaseBanner
 * Shows the user's current development stage with visual indicator
 */

import { motion } from "framer-motion";
import { Shield, Brain, Sparkles, Target, Clock, Star } from "lucide-react";

const PHASE_ICONS = {
  tactical_discipline: Shield,
  pattern_control: Brain,
  calculation_depth: Sparkles,
  positional_sense: Target,
  time_mastery: Clock,
  advanced_refinement: Star,
};

const PHASE_COLORS = {
  amber: "from-amber-500/10 to-amber-600/5 border-amber-500/30 text-amber-500",
  blue: "from-blue-500/10 to-blue-600/5 border-blue-500/30 text-blue-500",
  violet: "from-violet-500/10 to-violet-600/5 border-violet-500/30 text-violet-500",
  emerald: "from-emerald-500/10 to-emerald-600/5 border-emerald-500/30 text-emerald-500",
  orange: "from-orange-500/10 to-orange-600/5 border-orange-500/30 text-orange-500",
  primary: "from-primary/10 to-primary/5 border-primary/30 text-primary",
};

const DevelopmentPhaseBanner = ({ phase }) => {
  if (!phase) return null;
  
  const Icon = PHASE_ICONS[phase.phase_key] || Brain;
  const colorClass = PHASE_COLORS[phase.color] || PHASE_COLORS.primary;
  
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`rounded-lg bg-gradient-to-r ${colorClass} border p-3`}
      data-testid="development-phase-banner"
    >
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-background/50 flex items-center justify-center">
          <Icon className="w-5 h-5" />
        </div>
        <div className="flex-1">
          <p className="text-xs text-muted-foreground uppercase tracking-wide mb-0.5">
            Your Focus Stage
          </p>
          <p className="font-semibold">{phase.phase_name}</p>
        </div>
      </div>
    </motion.div>
  );
};

export default DevelopmentPhaseBanner;
