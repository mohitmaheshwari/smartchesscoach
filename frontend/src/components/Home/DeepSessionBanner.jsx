/**
 * Deep Session Banner - Shows when deep coaching session is due
 * 
 * Triggers:
 * - Weekly schedule
 * - 8+ games since last
 * - Regression detected
 * 
 * Shows on Home page with CTA to start coaching review.
 */

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Brain,
  ChevronRight,
  Sparkles,
  AlertTriangle,
  Calendar,
  Loader2
} from "lucide-react";

const TRIGGER_ICONS = {
  scheduled: Calendar,
  game_threshold: Brain,
  no_improvement: AlertTriangle,
  regression: AlertTriangle,
  resume: Sparkles
};

const TRIGGER_COLORS = {
  scheduled: "border-primary/30 bg-primary/5",
  game_threshold: "border-amber-500/30 bg-amber-500/5",
  no_improvement: "border-orange-500/30 bg-orange-500/5",
  regression: "border-red-500/30 bg-red-500/5",
  resume: "border-primary/30 bg-primary/5"
};

const DeepSessionBanner = ({ onStartSession }) => {
  const [loading, setLoading] = useState(true);
  const [triggerData, setTriggerData] = useState(null);

  useEffect(() => {
    checkTrigger();
  }, []);

  const checkTrigger = async () => {
    try {
      const res = await fetch(`${API}/coach/deep-session/check`, {
        credentials: "include"
      });
      
      if (res.ok) {
        const data = await res.json();
        if (data.should_trigger) {
          setTriggerData(data);
        }
      }
    } catch (err) {
      console.error("Error checking deep session trigger:", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading || !triggerData) {
    return null;
  }

  const reason = triggerData.reason;
  const Icon = TRIGGER_ICONS[reason] || Brain;
  const colorClass = TRIGGER_COLORS[reason] || TRIGGER_COLORS.scheduled;
  const isResume = reason === "resume";

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`rounded-xl border p-4 ${colorClass}`}
      data-testid="deep-session-banner"
    >
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${reason === "regression" ? "bg-red-500/20" : "bg-primary/20"}`}>
            <Icon className={`w-5 h-5 ${reason === "regression" ? "text-red-400" : "text-primary"}`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-medium text-sm">
                {isResume ? "Continue Your Review" : "Coaching Review Available"}
              </h3>
              {reason === "regression" && (
                <Badge variant="destructive" className="text-xs">
                  Needs Attention
                </Badge>
              )}
            </div>
            <p className="text-sm text-muted-foreground">
              {triggerData.message}
            </p>
          </div>
        </div>
        
        <Button 
          onClick={onStartSession}
          variant={reason === "regression" ? "destructive" : "default"}
          size="sm"
          className="gap-2 shrink-0"
          data-testid="start-deep-session-btn"
        >
          {isResume ? "Continue" : "Start Review"}
          <ChevronRight className="w-4 h-4" />
        </Button>
      </div>
    </motion.div>
  );
};

export default DeepSessionBanner;
