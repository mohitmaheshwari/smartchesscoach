/**
 * ActiveAdviceCard
 * Shows the single most important thing to focus on
 * This is the core of the "coach" experience
 */

import { motion } from "framer-motion";
import { Lightbulb, Target } from "lucide-react";

const ActiveAdviceCard = ({ advice, focusCapacity }) => {
  if (!advice) return null;
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border-2 border-primary/30 bg-primary/5 p-5"
      data-testid="active-advice-card"
    >
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center gap-2">
          <Lightbulb className="w-5 h-5 text-primary" />
          <span className="text-sm font-semibold text-primary uppercase tracking-wide">
            Your Focus
          </span>
        </div>
        
        {/* Primary Advice */}
        <p className="text-lg font-medium leading-relaxed">
          {advice.primary}
        </p>
        
        {/* Secondary Advice (if capacity allows) */}
        {advice.secondary && focusCapacity !== "single" && (
          <div className="pt-2 border-t border-primary/10">
            <p className="text-sm text-muted-foreground flex items-center gap-2">
              <Target className="w-4 h-4" />
              {advice.secondary}
            </p>
          </div>
        )}
      </div>
    </motion.div>
  );
};

export default ActiveAdviceCard;
