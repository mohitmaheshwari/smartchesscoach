/**
 * CoachHome - The Personal Coaching Home Page
 * 
 * Vision: Replace human coaches by feeling personal, warm, and actionable.
 * 
 * Target User: 600-1500 rated players who:
 * - Make tactical mistakes and want to improve
 * - Need ONE clear thing to focus on
 * - Want to feel like they're making progress
 * - Respond to encouragement, not overwhelm
 * 
 * State-Based Priority:
 * 1. Has games to reflect → REFLECT is primary (this is where learning happens)
 * 2. All games reflected → TRAIN is primary (practice the specific weakness)
 * 3. No recent games → Encourage PLAY (feed the loop)
 * 
 * The Coaching Loop: PLAY → REFLECT → TRAIN → PLAY
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import {
  ActiveMissionCard,
  DeepSessionBanner,
} from "@/components/Home";
import DeepSessionModal from "@/components/DeepSessionModal";
import {
  ChevronRight,
  Loader2,
  Target,
  Brain,
  Gamepad2,
  Trophy,
  AlertCircle,
  CheckCircle2,
  Clock,
  TrendingUp,
  Sparkles,
  MessageCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

// Helper to format time since
const getTimeSince = (dateStr) => {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now - date;
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHours / 24);
  
  if (diffDays > 0) return `${diffDays}d ago`;
  if (diffHours > 0) return `${diffHours}h ago`;
  return "Just now";
};

// Get result emoji and color
const getResultStyle = (result) => {
  if (result === "win") return { emoji: "✓", color: "text-green-500", bg: "bg-green-500/10" };
  if (result === "loss") return { emoji: "✗", color: "text-red-500", bg: "bg-red-500/10" };
  return { emoji: "=", color: "text-yellow-500", bg: "bg-yellow-500/10" };
};

const CoachHome = ({ user }) => {
  const navigate = useNavigate();
  
  // State
  const [loading, setLoading] = useState(true);
  const [homeData, setHomeData] = useState(null);
  const [mission, setMission] = useState(null);
  const [freshLoss, setFreshLoss] = useState(null);
  const [starting, setStarting] = useState(false);
  const [coachState, setCoachState] = useState(null);
  const [showDeepSession, setShowDeepSession] = useState(false);

  useEffect(() => {
    fetchAllData();
  }, []);

  const fetchAllData = async () => {
    try {
      setLoading(true);
      
      const [homeRes, missionRes, lossRes, coachStateRes] = await Promise.all([
        fetch(`${API}/coach/home-intelligence`, { credentials: "include" }),
        fetch(`${API}/missions/today`, { credentials: "include" }),
        fetch(`${API}/coach/fresh-loss`, { credentials: "include" }).catch(() => null),
        fetch(`${API}/coach/state`, { credentials: "include" }).catch(() => null),
      ]);
      
      if (homeRes.ok) {
        setHomeData(await homeRes.json());
      }
      
      if (missionRes.ok) {
        setMission(await missionRes.json());
      }
      
      if (lossRes?.ok) {
        const lossData = await lossRes.json();
        if (lossData?.has_fresh_loss) {
          setFreshLoss(lossData);
        }
      }
      
      if (coachStateRes?.ok) {
        setCoachState(await coachStateRes.json());
      }
    } catch (err) {
      console.error("Error fetching home data:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleStartMission = async () => {
    if (!mission?.mission_id) return;
    
    setStarting(true);
    try {
      const res = await fetch(`${API}/missions/${mission.mission_id}/start`, {
        method: "POST",
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        navigate(`/mission/${mission.mission_id}`, {
          state: { session_id: data.session_id, mission }
        });
      }
    } catch (err) {
      console.error("Failed to start mission:", err);
    } finally {
      setStarting(false);
    }
  };

  // Get greeting based on time
  // Get contextual, coach-like greeting
  const getGreeting = () => {
    const hour = new Date().getHours();
    const hasRecentGames = gamesNeedingReflection?.length > 0;
    const daysSinceLastGame = lastGame?.date 
      ? Math.floor((Date.now() - new Date(lastGame.date)) / (1000 * 60 * 60 * 24))
      : 999;
    
    // Time-based base greeting
    let baseGreeting = "Good evening";
    if (hour < 12) baseGreeting = "Good morning";
    else if (hour < 17) baseGreeting = "Good afternoon";
    
    // Add coach context
    if (daysSinceLastGame > 3) {
      return "Welcome back";
    }
    if (hasRecentGames && hour < 12) {
      return "Ready to learn";
    }
    if (lastGame?.result === "win") {
      return "Nice work yesterday";
    }
    
    return baseGreeting;
  };
  
  // Get coach message based on context
  const getCoachMessage = () => {
    const hasRecentGames = gamesNeedingReflection?.length > 0;
    
    if (hasRecentGames && gamesNeedingReflection.length >= 3) {
      return "You've been busy! Let's look at what we can learn from these games.";
    }
    if (hasRecentGames) {
      return "I've been looking at your recent games. Found some moments worth discussing.";
    }
    if (specificPatterns?.has_pattern) {
      return `I noticed a pattern in your play. Let's work on it together.`;
    }
    if (mission?.mission_id) {
      return "Your training is ready. Let's sharpen those skills.";
    }
    return "Ready when you are. What would you like to work on today?";
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-6 h-6 animate-spin text-primary" />
        </div>
      </Layout>
    );
  }

  const userName = user?.name?.split(" ")[0] || "there";
  const hasData = homeData?.has_data;
  const gamesNeedingReflection = homeData?.games_needing_reflection || [];
  const hasGamesToReflect = gamesNeedingReflection.length > 0;
  const lastGame = homeData?.last_game;
  const focusStage = coachState?.active_theme || homeData?.development_phase?.phase_name;
  const focusAdvice = homeData?.active_advice;
  
  // V2 Data - Specific patterns, progress trends, session continuity
  const specificPatterns = homeData?.specific_patterns;
  const progressTrend = homeData?.progress_trend;
  const lastSession = homeData?.last_session;
  
  // P1-3: Win streak & mood override
  const winStreak = homeData?.win_streak;
  const moodOverride = homeData?.mood_override;
  const momentumOverride = homeData?.development_phase?.momentum_override;
  
  // Determine the primary state
  const getPrimaryState = () => {
    if (hasGamesToReflect) return "REFLECT";
    if (mission?.mission_id) return "TRAIN";
    if (!hasData) return "NO_GAMES";
    return "TRAIN";
  };
  
  const primaryState = getPrimaryState();

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto space-y-4 pb-8" data-testid="coach-home">
        
        {/* Deep Session Banner - Shows when coaching review is due */}
        <DeepSessionBanner onStartSession={() => setShowDeepSession(true)} />
        
        {/* P1-3: Win Streak Momentum Banner */}
        {moodOverride?.type === "positive_momentum" && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 flex items-center gap-3"
            data-testid="win-streak-banner"
          >
            <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
              <Trophy className="w-5 h-5 text-emerald-500" />
            </div>
            <div>
              <p className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">
                {moodOverride.streak}-Game Win Streak
              </p>
              <p className="text-xs text-muted-foreground">
                {moodOverride.message}
              </p>
            </div>
          </motion.div>
        )}
        
        {/* ============================================ */}
        {/* HERO SECTION - Personal Coaching Greeting   */}
        {/* ============================================ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border bg-gradient-to-br from-card to-card/50 p-5"
          data-testid="hero-section"
        >
          {/* Greeting with context */}
          <div className="flex items-start justify-between mb-3">
            <div>
              <h1 className="text-xl font-semibold mb-1">
                {getGreeting()}, {userName}
              </h1>
              {/* Coach message - the human touch */}
              <p className="text-sm text-muted-foreground">
                {getCoachMessage()}
              </p>
            </div>
            {hasData && (
              <Badge variant="outline" className="text-xs">
                {homeData?.games_analyzed || 0} games analyzed
              </Badge>
            )}
          </div>
          
          {/* Focus area indicator */}
          {focusStage && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-4 pl-0.5">
              {momentumOverride ? (
                <>
                  <TrendingUp className="w-4 h-4 text-emerald-500" />
                  <span>Current vibe: <span className="text-emerald-500 font-medium">{momentumOverride.name}</span></span>
                </>
              ) : (
                <>
                  <Target className="w-4 h-4 text-primary" />
                  <span>This week's focus: <span className="text-primary font-medium">{focusStage.replace(/([A-Z])/g, ' $1').trim()}</span></span>
                </>
              )}
            </div>
          )}
          
          {/* State-based hero content */}
          {primaryState === "REFLECT" && (
            <div className="space-y-3">
              {/* Specific Pattern Insight from API - the key "95/100" improvement */}
              {specificPatterns?.has_pattern && !moodOverride?.suppress_negative && (
                <div className="flex items-start gap-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20">
                  <AlertCircle className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-amber-600 dark:text-amber-400">
                      {specificPatterns.pattern_count}x {specificPatterns.pattern_description.toLowerCase()} this week
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      This is your main leak. Let's fix it.
                    </p>
                  </div>
                </div>
              )}
              
              {/* Progress Trend - shows improvement or decline */}
              {progressTrend?.has_trend && (
                <div className={`flex items-center gap-2 text-sm ${
                  progressTrend.trend === "improving" ? "text-green-600 dark:text-green-400" :
                  progressTrend.trend === "declining" ? "text-red-500" : "text-muted-foreground"
                }`}>
                  {progressTrend.trend === "improving" && <TrendingUp className="w-4 h-4" />}
                  {progressTrend.trend === "declining" && <AlertCircle className="w-4 h-4" />}
                  {progressTrend.trend === "stable" && <CheckCircle2 className="w-4 h-4" />}
                  <span>{progressTrend.message}</span>
                </div>
              )}
              
              {/* Session Continuity - what we worked on last time */}
              {lastSession?.has_session && lastSession.games_on_theme > 0 && (
                <p className="text-sm text-muted-foreground italic">
                  {lastSession.message}
                </p>
              )}
              
              {/* Fallback if no specific pattern data - use game count */}
              {!specificPatterns?.has_pattern && (
                <p className="text-sm text-muted-foreground">
                  {gamesNeedingReflection.length >= 3 
                    ? "A few games to catch up on. Reflection is where real learning happens."
                    : "Let's review your recent play."}
                </p>
              )}
              
              <p className="text-sm">
                <span className="text-primary font-medium">{gamesNeedingReflection.length} game{gamesNeedingReflection.length !== 1 ? 's' : ''}</span>
                {" "}waiting for reflection.
              </p>
            </div>
          )}
          
          {primaryState === "TRAIN" && (
            <div className="space-y-3">
              {gamesNeedingReflection.length === 0 && hasData && (
                <div className="flex items-center gap-2 p-2 rounded-lg bg-green-500/10 border border-green-500/20">
                  <CheckCircle2 className="w-4 h-4 text-green-500" />
                  <span className="text-sm text-green-600 dark:text-green-400">
                    All caught up! You've reflected on your recent games.
                  </span>
                </div>
              )}
              
              {/* Progress Trend in TRAIN mode too */}
              {progressTrend?.has_trend && progressTrend.trend === "improving" && (
                <div className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
                  <TrendingUp className="w-4 h-4" />
                  <span>{progressTrend.message}</span>
                </div>
              )}
              
              {/* Session Continuity */}
              {lastSession?.has_session && lastSession.games_on_theme > 0 && (
                <p className="text-sm text-muted-foreground italic">
                  {lastSession.message}
                </p>
              )}
              
              <p className="text-sm text-muted-foreground">
                Time to train. Today's focus: <span className="text-foreground font-medium">{focusStage || "Tactical awareness"}</span>
              </p>
            </div>
          )}
          
          {primaryState === "NO_GAMES" && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                I haven't seen any games yet. Play some games on Lichess/Chess.com, 
                then import them so we can start learning together.
              </p>
            </div>
          )}
        </motion.div>
        
        {/* ============================================ */}
        {/* PRIMARY ACTION - Based on State             */}
        {/* ============================================ */}
        
        {/* State: REFLECT - Games needing reflection */}
        {primaryState === "REFLECT" && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="space-y-3"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
                Games to Reflect
              </h2>
              <Badge variant="secondary" className="bg-amber-500/10 text-amber-600 dark:text-amber-400">
                {gamesNeedingReflection.length} waiting
              </Badge>
            </div>
            
            <div className="space-y-2">
              {gamesNeedingReflection.slice(0, 3).map((game, index) => {
                const style = getResultStyle(game.result);
                const blunders = game.blunders || 0;
                const accuracy = game.accuracy;
                const isWin = game.result === "win";
                
                // Individual game insight - more specific and celebratory for wins
                let gameInsight = "";
                if (isWin && blunders === 0) {
                  gameInsight = "Clean win! Let's see what worked.";
                } else if (isWin && blunders > 0) {
                  gameInsight = `Won but ${blunders} close call${blunders !== 1 ? 's' : ''}.`;
                } else if (game.result === "loss" && blunders >= 2) {
                  gameInsight = `${blunders} blunder${blunders !== 1 ? 's' : ''} to understand`;
                } else if (game.result === "loss" && blunders === 1) {
                  gameInsight = "1 critical moment to study";
                } else if (accuracy && accuracy < 60) {
                  gameInsight = `${accuracy}% accuracy - room to grow`;
                } else {
                  gameInsight = `${game.moments_count || game.critical_moments_count || 0} moment${(game.moments_count || game.critical_moments_count || 0) !== 1 ? 's' : ''} to review`;
                }
                
                return (
                  <motion.button
                    key={game.game_id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.1 + index * 0.05 }}
                    onClick={() => navigate(`/reflect?game=${game.game_id}`)}
                    className={`w-full p-3 rounded-xl border bg-card hover:bg-accent/50 transition-colors text-left group ${
                      isWin ? "border-green-500/30 bg-green-500/5" : ""
                    }`}
                    data-testid={`reflect-game-${index}`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${style.bg}`}>
                        {isWin && blunders === 0 ? (
                          <Trophy className="w-5 h-5 text-green-500" />
                        ) : (
                          <span className={`text-lg font-bold ${style.color}`}>{style.emoji}</span>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium truncate">vs {game.opponent_name || game.opponent || "Opponent"}</span>
                          <span className="text-xs text-muted-foreground">{getTimeSince(game.date || game.analyzed_at)}</span>
                        </div>
                        <p className={`text-xs truncate ${isWin && blunders === 0 ? "text-green-600 dark:text-green-400" : "text-muted-foreground"}`}>
                          {gameInsight}
                        </p>
                      </div>
                      <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
                    </div>
                  </motion.button>
                );
              })}
              
              {gamesNeedingReflection.length > 3 && (
                <p className="text-xs text-center text-muted-foreground pt-1">
                  +{gamesNeedingReflection.length - 3} more game{gamesNeedingReflection.length - 3 !== 1 ? 's' : ''}
                </p>
              )}
            </div>
          </motion.div>
        )}
        
        {/* State: TRAIN - Today's Mission */}
        {primaryState === "TRAIN" && mission?.mission_id && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
                Today's Training
              </h2>
            </div>
            
            <div 
              className="p-4 rounded-xl border bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20 cursor-pointer hover:border-primary/40 transition-colors"
              onClick={handleStartMission}
              data-testid="mission-card"
            >
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center">
                  <Brain className="w-6 h-6 text-primary" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold mb-1">{mission.name || "Training Mission"}</h3>
                  <p className="text-sm text-muted-foreground mb-3">{mission.description || "Practice your focus area"}</p>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {mission.estimated_time || "7 min"}
                    </span>
                    <span className="flex items-center gap-1">
                      <Target className="w-3 h-3" />
                      {mission.position_count || 5} positions
                    </span>
                  </div>
                </div>
                <Button size="sm" disabled={starting}>
                  {starting ? <Loader2 className="w-4 h-4 animate-spin" /> : "Start"}
                </Button>
              </div>
            </div>
          </motion.div>
        )}
        
        {/* State: NO_GAMES - Import prompt */}
        {primaryState === "NO_GAMES" && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <Button 
              className="w-full h-14 text-base"
              onClick={() => navigate("/import")}
              data-testid="import-games-btn"
            >
              <Gamepad2 className="w-5 h-5 mr-2" />
              Import Your Games
            </Button>
            <p className="text-xs text-center text-muted-foreground mt-2">
              Connect your Lichess or Chess.com account to get started
            </p>
          </motion.div>
        )}
        
        {/* ============================================ */}
        {/* YOUR FOCUS - The ONE thing to work on       */}
        {/* ============================================ */}
        {focusAdvice && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="p-4 rounded-xl border bg-gradient-to-br from-amber-500/5 to-amber-500/10 border-amber-500/20"
            data-testid="focus-advice-card"
          >
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                <Sparkles className="w-5 h-5 text-amber-500" />
              </div>
              <div className="flex-1">
                <h3 className="text-xs font-medium text-amber-600 dark:text-amber-400 uppercase tracking-wide mb-1">
                  Your Focus
                </h3>
                <p className="text-sm font-medium">
                  {focusAdvice.advice || focusAdvice.message || "Before each move, check what your opponent is threatening."}
                </p>
              </div>
            </div>
            
            {/* Start Training button - auto-routes to prescribed training */}
            {specificPatterns?.dominant_pattern && (
              <Button 
                className="w-full mt-3 bg-amber-500 hover:bg-amber-600 text-black"
                onClick={() => navigate(`/training/prescribed?weakness=${specificPatterns.dominant_pattern}`)}
                data-testid="start-training-btn"
              >
                <Target className="w-4 h-4 mr-2" />
                Start Training ({specificPatterns.pattern_count} {specificPatterns.dominant_pattern.replace(/_/g, " ")}s to fix)
              </Button>
            )}
          </motion.div>
        )}
        
        {/* ============================================ */}
        {/* PLAY WITH COACH - Training mode             */}
        {/* ============================================ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="p-4 rounded-xl border bg-card hover:bg-accent/30 cursor-pointer transition-colors"
          onClick={() => navigate("/play-with-coach")}
          data-testid="play-with-coach-card"
        >
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
              <MessageCircle className="w-6 h-6 text-primary" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold">Play with Coach</h3>
                <Badge variant="secondary" className="text-xs bg-primary/10 text-primary">NEW</Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                Practice with real-time guidance
              </p>
            </div>
            <ChevronRight className="w-5 h-5 text-muted-foreground" />
          </div>
        </motion.div>
        
        {/* ============================================ */}
        {/* PROGRESS SECTION - Skill tracking           */}
        {/* ============================================ */}
        {hasData && coachState?.skill_progress && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="p-4 rounded-xl border bg-card"
            data-testid="progress-section"
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
                {focusStage || "Skill"} Progress
              </h3>
              <span className="text-sm font-medium text-primary">
                {coachState.skill_progress.percentage || 0}%
              </span>
            </div>
            <Progress value={coachState.skill_progress.percentage || 0} className="h-2 mb-2" />
            <p className="text-xs text-muted-foreground">
              {coachState.skill_progress.games_completed || 0} of {coachState.skill_progress.games_required || 10} games to master this skill
            </p>
          </motion.div>
        )}
        
        {/* ============================================ */}
        {/* QUICK ACTIONS                               */}
        {/* ============================================ */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="grid grid-cols-3 gap-2"
        >
          <button
            onClick={() => navigate("/coach")}
            className="p-3 rounded-xl border bg-card hover:bg-accent/50 transition-colors text-center"
            data-testid="puzzles-action"
          >
            <Target className="w-5 h-5 mx-auto mb-1 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">Puzzles</span>
          </button>
          <button
            onClick={() => navigate("/progress")}
            className="p-3 rounded-xl border bg-card hover:bg-accent/50 transition-colors text-center"
            data-testid="progress-action"
          >
            <TrendingUp className="w-5 h-5 mx-auto mb-1 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">Progress</span>
          </button>
          <button
            onClick={() => navigate("/analyze")}
            className="p-3 rounded-xl border bg-card hover:bg-accent/50 transition-colors text-center"
            data-testid="analyze-action"
          >
            <Brain className="w-5 h-5 mx-auto mb-1 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">Analyze</span>
          </button>
        </motion.div>
        
      </div>
      
      {/* Deep Session Modal */}
      {showDeepSession && (
        <DeepSessionModal onClose={() => setShowDeepSession(false)} />
      )}
    </Layout>
  );
};

export default CoachHome;
