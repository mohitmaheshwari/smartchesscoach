import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import {
  Target,
  Clock,
  ChevronRight,
  Play,
  Loader2,
  AlertTriangle,
  Wrench,
  Trophy,
  TrendingUp,
  TrendingDown,
  Minus,
  Flame,
  ChevronDown,
  ChevronUp,
  Gamepad2,
  Import,
  Brain,
  CheckCircle2,
  XCircle,
  MinusCircle,
  Lightbulb,
  Swords,
} from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * CoachHome - The paradigm shift: Action-first, not dashboard-first.
 * 
 * UX Promise: "From loss to learning in under 90 seconds."
 * 
 * Layout:
 * - Above fold: ONE primary action (Post-Loss Rescue OR Today's Mission)
 * - Below fold: Weekly Proof, Continue Session, Recent Games
 */
const CoachHome = ({ user }) => {
  const navigate = useNavigate();
  
  // State
  const [loading, setLoading] = useState(true);
  const [mission, setMission] = useState(null);
  const [freshLoss, setFreshLoss] = useState(null);
  const [weeklyProof, setWeeklyProof] = useState(null);
  const [recentGames, setRecentGames] = useState([]);
  const [showRecentGames, setShowRecentGames] = useState(false);
  const [starting, setStarting] = useState(false);
  
  // Adaptive Coach data
  const [coachData, setCoachData] = useState(null);
  const [showPlanDetails, setShowPlanDetails] = useState(false);

  useEffect(() => {
    fetchCoachData();
  }, []);

  const fetchCoachData = async () => {
    try {
      setLoading(true);
      
      // Fetch in parallel
      const [missionRes, lossRes, proofRes, gamesRes, adaptiveRes] = await Promise.all([
        fetch(`${API}/missions/today`, { credentials: "include" }),
        fetch(`${API}/coach/fresh-loss`, { credentials: "include" }).catch(() => null),
        fetch(`${API}/coach/weekly-proof`, { credentials: "include" }).catch(() => null),
        fetch(`${API}/games?limit=5`, { credentials: "include" }).catch(() => null),
        fetch(`${API}/adaptive-coach`, { credentials: "include" }).catch(() => null),
      ]);
      
      if (missionRes.ok) {
        setMission(await missionRes.json());
      }
      
      if (lossRes?.ok) {
        const lossData = await lossRes.json();
        if (lossData?.has_fresh_loss) {
          setFreshLoss(lossData);
        }
      }
      
      if (proofRes?.ok) {
        setWeeklyProof(await proofRes.json());
      }
      
      if (gamesRes?.ok) {
        const gamesData = await gamesRes.json();
        setRecentGames(gamesData.games || []);
      }
      
      if (adaptiveRes?.ok) {
        setCoachData(await adaptiveRes.json());
      }
    } catch (err) {
      console.error("Error fetching coach data:", err);
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

  const handleStartRecovery = () => {
    if (freshLoss?.game_id) {
      navigate(`/recover/${freshLoss.game_id}`);
    }
  };

  // Greeting based on time
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 17) return "Good afternoon";
    return "Good evening";
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

  const hasFreshLoss = freshLoss?.has_fresh_loss;
  const userName = user?.name?.split(" ")[0] || "Player";

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto space-y-8" data-testid="coach-home">
        {/* Greeting - subtle, not dominant */}
        <motion.p 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-sm text-muted-foreground"
        >
          {getGreeting()}, {userName}
        </motion.p>

        {/* ========== PRIMARY ACTION CARD (Above Fold) ========== */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          {hasFreshLoss ? (
            /* Post-Loss Recovery Card - HIGHEST PRIORITY */
            <PostLossRecoveryHero 
              loss={freshLoss} 
              onStart={handleStartRecovery}
            />
          ) : mission ? (
            /* Today's Mission Card */
            <TodaysMissionHero 
              mission={mission}
              onStart={handleStartMission}
              starting={starting}
            />
          ) : (
            /* No mission - prompt to play/import */
            <NoMissionCard onImport={() => navigate("/import")} />
          )}
        </motion.div>

        {/* ========== SECONDARY SECTION (Below Fold) ========== */}
        <div className="space-y-4">
          {/* Adaptive Coach - Game Analysis & Plan */}
          {coachData && !coachData.needs_more_games && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 }}
            >
              <AdaptiveCoachCard 
                data={coachData}
                expanded={showPlanDetails}
                onToggle={() => setShowPlanDetails(!showPlanDetails)}
                onViewGame={(gameId) => navigate(`/game/${gameId}`)}
              />
            </motion.div>
          )}
          
          {/* Weekly Proof - compact */}
          {weeklyProof && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <WeeklyProofCard proof={weeklyProof} />
            </motion.div>
          )}

          {/* Recent Games - collapsed by default */}
          {recentGames.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
            >
              <RecentGamesCollapsed 
                games={recentGames}
                expanded={showRecentGames}
                onToggle={() => setShowRecentGames(!showRecentGames)}
                onSelectGame={(id) => navigate(`/game/${id}`)}
              />
            </motion.div>
          )}

          {/* Quick actions row */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="flex gap-3"
          >
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate("/import")}
              className="flex-1 text-muted-foreground"
              data-testid="quick-import"
            >
              <Import className="w-4 h-4 mr-2" />
              Import Games
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate("/progress")}
              className="flex-1 text-muted-foreground"
              data-testid="quick-progress"
            >
              <TrendingUp className="w-4 h-4 mr-2" />
              View Progress
            </Button>
          </motion.div>
        </div>
      </div>
    </Layout>
  );
};

