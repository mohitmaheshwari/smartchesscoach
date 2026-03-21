/**
 * PreGameStreakPopup.jsx - Carry-Forward Pressure Component
 * 
 * Shows before user starts a new game to remind them of:
 * - Their current streak
 * - Their focus rule
 * - The psychological pressure to not break it
 * 
 * This is the "carry-forward" mechanism that makes learning stick.
 */

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Flame,
  Target,
  Shield,
  AlertTriangle,
  X,
  Play
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

const PreGameStreakPopup = ({ 
  userId, 
  isOpen, 
  onClose, 
  onStartGame 
}) => {
  const [streakData, setStreakData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isOpen && userId) {
      fetchStreakStatus();
    }
  }, [isOpen, userId]);

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
    } finally {
      setLoading(false);
    }
  };

  const handleStartGame = () => {
    if (onStartGame) {
      onStartGame();
    }
    if (onClose) {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
          className="max-w-md w-full"
        >
          {loading ? (
            <Card className="bg-zinc-900 border-zinc-800">
              <CardContent className="p-8 text-center">
                <div className="animate-pulse">
                  <div className="w-16 h-16 bg-zinc-800 rounded-full mx-auto mb-4" />
                  <div className="h-6 bg-zinc-800 rounded w-2/3 mx-auto mb-2" />
                  <div className="h-4 bg-zinc-800 rounded w-1/2 mx-auto" />
                </div>
              </CardContent>
            </Card>
          ) : streakData ? (
            <StreakContent 
              data={streakData} 
              onClose={onClose}
              onStartGame={handleStartGame}
            />
          ) : null}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

const StreakContent = ({ data, onClose, onStartGame }) => {
  const {
    focus_mistake_name,
    rule,
    current_streak,
    best_streak,
    last_game_had_mistake,
    tone
  } = data;

  const isOnStreak = current_streak > 0;
  const isNewBest = current_streak >= best_streak && current_streak > 0;

  // Different messaging based on state
  let icon, iconBg, headline, subtext, buttonText;

  if (last_game_had_mistake) {
    // Just broke streak
    icon = <AlertTriangle className="w-8 h-8 text-red-400" />;
    iconBg = "bg-red-500/20";
    headline = "Streak Broken";
    subtext = "You repeated your core mistake. Start fresh.";
    buttonText = "Redeem Yourself";
  } else if (current_streak === 0) {
    // No streak yet
    icon = <Target className="w-8 h-8 text-zinc-400" />;
    iconBg = "bg-zinc-800";
    headline = "Start Your Streak";
    subtext = `Play a game without ${focus_mistake_name.toLowerCase()} mistakes.`;
    buttonText = "Begin";
  } else if (isNewBest) {
    // On a personal best streak
    icon = <Flame className="w-8 h-8 text-amber-400" />;
    iconBg = "bg-gradient-to-br from-amber-500/20 to-orange-500/20";
    headline = `${current_streak}-Game Streak`;
    subtext = "This is your BEST. Don't break it.";
    buttonText = "Keep It Going";
  } else {
    // Active streak, not best
    icon = <Shield className="w-8 h-8 text-blue-400" />;
    iconBg = "bg-blue-500/20";
    headline = `${current_streak}-Game Streak`;
    subtext = `Best is ${best_streak}. Can you beat it?`;
    buttonText = "Continue";
  }

  return (
    <Card className={`border ${
      last_game_had_mistake 
        ? "bg-red-950/30 border-red-500/50" 
        : isOnStreak 
          ? "bg-amber-950/30 border-amber-500/50"
          : "bg-zinc-900 border-zinc-700"
    }`}>
      <CardContent className="p-6">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-zinc-500 hover:text-white transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Icon */}
        <div className="text-center mb-4">
          <div className={`w-16 h-16 ${iconBg} rounded-full flex items-center justify-center mx-auto`}>
            {icon}
          </div>
        </div>

        {/* Headline */}
        <h2 className={`text-2xl font-bold text-center mb-2 ${
          last_game_had_mistake ? "text-red-400" : 
          isOnStreak ? "text-amber-400" : "text-white"
        }`}>
          {headline}
        </h2>

        <p className="text-zinc-400 text-center mb-6">{subtext}</p>

        {/* Rule Box */}
        <div className="bg-zinc-900/50 rounded-lg p-4 mb-6 border border-zinc-800">
          <p className="text-xs text-zinc-500 mb-2 text-center">REMEMBER YOUR RULE</p>
          <p className="text-white text-center font-semibold">{rule}</p>
        </div>

        {/* Streak Stats (if on streak) */}
        {current_streak > 0 && (
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="text-center p-3 bg-zinc-800/50 rounded-lg">
              <p className="text-2xl font-bold text-white">{current_streak}</p>
              <p className="text-xs text-zinc-500">Current</p>
            </div>
            <div className="text-center p-3 bg-zinc-800/50 rounded-lg">
              <p className="text-2xl font-bold text-amber-400">{best_streak}</p>
              <p className="text-xs text-zinc-500">Best</p>
            </div>
          </div>
        )}

        {/* CTA */}
        <Button
          onClick={onStartGame}
          className={`w-full h-12 text-lg ${
            last_game_had_mistake 
              ? "bg-red-600 hover:bg-red-700"
              : "bg-amber-600 hover:bg-amber-700"
          }`}
        >
          <Play className="w-5 h-5 mr-2" />
          {buttonText}
        </Button>
      </CardContent>
    </Card>
  );
};

export default PreGameStreakPopup;
