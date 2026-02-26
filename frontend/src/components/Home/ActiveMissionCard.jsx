/**
 * ActiveMissionCard
 * Shows the current active mission with focus and protocol
 */

import { motion } from "framer-motion";
import { Target, Clock, Play, ChevronRight, Loader2, Flame } from "lucide-react";
import { Button } from "@/components/ui/button";

const ActiveMissionCard = ({ 
  mission, 
  onStart, 
  starting = false,
  compact = false 
}) => {
  if (!mission) return null;
  
  const isActive = mission.status === "active";
  const minutes = mission.estimated_minutes || 7;
  const goal = mission.goal?.target || 5;
  const protocol = mission.micro_protocol || [];
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-border bg-card p-5"
      data-testid="active-mission-card"
    >
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Target className="w-5 h-5 text-primary" />
            <span className="text-sm font-medium text-primary">
              {isActive ? "Continue Mission" : "Today's Mission"}
            </span>
          </div>
          {mission.streak_count > 0 && (
            <span className="flex items-center gap-1 text-xs text-amber-500">
              <Flame className="w-3.5 h-3.5" />
              {mission.streak_count} day streak
            </span>
          )}
        </div>
        
        {/* Focus Label */}
        <h3 className="text-xl font-bold tracking-tight">
          {mission.focus_label || "Focus Training"}
        </h3>
        
        {/* Protocol Preview (if not compact) */}
        {!compact && protocol.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground uppercase tracking-wide">
              Before each move
            </p>
            <div className="space-y-1.5">
              {protocol.slice(0, 2).map((step, idx) => (
                <div key={idx} className="flex items-center gap-2 text-sm">
                  <span className="w-5 h-5 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-medium">
                    {idx + 1}
                  </span>
                  <span className="text-muted-foreground">{step}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Meta */}
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Clock className="w-4 h-4" />
            {minutes} min
          </span>
          <span className="flex items-center gap-1.5">
            <Target className="w-4 h-4" />
            {goal} positions
          </span>
        </div>
        
        {/* CTA */}
        <Button 
          onClick={onStart}
          disabled={starting}
          className="w-full font-semibold"
          data-testid="start-mission-btn"
        >
          {starting ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : isActive ? (
            <>
              Continue
              <Play className="w-4 h-4 ml-2" />
            </>
          ) : (
            <>
              Start Mission
              <ChevronRight className="w-4 h-4 ml-2" />
            </>
          )}
        </Button>
      </div>
    </motion.div>
  );
};

export default ActiveMissionCard;
