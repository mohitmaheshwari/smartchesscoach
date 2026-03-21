/**
 * PlateauBreakerDashboard.jsx - V1 Enforced Dashboard
 * 
 * PHILOSOPHY: "One game = One mistake = One rule = One enforced action"
 * 
 * Shows ONLY:
 * 1. Your Current Blocker (biggest mistake)
 * 2. How many times it happened
 * 3. "Fix This Now" CTA
 * 
 * Nothing else. No distractions.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { 
  AlertTriangle, 
  Target, 
  ArrowRight, 
  Lock,
  Unlock,
  TrendingDown,
  Zap,
  CheckCircle
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { MistakeFreeStreak } from "@/components/streak";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

// Map mistake types to user-friendly messages - HARSH but true
const BLOCKER_MESSAGES = {
  "hanging_piece": {
    title: "You leave pieces undefended",
    why: "You are a player who moves without checking if pieces are safe. This is why you're stuck at your rating.",
    rule: "Before EVERY move, count attackers vs defenders.",
    icon: "♟️",
    identity: "a careless player"
  },
  "tactical_error": {
    title: "You miss opponent's threats",
    why: "You are a player who ignores what the opponent is doing. You move, then get surprised. This is why you lose games you should win.",
    rule: "Before EVERY move, ask: What is my opponent threatening?",
    icon: "⚔️",
    identity: "an oblivious player"
  },
  "missed_tactic": {
    title: "You miss winning moves",
    why: "You are a player who plays 'safe' when winning moves exist. You see threats but don't look for opportunities. This is why you draw games you should win.",
    rule: "Before EVERY move: Checks, Captures, Threats (in that order).",
    icon: "💥",
    identity: "a passive player"
  },
  "positional_mistake": {
    title: "You make planless moves",
    why: "You are a player who moves pieces randomly without a plan. Your pieces look active but achieve nothing. This is why stronger players crush you in the middlegame.",
    rule: "Before EVERY move, ask: What is my plan for the next 3 moves?",
    icon: "🎯",
    identity: "a planless player"
  },
  "time_trouble": {
    title: "You blunder under pressure",
    why: "You are a player who panics with low time. All your good work disappears in the last 2 minutes. This is why you lose won games.",
    rule: "Under 2 minutes: Simplify. Trade pieces. Don't calculate.",
    icon: "⏱️",
    identity: "a time-trouble player"
  },
  "opening_error": {
    title: "You lose in the opening",
    why: "You are a player who doesn't know basic opening principles. You're already losing before move 10. This is why you start every game at a disadvantage.",
    rule: "Opening: Develop pieces, Control center, Castle early.",
    icon: "📖",
    identity: "an unprepared player"
  },
  "endgame_error": {
    title: "You can't convert wins",
    why: "You are a player who doesn't know endgame basics. You get winning positions, then throw them away. This is why you draw games you should win.",
    rule: "Endgame: Activate king, Push passed pawns, Cut off enemy king.",
    icon: "👑",
    identity: "an endgame amateur"
  }
};

const PlateauBreakerDashboard = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [blockerData, setBlockerData] = useState(null);
  const [trainingStatus, setTrainingStatus] = useState(null);
  const [recentGame, setRecentGame] = useState(null);

  useEffect(() => {
    fetchBlockerData();
  }, [user]);

  const fetchBlockerData = async () => {
    try {
      setLoading(true);
      
      // Fetch player identity for weakness data
      const identityRes = await fetch(`${API}/coach/deep-memory?user_id=${user?.user_id}`, {
        credentials: "include"
      });
      const identityData = await identityRes.json();
      
      // Fetch recent games
      const gamesRes = await fetch(`${API}/games?user_id=${user?.user_id}&limit=10`, {
        credentials: "include"
      });
      const gamesData = await gamesRes.json();
      
      // If user is not logged in, we can't show real data
      if (!user?.user_id) {
        setLoading(false);
        return;
      }

      // Find the biggest blocker from pattern data
      const patterns = identityData.blunder_taxonomy || {};
      let biggestBlocker = null;
      let maxCount = 0;
      
      for (const [type, count] of Object.entries(patterns)) {
        if (count > maxCount) {
          maxCount = count;
          biggestBlocker = type;
        }
      }
      
      // Also check streak data for current focus (backend source of truth)
      let streakFocusMistake = null;
      try {
        const streakRes = await fetch(`${API}/streak/status?user_id=${user?.user_id}`, {
          credentials: "include"
        });
        if (streakRes.ok) {
          const streakData = await streakRes.json();
          streakFocusMistake = streakData.focus_mistake_type;
        }
      } catch (e) {
        console.warn("Could not fetch streak data");
      }
      
      // Determine blocker source:
      // 1. If we have real pattern data with count > 0, use that
      // 2. Otherwise use streak focus (which is the active training focus)
      // 3. Only show "no data" state if truly no focus set
      
      let blockerSource = "pattern";
      if (!biggestBlocker || maxCount === 0) {
        if (streakFocusMistake) {
          // Map streak focus to blocker type
          const focusToBlocker = {
            "THREAT_VERIFICATION": "tactical_error",
            "FORCING_BLIND": "missed_tactic",
            "STOPPED_CALCULATION_EARLY": "calculation_error",
            "HANGING_PIECE": "hanging_piece",
            "TACTICAL_MISS": "missed_tactic"
          };
          biggestBlocker = focusToBlocker[streakFocusMistake] || "tactical_error";
          blockerSource = "streak_focus";
        } else {
          // Truly no data - will show "needs games" state
          biggestBlocker = null;
        }
      }
      
      // Get message config
      const blockerConfig = biggestBlocker 
        ? (BLOCKER_MESSAGES[biggestBlocker] || BLOCKER_MESSAGES["tactical_error"])
        : null;
      
      // Calculate occurrence rate
      const totalGames = identityData.games_analyzed || 10;
      const occurrenceRate = maxCount > 0 ? Math.round((maxCount / totalGames) * 100) : 0;
      
      // Set blocker data based on source
      if (blockerConfig) {
        setBlockerData({
          type: biggestBlocker,
          count: maxCount,
          totalGames,
          occurrenceRate,
          source: blockerSource, // "pattern" or "streak_focus"
          isActiveTraining: blockerSource === "streak_focus",
          ...blockerConfig
        });
      } else {
        // No blocker data at all - needs more games
        setBlockerData({
          type: null,
          count: 0,
          totalGames: 0,
          occurrenceRate: 0,
          source: "none",
          title: "Play More Games",
          why: "We need to analyze your games to find your biggest weakness. Import or play some games first.",
          rule: "Start by playing a few games so we can identify your pattern."
        });
      }
      
      // Get most recent unreviewed game
      const games = gamesData.games || gamesData || [];
      const analyzedGames = games.filter(g => g.is_analyzed);
      if (analyzedGames.length > 0) {
        setRecentGame(analyzedGames[0]);
      }
      
      // Check training status (localStorage for now, should be backend)
      const savedStatus = localStorage.getItem(`training_status_${user?.user_id}`);
      if (savedStatus) {
        setTrainingStatus(JSON.parse(savedStatus));
      } else {
        setTrainingStatus({
          puzzlesCompleted: 0,
          puzzlesRequired: 5,
          coachGamesPlayed: 0,
          isUnlocked: false
        });
      }
      
    } catch (err) {
      console.error("Error fetching blocker data:", err);
      // Set defaults
      setBlockerData({
        type: "tactical_error",
        count: 0,
        totalGames: 0,
        occurrenceRate: 0,
        ...BLOCKER_MESSAGES["tactical_error"]
      });
    } finally {
      setLoading(false);
    }
  };

  const handleFixNow = () => {
    // Navigate to focused review with blocker context
    if (recentGame) {
      navigate(`/plateau-breaker/review/${recentGame.game_id}`, {
        state: { blocker: blockerData }
      });
    } else {
      // No game to review, go to training
      navigate("/plateau-breaker/training", {
        state: { blocker: blockerData }
      });
    }
  };

  const handlePlayCoached = () => {
    navigate("/plateau-breaker/play", {
      state: { blocker: blockerData, enforced: true }
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
          className="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full"
        />
      </div>
    );
  }

  const isTrainingComplete = trainingStatus?.puzzlesCompleted >= trainingStatus?.puzzlesRequired;

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      {/* Header - Minimal */}
      <div className="border-b border-zinc-800 p-4">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <h1 className="text-lg font-semibold text-amber-500">Chess Coach</h1>
          <span className="text-sm text-zinc-500">Plateau Breaker Mode</span>
        </div>
      </div>

      {/* Main Content - Focused */}
      <div className="max-w-2xl mx-auto p-6 space-y-8">
        
        {/* MISTAKE-FREE STREAK - Proof of improvement */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <MistakeFreeStreak 
            userId={user?.user_id}
            onStartTraining={() => navigate("/plateau-breaker/training", { state: { blocker: blockerData } })}
          />
        </motion.div>
        
        {/* THE BLOCKER - Only show if we have detected one */}
        {blockerData?.type ? (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            <Card className="bg-red-950/30 border-red-500/50 overflow-hidden">
              <CardContent className="p-0">
                {/* Red Alert Header */}
              <div className="bg-red-500/20 px-6 py-4 border-b border-red-500/30">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-full bg-red-500/30 flex items-center justify-center">
                    <AlertTriangle className="w-6 h-6 text-red-400" />
                  </div>
                  <div>
                    <p className="text-red-400 text-sm font-medium uppercase tracking-wide">
                      Your Current Blocker
                    </p>
                    <h2 className="text-2xl font-bold text-white">
                      {blockerData?.title}
                    </h2>
                  </div>
                </div>
              </div>

              {/* The Why */}
              <div className="px-6 py-5 space-y-4">
                <p className="text-lg text-zinc-300">
                  {blockerData?.why}
                </p>

                {/* Stats - Show based on data source */}
                <div className="flex items-center gap-4 py-3 px-4 bg-zinc-900/50 rounded-lg">
                  <TrendingDown className="w-5 h-5 text-red-400" />
                  <div>
                    {blockerData?.source === "pattern" && blockerData?.count > 0 ? (
                      <>
                        <p className="text-white font-bold">
                          {blockerData?.count} times in your last {blockerData?.totalGames} games
                        </p>
                        <p className="text-sm text-zinc-500">
                          {blockerData?.occurrenceRate}% of your games have this problem
                        </p>
                      </>
                    ) : blockerData?.source === "streak_focus" ? (
                      <>
                        <p className="text-white font-bold">
                          This is your current training focus
                        </p>
                        <p className="text-sm text-zinc-500">
                          Practice until you stop making this mistake
                        </p>
                      </>
                    ) : (
                      <>
                        <p className="text-white font-bold">
                          No data yet
                        </p>
                        <p className="text-sm text-zinc-500">
                          Play some games to identify your patterns
                        </p>
                      </>
                    )}
                  </div>
                </div>

                {/* The Rule */}
                <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <Target className="w-5 h-5 text-amber-400 mt-0.5" />
                    <div>
                      <p className="text-amber-400 text-sm font-medium mb-1">Your Rule</p>
                      <p className="text-white font-semibold text-lg">
                        {blockerData?.rule}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* CTA */}
              <div className="px-6 py-4 bg-zinc-900/30 border-t border-zinc-800">
                <Button 
                  onClick={handleFixNow}
                  className="w-full h-14 text-lg font-bold bg-red-600 hover:bg-red-700"
                >
                  <Zap className="w-5 h-5 mr-2" />
                  Fix This Now
                  <ArrowRight className="w-5 h-5 ml-2" />
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
        ) : (
          /* No blocker detected - show "needs games" state */
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            <Card className="bg-zinc-900/50 border-zinc-700">
              <CardContent className="p-6">
                <div className="text-center py-8">
                  <Target className="w-12 h-12 text-zinc-500 mx-auto mb-4" />
                  <h3 className="text-xl font-bold text-white mb-2">No Weakness Detected Yet</h3>
                  <p className="text-zinc-400 mb-6 max-w-md mx-auto">
                    We need to analyze your games to find your biggest mistake pattern. 
                    Import some games or play against the coach first.
                  </p>
                  <div className="flex gap-3 justify-center">
                    <Button
                      onClick={() => navigate("/import")}
                      variant="outline"
                      className="border-zinc-700"
                    >
                      Import Games
                    </Button>
                    <Button
                      onClick={() => navigate("/play-with-coach")}
                      className="bg-amber-600 hover:bg-amber-700"
                    >
                      Play With Coach
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Training Progress - Only show if blocker exists */}
        {blockerData?.type && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <Card className="bg-zinc-900/50 border-zinc-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  {isTrainingComplete ? (
                    <Unlock className="w-5 h-5 text-green-400" />
                  ) : (
                    <Lock className="w-5 h-5 text-zinc-500" />
                  )}
                  <span className="font-medium">
                    {isTrainingComplete ? "Training Complete" : "Training Required"}
                  </span>
                </div>
                <span className="text-sm text-zinc-500">
                  {trainingStatus?.puzzlesCompleted || 0} / {trainingStatus?.puzzlesRequired || 5} puzzles
                </span>
              </div>
              
              <Progress 
                value={(trainingStatus?.puzzlesCompleted / trainingStatus?.puzzlesRequired) * 100} 
                className="h-2 mb-4"
              />

              {isTrainingComplete ? (
                <div className="flex items-center gap-2 text-green-400 text-sm">
                  <CheckCircle className="w-4 h-4" />
                  <span>You can now play your next game!</span>
                </div>
              ) : (
                <p className="text-sm text-zinc-500">
                  Complete {trainingStatus?.puzzlesRequired - trainingStatus?.puzzlesCompleted} more puzzles to unlock your next game analysis.
                </p>
              )}
            </CardContent>
          </Card>
        </motion.div>
        )}

        {/* Play with Enforcement */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
        >
          <Card className="bg-zinc-900/50 border-zinc-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-semibold text-white">Play with Enforced Coaching</h3>
                  <p className="text-sm text-zinc-500 mt-1">
                    Play a game where the coach blocks mistakes before they happen
                  </p>
                </div>
                <Button 
                  onClick={handlePlayCoached}
                  variant="outline"
                  className="border-amber-500/50 text-amber-400 hover:bg-amber-500/10"
                >
                  Play Now
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Back to Classic Mode */}
        <div className="text-center pt-4">
          <button 
            onClick={() => navigate("/home")}
            className="text-sm text-zinc-600 hover:text-zinc-400 transition-colors"
          >
            Switch to Classic Mode →
          </button>
        </div>
      </div>
    </div>
  );
};

export default PlateauBreakerDashboard;
