/**
 * RecommendedDrillCard
 * Shows the recommended drill based on current development phase
 */

import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { Dumbbell, ChevronRight, Crosshair, Brain, Sparkles, Clock, Target } from "lucide-react";
import { Button } from "@/components/ui/button";

const DRILL_ICONS = {
  threat_detection: Crosshair,
  pattern_recognition: Brain,
  calculation: Sparkles,
  positional: Target,
  speed: Clock,
  precision: Sparkles,
};

const RecommendedDrillCard = ({ drill, advice }) => {
  const navigate = useNavigate();
  
  if (!drill) return null;
  
  const Icon = DRILL_ICONS[drill.type] || Dumbbell;
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-border bg-card p-5"
      data-testid="recommended-drill-card"
    >
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
            <Icon className="w-5 h-5 text-primary" />
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wide">
              Recommended Drill
            </p>
            <p className="font-semibold">{drill.title}</p>
          </div>
        </div>
        
        {/* Description */}
        <p className="text-sm text-muted-foreground">
          {drill.description}
        </p>
        
        {/* Advice Context */}
        {advice?.last_game_context && (
          <div className="p-3 rounded-lg bg-muted/30 text-sm text-muted-foreground">
            {advice.last_game_context}
          </div>
        )}
        
        {/* CTA */}
        <Button 
          variant="outline"
          className="w-full"
          onClick={() => navigate("/training")}
          data-testid="start-drill-btn"
        >
          Start Training
          <ChevronRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </motion.div>
  );
};

export default RecommendedDrillCard;
