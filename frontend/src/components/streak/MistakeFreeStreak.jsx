/**
 * MistakeFreeStreak.jsx - Dashboard Streak Display Component
 * 
 * Shows the user's current mistake-free streak prominently on the dashboard.
 * This is NOT gamification - it's proof of behavior change.
 * 
 * Features:
 * - Current streak count
 * - Best streak (personal record)
 * - Focus mistake name and rule
 * - Improvement trend (after 5 games)
 */

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Flame,
  Target,
  TrendingUp,
  Trophy,
  AlertTriangle,
  ArrowRight,
  Zap
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

/**
 * @param {Object} props
 * @param {string} props.userId - User ID for fetching streak data
 * @param {boolean} props.blockerDetected - Whether the parent dashboard has detected a blocker (prevents conflicting UI)
 * @param {Object} props.blockerInfo - Blocker info from parent (type, name, rule) to use as fallback
 * @param {Function} props.onStartTraining - Callback when training CTA is clicked
 */
const MistakeFreeStreak = ({ userId, blockerDetected = false, blockerInfo = null, onStartTraining }) => {
  const [streakData, setStreakData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (userId) {
      fetchStreakStatus();
    }
  }, [userId]);

  const fetchStreakStatus = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API}/streak/status?user_id=${userId}`, {
        credentials: "include"
      });
      
      if (!res.ok) throw new Error("Failed to fetch streak");
      
      const data = await res.json();
      setStreakData(data);
    } catch (err) {
      console.error("Error fetching streak:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card className="bg-zinc-900/50 border-zinc-800">
        <CardContent className="p-6">
          <div className="animate-pulse flex items-center gap-4">
            <div className="w-16 h-16 bg-zinc-800 rounded-full" />
            <div className="flex-1 space-y-2">
              <div className="h-6 bg-zinc-800 rounded w-1/2" />
              <div className="h-4 bg-zinc-800 rounded w-3/4" />
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !streakData) {
    return null; // Silently fail
  }

  // Extract data from streak API
  let {
    focus_mistake_name,
    rule,
    current_streak,
    best_streak,
    last_game_had_mistake,
    headline,
    message,
    tone,
    trend,
    needs_detection
  } = streakData;

  // CRITICAL FIX: If streak API says "needs_detection" but parent dashboard found a blocker,
  // use the blocker info instead of showing conflicting "No Weakness Detected" message.
  // This happens when blunder_taxonomy has data but streak_data.current_focus_mistake is null.
  if (needs_detection && blockerDetected && blockerInfo) {
    // Override with blocker info from parent
    focus_mistake_name = blockerInfo.name || "Your Current Blocker";
    rule = blockerInfo.rule || "Fix this pattern to improve";
    headline = "Start Your Streak";
    message = "Play a game without this mistake to begin your streak.";
    tone = "neutral";
    needs_detection = false; // Don't show "no detection" state
    current_streak = 0;
    best_streak = 0;
  }
  
  // If still needs detection after fallback check, show "needs detection" state
  // This should only happen if NO blocker was found anywhere
  if (needs_detection) {
    return (
      <Card className="bg-zinc-900/50 border-zinc-700" data-testid="mistake-free-streak-needs-detection">
        <CardContent className="p-6">
          <div className="flex items-start gap-4">
            <div className="w-16 h-16 rounded-full bg-zinc-800/50 flex items-center justify-center">
              <Target className="w-8 h-8 text-zinc-500" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-bold text-white mb-1">No Weakness Detected Yet</h3>
              <p className="text-zinc-400 text-sm mb-3">
                Play and analyze some games first. We'll identify your biggest mistake pattern.
              </p>
              <div className="p-3 bg-zinc-800/50 rounded-lg">
                <p className="text-xs text-zinc-500">HOW IT WORKS</p>
                <p className="text-sm text-zinc-300 mt-1">
                  Import games → We analyze → Detect your pattern → Start your streak
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Determine colors based on tone
  const toneStyles = {
    celebration: {
      bg: "bg-amber-950/30",
      border: "border-amber-500/50",
      icon: "text-amber-400",
      headline: "text-amber-400"
    },
    success: {
      bg: "bg-green-950/30",
      border: "border-green-500/50",
      icon: "text-green-400",
      headline: "text-green-400"
    },
    active: {
      bg: "bg-blue-950/30",
      border: "border-blue-500/50",
      icon: "text-blue-400",
      headline: "text-blue-400"
    },
    warning: {
      bg: "bg-red-950/30",
      border: "border-red-500/50",
      icon: "text-red-400",
      headline: "text-red-400"
    },
    neutral: {
      bg: "bg-zinc-900/50",
      border: "border-zinc-700",
      icon: "text-zinc-400",
      headline: "text-white"
    }
  };

  const style = toneStyles[tone] || toneStyles.neutral;

  return (
    <Card className={`${style.bg} ${style.border}`} data-testid="mistake-free-streak">
      <CardContent className="p-6">
        {/* Main Streak Display */}
        <div className="flex items-start gap-4">
          {/* Streak Number */}
          <motion.div
            initial={{ scale: 0.8 }}
            animate={{ scale: 1 }}
            className={`w-20 h-20 rounded-full flex items-center justify-center ${
              current_streak > 0 
                ? "bg-gradient-to-br from-amber-500/20 to-orange-500/20" 
                : "bg-zinc-800/50"
            }`}
          >
            {current_streak > 0 ? (
              <div className="text-center">
                <Flame className="w-6 h-6 text-amber-400 mx-auto" />
                <span className="text-2xl font-bold text-white">{current_streak}</span>
              </div>
            ) : (
              <Target className={`w-8 h-8 ${style.icon}`} />
            )}
          </motion.div>

          {/* Streak Info */}
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h3 className={`text-lg font-bold ${style.headline}`}>
                {headline}
              </h3>
              {current_streak >= best_streak && current_streak > 0 && (
                <Trophy className="w-4 h-4 text-amber-400" />
              )}
            </div>
            
            <p className="text-zinc-400 text-sm mb-2">{message}</p>
            
            {/* Focus Mistake Name */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-zinc-500">TRACKING:</span>
              <span className="text-sm font-medium text-white">{focus_mistake_name}</span>
            </div>

            {/* Best Streak */}
            {best_streak > 0 && current_streak < best_streak && (
              <div className="flex items-center gap-2 mt-1">
                <Trophy className="w-3 h-3 text-zinc-500" />
                <span className="text-xs text-zinc-500">Best: {best_streak} games</span>
              </div>
            )}
          </div>
        </div>

        {/* Rule Reminder */}
        <div className="mt-4 p-3 bg-zinc-900/50 rounded-lg border border-zinc-800">
          <p className="text-xs text-zinc-500 mb-1">YOUR RULE</p>
          <p className="text-sm text-white font-medium">{rule}</p>
        </div>

        {/* Improvement Trend (only show after 5 games) */}
        {trend?.show_trend && trend.improvement_pct !== null && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-4 p-3 bg-green-500/10 rounded-lg border border-green-500/20"
          >
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-green-400" />
              <span className="text-sm text-green-400 font-medium">
                {trend.improvement_pct > 0 
                  ? `${trend.improvement_pct}% fewer mistakes`
                  : "Tracking progress..."}
              </span>
            </div>
            {trend.before_avg && trend.recent_avg && (
              <p className="text-xs text-zinc-500 mt-1">
                Before: {trend.before_avg.toFixed(1)}/game → Now: {trend.recent_avg.toFixed(1)}/game
              </p>
            )}
          </motion.div>
        )}

        {/* CTA for new users or after streak break */}
        {(current_streak === 0 || last_game_had_mistake) && onStartTraining && (
          <Button
            onClick={onStartTraining}
            className="w-full mt-4 bg-amber-600 hover:bg-amber-700"
          >
            <Zap className="w-4 h-4 mr-2" />
            {last_game_had_mistake ? "Fix This Now" : "Start Training"}
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        )}
      </CardContent>
    </Card>
  );
};

export default MistakeFreeStreak;
