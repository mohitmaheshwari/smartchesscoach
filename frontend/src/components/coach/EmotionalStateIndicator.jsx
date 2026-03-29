/**
 * Emotional State Indicator
 * 
 * Shows the coach's awareness of the player's emotional state.
 * Adapts tone and offers support based on detected state.
 */

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import {
  Brain,
  Target,
  Flame,
  Heart,
  RefreshCw,
  Clock,
  Sparkles,
  Coffee,
  X
} from "lucide-react";

// Emotional state configurations
const STATE_CONFIG = {
  confident: { 
    icon: Flame, 
    color: "text-orange-500", 
    bg: "bg-orange-500/10",
    border: "border-orange-500/30",
    label: "You're on fire!",
    message: "Keep that energy going!"
  },
  frustrated: { 
    icon: Heart, 
    color: "text-red-400", 
    bg: "bg-red-500/10",
    border: "border-red-500/30",
    label: "Tough stretch",
    message: "Chess is hard. Let's focus on one thing."
  },
  tilted: { 
    icon: RefreshCw, 
    color: "text-amber-500", 
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    label: "Take a breather?",
    message: "A short break might help you see the board fresh."
  },
  rushed: { 
    icon: Clock, 
    color: "text-blue-400", 
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
    label: "Slow down",
    message: "No rush. The position will wait for you."
  },
  uncertain: { 
    icon: Brain, 
    color: "text-purple-400", 
    bg: "bg-purple-500/10",
    border: "border-purple-500/30",
    label: "Thinking hard",
    message: "Trust your instincts. You know more than you think."
  },
  focused: { 
    icon: Target, 
    color: "text-emerald-500", 
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
    label: "In the zone",
    message: "Great focus! Keep it up."
  },
  neutral: { 
    icon: Sparkles, 
    color: "text-primary", 
    bg: "bg-primary/10",
    border: "border-primary/30",
    label: "Ready to learn",
    message: "Let's make some good moves!"
  }
};

const EmotionalStateIndicator = ({ 
  blundersThisGame = 0,
  avgMoveTime = 0,
  recentResults = [],
  onTakeBreak
}) => {
  const [state, setState] = useState(null);
  const [dismissed, setDismissed] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    detectState();
  }, [blundersThisGame, recentResults?.length]);

  const detectState = async () => {
    // Only detect if we have some game context
    if (blundersThisGame === 0 && recentResults.length === 0) {
      setState(null);
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API}/coach/human-coach/emotional-state`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          recent_results: recentResults,
          avg_move_time: avgMoveTime,
          blunders_this_game: blundersThisGame
        })
      });

      if (response.ok) {
        const data = await response.json();
        setState(data);
        setDismissed(false);
      }
    } catch (error) {
      console.error("Error detecting emotional state:", error);
    } finally {
      setLoading(false);
    }
  };

  // Don't show for neutral state or if dismissed
  if (!state || state.emotional_state === "neutral" || dismissed) {
    return null;
  }

  const config = STATE_CONFIG[state.emotional_state] || STATE_CONFIG.neutral;
  const StateIcon = config.icon;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -10, height: 0 }}
        animate={{ opacity: 1, y: 0, height: "auto" }}
        exit={{ opacity: 0, y: -10, height: 0 }}
        className={`mx-4 mt-3 p-3 rounded-lg ${config.bg} border ${config.border}`}
        data-testid="emotional-state-indicator"
      >
        <div className="flex items-start gap-3">
          <div className={`w-8 h-8 rounded-full ${config.bg} flex items-center justify-center flex-shrink-0`}>
            <StateIcon className={`w-4 h-4 ${config.color}`} />
          </div>
          
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <span className={`font-medium text-sm ${config.color}`}>
                {config.label}
              </span>
              <button 
                onClick={() => setDismissed(true)}
                className="text-muted-foreground hover:text-foreground p-1 -m-1"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              {config.message}
            </p>
            
            {/* Show break button for tilted state */}
            {state.should_offer_break && onTakeBreak && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onTakeBreak}
                className={`mt-2 h-7 text-xs ${config.color} hover:${config.bg}`}
              >
                <Coffee className="w-3 h-3 mr-1" />
                Take a 5-min break
              </Button>
            )}
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
};

export default EmotionalStateIndicator;