/* ========== SUB-COMPONENTS ========== */

/**
 * Post-Loss Recovery Hero - The signature UX pattern
 * Emotional headline + Single insight + Single CTA
 */
const PostLossRecoveryHero = ({ loss, onStart }) => {
  const minutes = loss?.estimated_minutes || 6;
  const focus = loss?.focus_label || "Critical moment";
  
  return (
    <div 
      className="relative overflow-hidden rounded-xl border-l-4 border-l-[#EF4444] bg-card p-6"
      data-testid="post-loss-hero"
    >
      {/* Subtle gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-red-500/5 via-transparent to-transparent pointer-events-none" />
      
      <div className="relative space-y-4">
        {/* Badge */}
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-[#EF4444]" />
          <span className="text-xs font-semibold text-[#EF4444] uppercase tracking-wide">
            Fresh Loss
          </span>
        </div>
        
        {/* Headline - Emotional, Direct */}
        <h1 className="text-2xl font-bold tracking-tight">
          Tough game. Don't waste it.
        </h1>
        
        {/* Single Insight */}
        <div className="flex items-center gap-3 p-3 rounded-lg bg-secondary/50">
          <Wrench className="w-5 h-5 text-muted-foreground" />
          <div>
            <p className="text-xs text-muted-foreground">Main issue</p>
            <p className="text-sm font-medium">{focus}</p>
          </div>
        </div>
        
        {/* Single CTA */}
        <Button 
          onClick={onStart}
          size="lg"
          className="w-full bg-[#EF4444] hover:bg-[#DC2626] text-white font-semibold"
          data-testid="start-recovery-btn"
        >
          Fix this in {minutes} min
          <ChevronRight className="w-5 h-5 ml-2" />
        </Button>
        
        {/* Secondary option - subtle */}
        <button 
          className="w-full text-center text-xs text-muted-foreground hover:text-foreground transition-colors"
          onClick={() => {/* Navigate to full analysis */}}
        >
          See full analysis instead →
        </button>
      </div>
    </div>
  );
};

/**
 * Today's Mission Hero - Primary action when no fresh loss
 */
const TodaysMissionHero = ({ mission, onStart, starting }) => {
  const minutes = mission?.estimated_minutes || 7;
  const focus = mission?.focus_label || "Critical Position Focus";
  const protocol = mission?.micro_protocol || [];
  const goal = mission?.goal?.target || 5;
  const isActive = mission?.status === "active";
  
  return (
    <div 
      className="relative overflow-hidden rounded-xl border-l-4 border-l-primary bg-card p-6"
      data-testid="mission-hero"
    >
      {/* Subtle gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-transparent pointer-events-none" />
      
      <div className="relative space-y-4">
        {/* Badge */}
        <div className="flex items-center gap-2">
          <Target className="w-4 h-4 text-primary" />
          <span className="text-xs font-semibold text-primary uppercase tracking-wide">
            {isActive ? "Continue Mission" : "Today's Mission"}
          </span>
          {mission?.streak_count > 0 && (
            <span className="flex items-center gap-1 text-xs text-[#F59E0B] ml-auto">
              <Flame className="w-3.5 h-3.5" />
              {mission.streak_count} day streak
            </span>
          )}
        </div>
        
        {/* Focus Label - The main message */}
        <h1 className="text-2xl font-bold tracking-tight">
          {focus}
        </h1>
        
        {/* Protocol Preview */}
        {protocol.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground uppercase tracking-wide">Before each move</p>
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
        
        {/* Meta - Duration & Goal */}
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
        
        {/* Single CTA */}
        <Button 
          onClick={onStart}
          disabled={starting}
          size="lg"
          className="w-full font-semibold"
          data-testid="start-mission-btn"
        >
          {starting ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : isActive ? (
            <>
              Continue
              <Play className="w-5 h-5 ml-2" />
            </>
          ) : (
            <>
              Start Mission
              <ChevronRight className="w-5 h-5 ml-2" />
            </>
          )}
        </Button>
      </div>
    </div>
  );
};

/**
 * No Mission Card - When user has no games/mission
 */
const NoMissionCard = ({ onImport }) => (
  <div 
    className="rounded-xl border border-dashed border-border bg-card/50 p-8 text-center"
    data-testid="no-mission-card"
  >
    <Gamepad2 className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
    <h2 className="text-lg font-semibold mb-2">No mission yet</h2>
    <p className="text-sm text-muted-foreground mb-4">
      Import a game and we'll create a personalized mission based on your patterns.
    </p>
    <Button onClick={onImport} data-testid="import-first-game">
      <Import className="w-4 h-4 mr-2" />
      Import Your First Game
    </Button>
  </div>
);

/**
 * Weekly Proof Card - Compact progress indicator
 */
const WeeklyProofCard = ({ proof }) => {
  const wins = proof?.wins || 0;
  const leakReduced = proof?.leak_reduced || null;
  const streakDays = proof?.streak_days || 0;
  
  return (
    <div className="rounded-lg bg-card border border-border p-4" data-testid="weekly-proof">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-[#10B981]/10 flex items-center justify-center">
            <Trophy className="w-5 h-5 text-[#10B981]" />
          </div>
          <div>
            <p className="text-xs text-muted-foreground">This week</p>
            <p className="text-sm font-medium">
              {wins > 0 && `${wins} win${wins > 1 ? 's' : ''}`}
              {wins > 0 && leakReduced && ' · '}
              {leakReduced && `${leakReduced} improving`}
              {!wins && !leakReduced && 'Keep playing'}
            </p>
          </div>
        </div>
        
        {streakDays > 0 && (
          <div className="flex items-center gap-1 text-[#F59E0B]">
            <Flame className="w-4 h-4" />
            <span className="text-sm font-medium">{streakDays}</span>
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * Recent Games - Collapsed by default, expandable
 */
const RecentGamesCollapsed = ({ games, expanded, onToggle, onSelectGame }) => {
  return (
    <div className="rounded-lg bg-card border border-border overflow-hidden" data-testid="recent-games">
      {/* Header - always visible */}
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 hover:bg-secondary/30 transition-colors"
      >
        <span className="text-sm font-medium text-muted-foreground">
          Recent Games ({games.length})
        </span>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        )}
      </button>
      
      {/* Expandable list */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-t border-border"
          >
            {games.map((game, idx) => (
              <button
                key={game.game_id || idx}
                onClick={() => onSelectGame(game.game_id)}
                className="w-full flex items-center justify-between p-3 hover:bg-secondary/30 transition-colors text-left border-b border-border last:border-0"
              >
                <div className="flex items-center gap-3">
                  {/* Result indicator */}
                  <div className={`w-2 h-2 rounded-full ${
                    game.result === 'win' ? 'bg-[#10B981]' : 
                    game.result === 'loss' ? 'bg-[#EF4444]' : 
                    'bg-muted-foreground'
                  }`} />
                  <div>
                    <p className="text-sm font-medium">vs {game.opponent || 'Opponent'}</p>
                    <p className="text-xs text-muted-foreground">
                      {game.time_control || 'Rapid'} · {game.opening_name?.split(':')[0] || 'Unknown opening'}
                    </p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-muted-foreground" />
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

/**
 * Adaptive Coach Card - Rich game analysis and personalized plan
 */
const AdaptiveCoachCard = ({ data, expanded, onToggle, onViewGame }) => {
  const [richAudit, setRichAudit] = useState(null);
  const [loadingAudit, setLoadingAudit] = useState(false);
  
  // Fetch rich audit when expanded
  useEffect(() => {
    if (expanded && !richAudit && !loadingAudit) {
      fetchRichAudit();
    }
  }, [expanded]);
  
  const fetchRichAudit = async () => {
    setLoadingAudit(true);
    try {
      const res = await fetch(`${API}/coach/rich-audit-latest`, { credentials: "include" });
      if (res.ok) {
        setRichAudit(await res.json());
      }
    } catch (err) {
      console.error("Error fetching rich audit:", err);
    } finally {
      setLoadingAudit(false);
    }
  };
  
  const { diagnosis, plan_audit, next_game_plan, skill_signals } = data || {};
  
  const getStatusIcon = (status) => {
    if (status === "executed" || status === "better") return <CheckCircle2 className="w-4 h-4 text-emerald-500" />;
    if (status === "partial") return <MinusCircle className="w-4 h-4 text-amber-500" />;
    if (status === "missed" || status === "worse") return <XCircle className="w-4 h-4 text-red-500" />;
    return <Minus className="w-4 h-4 text-muted-foreground" />;
  };
  
  const getStatusColor = (status) => {
    if (status === "executed" || status === "better") return "border-emerald-500/30 bg-emerald-500/5";
    if (status === "partial") return "border-amber-500/30 bg-amber-500/5";
    if (status === "missed" || status === "worse") return "border-red-500/30 bg-red-500/5";
    return "border-border bg-muted/30";
  };
  
  const getTrendIcon = (trend) => {
    if (trend === "improving" || trend === "better") return <TrendingUp className="w-3 h-3 text-emerald-500" />;
    if (trend === "declining" || trend === "worse") return <TrendingDown className="w-3 h-3 text-red-500" />;
    return <Minus className="w-3 h-3 text-muted-foreground" />;
  };
  
  // Use rich audit if available
  const audit = richAudit;
  const gameSummary = audit?.game_summary;
  const baseline = audit?.performance_vs_baseline;
  const recurring = audit?.recurring_patterns || [];
  const improvements = audit?.improvements || [];
  const concerns = audit?.concerns || [];
  const coachNarrative = audit?.coach_narrative;
  const targetedPlan = audit?.next_game_plan;
  
  // Fallback to basic audit data
  const auditCards = plan_audit?.audit_cards || [];
  const executed = auditCards.filter(c => c.status === "executed").length;
  const total = auditCards.filter(c => c.status !== "n/a").length;
  
  const overallGood = audit ? baseline?.overall === "better" : (executed >= total / 2 && total > 0);
  
  return (
    <div className="rounded-lg bg-card border border-border overflow-hidden" data-testid="adaptive-coach">
      {/* Header */}
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 hover:bg-secondary/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
            overallGood ? 'bg-emerald-500/10' : 'bg-amber-500/10'
          }`}>
            <Brain className={`w-5 h-5 ${overallGood ? 'text-emerald-500' : 'text-amber-500'}`} />
          </div>
          <div className="text-left">
            <p className="text-sm font-medium">
              {gameSummary ? `Last game: ${gameSummary.outcome} vs ${gameSummary.opponent}` : 
               overallGood ? "Good progress on your plan" : "Room for improvement"}
            </p>
            <p className="text-xs text-muted-foreground">
              {baseline?.has_baseline ? 
                (baseline.overall === "better" ? "Better than your average" : 
                 baseline.overall === "worse" ? "Below your average" : "Typical performance") :
                `${executed}/${total} goals executed`}
            </p>
          </div>
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        )}
      </button>
      
      {/* Expanded content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-t border-border"
          >
            {loadingAudit ? (
              <div className="p-8 flex items-center justify-center">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : audit?.has_audit ? (
              <>
                {/* Coach Narrative */}
                {coachNarrative && (
                  <div className="p-4 border-b border-border">
                    <div className="p-4 rounded-lg bg-gradient-to-r from-primary/10 to-purple-500/10 border border-primary/30">
                      <div className="flex items-start gap-3">
                        <Brain className="w-5 h-5 text-primary shrink-0 mt-0.5" />
                        <p className="text-sm leading-relaxed">{coachNarrative}</p>
                      </div>
                    </div>
                  </div>
                )}
                
                {/* Game Summary */}
                {gameSummary && (
                  <div className="p-4 border-b border-border space-y-3">
                    <div className="flex items-center gap-2">
                      <Swords className="w-4 h-4 text-muted-foreground" />
                      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        Game Analysis
                      </span>
                    </div>
                    
                    <div className="grid grid-cols-3 gap-3 text-center">
                      <div className="p-2 rounded-lg bg-muted/30">
                        <div className={`text-xl font-bold ${
                          gameSummary.blunders === 0 ? 'text-emerald-500' : 'text-red-500'
                        }`}>{gameSummary.blunders}</div>
                        <div className="text-xs text-muted-foreground">Blunders</div>
                      </div>
                      <div className="p-2 rounded-lg bg-muted/30">
                        <div className="text-xl font-bold text-amber-500">{gameSummary.mistakes}</div>
                        <div className="text-xs text-muted-foreground">Mistakes</div>
                      </div>
                      <div className="p-2 rounded-lg bg-muted/30">
                        <div className="text-xl font-bold">{gameSummary.avg_cp_loss}</div>
                        <div className="text-xs text-muted-foreground">Avg CP Loss</div>
                      </div>
                    </div>
                    
                    {/* Turning point */}
                    {gameSummary.turning_point && gameSummary.turning_point.cp_loss >= 100 && (
                      <div 
                        className="p-3 rounded-lg bg-red-500/5 border border-red-500/20 cursor-pointer hover:bg-red-500/10"
                        onClick={() => onViewGame?.(audit.game_id)}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-xs text-red-400 mb-1">Key moment: Move {gameSummary.turning_point.move_number}</p>
                            <p className="text-sm font-medium">{gameSummary.turning_point.move} lost {gameSummary.turning_point.cp_loss} centipawns</p>
                          </div>
                          <ChevronRight className="w-4 h-4 text-red-400" />
                        </div>
                      </div>
                    )}
                  </div>
                )}
                
                {/* Performance vs Baseline */}
                {baseline?.has_baseline && baseline.comparisons?.length > 0 && (
                  <div className="p-4 border-b border-border space-y-3">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-muted-foreground" />
                      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        vs Your Average ({baseline.baseline_games} games)
                      </span>
                    </div>
                    
                    <div className="space-y-2">
                      {baseline.comparisons.map((comp, idx) => (
                        <div key={idx} className={`p-3 rounded-lg border ${getStatusColor(comp.status)}`}>
                          <div className="flex items-center gap-2">
                            {getStatusIcon(comp.status)}
                            <span className="text-sm">{comp.message}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Recurring Patterns (Important!) */}
                {recurring.length > 0 && (
                  <div className="p-4 border-b border-border space-y-3">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-500" />
                      <span className="text-xs font-semibold uppercase tracking-wide text-amber-500">
                        Recurring Patterns
                      </span>
                    </div>
                    
                    <div className="space-y-2">
                      {recurring.map((pattern, idx) => (
                        <div key={idx} className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/30">
                          <p className="text-sm font-medium text-amber-400">{pattern.message}</p>
                          <p className="text-xs text-muted-foreground mt-1">{pattern.coach_advice}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Improvements & Concerns */}
                {(improvements.length > 0 || concerns.length > 0) && (
                  <div className="p-4 border-b border-border space-y-3">
                    {improvements.length > 0 && (
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                          <span className="text-xs font-semibold uppercase tracking-wide text-emerald-500">
                            What's Improving
                          </span>
                        </div>
                        {improvements.map((imp, idx) => (
                          <div key={idx} className="p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/30">
                            <p className="text-sm font-medium text-emerald-400">{imp.message}</p>
                            <p className="text-xs text-muted-foreground">{imp.detail}</p>
                          </div>
                        ))}
                      </div>
                    )}
                    
                    {concerns.length > 0 && (
                      <div className="space-y-2 mt-3">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4 text-red-500" />
                          <span className="text-xs font-semibold uppercase tracking-wide text-red-500">
                            Needs Attention
                          </span>
                        </div>
                        {concerns.map((con, idx) => (
                          <div key={idx} className="p-3 rounded-lg bg-red-500/5 border border-red-500/30">
                            <p className="text-sm font-medium text-red-400">{con.message}</p>
                            <p className="text-xs text-muted-foreground">{con.detail}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                
                {/* Next Game Plan */}
                {targetedPlan && (
                  <div className="p-4 space-y-3">
                    <div className="flex items-center gap-2">
                      <Lightbulb className="w-4 h-4 text-primary" />
                      <span className="text-xs font-semibold uppercase tracking-wide text-primary">
                        Your Plan for Next Game
                      </span>
                    </div>
                    
                    {targetedPlan.primary_focus && (
                      <div className="p-3 rounded-lg bg-primary/10 border border-primary/30">
                        <p className="text-xs text-primary mb-1">Primary Focus</p>
                        <p className="text-sm font-medium">{targetedPlan.primary_focus.area}</p>
                        <p className="text-xs text-muted-foreground mt-1">{targetedPlan.primary_focus.action}</p>
                      </div>
                    )}
                    
                    {targetedPlan.before_each_move?.length > 0 && (
                      <div className="p-3 rounded-lg bg-muted/30">
                        <p className="text-xs text-muted-foreground mb-2">Before Each Move</p>
                        <div className="space-y-1">
                          {targetedPlan.before_each_move.map((item, idx) => (
                            <div key={idx} className="flex items-center gap-2 text-sm">
                              <span className="w-5 h-5 rounded-full bg-primary/20 text-primary flex items-center justify-center text-xs">{idx + 1}</span>
                              <span>{item}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    {targetedPlan.situational_rules?.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-xs text-muted-foreground">Situational Rules</p>
                        {targetedPlan.situational_rules.map((rule, idx) => (
                          <div key={idx} className="p-2 rounded bg-muted/20 text-sm">
                            <span className="text-muted-foreground">When:</span> {rule.situation}<br/>
                            <span className="text-primary">→</span> {rule.action}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </>
            ) : (
              /* Fallback to basic audit */
              <>
                {plan_audit?.has_plan && (
                  <div className="p-4 space-y-3">
                    <div className="flex items-center gap-2">
                      <Swords className="w-4 h-4 text-muted-foreground" />
                      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        Last Game vs Your Plan
                      </span>
                    </div>
                    
                    <div className="space-y-2">
                      {auditCards.filter(c => c.status !== "n/a").map((card, idx) => (
                        <div 
                          key={idx}
                          className={`p-3 rounded-lg border ${getStatusColor(card.status)}`}
                        >
                          <div className="flex items-start gap-3">
                            {getStatusIcon(card.status)}
                            <div className="flex-1">
                              <p className="text-sm font-medium">{card.label}</p>
                              <p className="text-xs text-muted-foreground">{card.goal}</p>
                              {card.data_line && (
                                <p className={`text-xs mt-1 ${
                                  card.status === "executed" ? "text-emerald-400" :
                                  card.status === "missed" ? "text-red-400" : "text-amber-400"
                                }`}>{card.data_line}</p>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default CoachHome;
