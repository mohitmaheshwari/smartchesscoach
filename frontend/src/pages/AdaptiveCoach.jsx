import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import CoachBoard from "@/components/CoachBoard";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import {
  Loader2,
  Target,
  Brain,
  ChevronRight,
  Eye,
  Zap,
  Shield,
  Clock,
  Crown,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Minus,
  RefreshCw,
  Flame,
  Play,
  ArrowRight,
} from "lucide-react";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

/**
 * AdaptiveCoach - GM-Style Performance Coach
 * 
 * 3 Connected Sections (No Tabs):
 * 1. Last Game Audit - Did you execute the plan?
 * 2. Next Game Plan - What to focus on next
 * 3. Mission - Gamified goal tracking
 */
const AdaptiveCoach = ({ user }) => {
  const navigate = useNavigate();
  const boardRef = useRef(null);

  // Data states
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [coachData, setCoachData] = useState(null);
  const [focusData, setFocusData] = useState(null);

  // Board state
  const [currentFen, setCurrentFen] = useState(START_FEN);
  const [boardTitle, setBoardTitle] = useState("Interactive Board");

  // Sync status
  const [syncStatus, setSyncStatus] = useState(null);

  // Fetch data
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        
        // Fetch adaptive coach data and focus data (for mission) in parallel
        const [coachRes, focusRes] = await Promise.all([
          fetch(`${API}/adaptive-coach`, { credentials: "include" }),
          fetch(`${API}/focus`, { credentials: "include" })
        ]);

        if (coachRes.ok) {
          const data = await coachRes.json();
          setCoachData(data);
        } else {
          setError("Failed to load coaching data");
        }
        
        if (focusRes.ok) {
          const data = await focusRes.json();
          setFocusData(data);
        }
      } catch (err) {
        console.error("Failed to load coaching data:", err);
        setError("Failed to load coaching data");
        toast.error("Failed to load coaching data");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Sync status polling
  useEffect(() => {
    const fetchSyncStatus = async () => {
      try {
        const response = await fetch(`${API}/sync-status`, { credentials: "include" });
        if (response.ok) {
          const data = await response.json();
          setSyncStatus(data);
        }
      } catch (error) {
        console.error("Error fetching sync status:", error);
      }
    };

    fetchSyncStatus();
    const interval = setInterval(fetchSyncStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  // Handle viewing position on board
  const handleViewPosition = useCallback((fen, title) => {
    if (boardRef.current && fen) {
      boardRef.current.jumpToFen(fen);
      setCurrentFen(fen);
      setBoardTitle(title || "Position");
    }
  }, []);

  // Format time for sync status
  const formatSyncTime = (seconds) => {
    if (!seconds || seconds <= 0) return "0:00";
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // Get domain icon
  const getDomainIcon = (domainId) => {
    const icons = {
      opening: <Play className="w-4 h-4" />,
      middlegame: <Target className="w-4 h-4" />,
      tactical: <Zap className="w-4 h-4" />,
      endgame: <Crown className="w-4 h-4" />,
      time: <Clock className="w-4 h-4" />,
    };
    return icons[domainId] || <Target className="w-4 h-4" />;
  };

  // Get status styling
  const getStatusStyle = (status) => {
    if (status === "executed") return { bg: "bg-emerald-500/10", border: "border-emerald-500/30", text: "text-emerald-400" };
    if (status === "partial") return { bg: "bg-amber-500/10", border: "border-amber-500/30", text: "text-amber-400" };
    if (status === "missed") return { bg: "bg-red-500/10", border: "border-red-500/30", text: "text-red-400" };
    return { bg: "bg-muted/30", border: "border-border/50", text: "text-muted-foreground" };
  };

  // Loading state
  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </Layout>
    );
  }

  // Error state
  if (error) {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto text-center py-12">
          <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-amber-400" />
          <h3 className="text-lg font-medium mb-2">Error Loading Coach</h3>
          <p className="text-muted-foreground">{error}</p>
        </div>
      </Layout>
    );
  }

  // Need more games state
  if (coachData?.needs_more_games) {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto py-12">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <Card className="border-2 border-dashed border-muted-foreground/20">
              <CardContent className="py-12 text-center">
                <Brain className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
                <h3 className="text-lg font-medium mb-2">Building Your Profile</h3>
                <p className="text-muted-foreground mb-6">
                  Analyze {coachData.games_required - coachData.games_analyzed} more games to unlock personalized coaching
                </p>
                <Progress value={(coachData.games_analyzed / coachData.games_required) * 100} className="w-48 mx-auto mb-4" />
                <p className="text-sm text-muted-foreground mb-4">
                  {coachData.games_analyzed}/{coachData.games_required} games analyzed
                </p>
                <Button onClick={() => navigate("/import")}>Import Games</Button>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </Layout>
    );
  }

  const { diagnosis, next_game_plan, plan_audit } = coachData || {};
  const mission = focusData?.mission;

  return (
    <Layout user={user}>
      <div className="max-w-3xl mx-auto px-4 py-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between mb-6"
        >
          <div>
            <h1 className="text-2xl font-bold">Focus</h1>
            <p className="text-sm text-muted-foreground">
              {coachData?.rating_band} • Your personal game plan
            </p>
          </div>

          {syncStatus && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted/50 border border-border/50">
              {syncStatus.is_syncing ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 text-primary animate-spin" />
                  <span className="text-xs text-primary font-medium">Syncing...</span>
                </>
              ) : (
                <>
                  <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                  <span className="text-xs text-muted-foreground">
                    Next sync: <span className="font-mono font-medium text-foreground">{formatSyncTime(syncStatus.next_sync_in_seconds)}</span>
                  </span>
                </>
              )}
            </div>
          )}
        </motion.div>

        {/* Single Column Flowing Layout */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-6"
        >
          
          {/* ============================================ */}
          {/* SECTION 1: LAST GAME AUDIT (with embedded board) */}
          {/* ============================================ */}
          <Card className="border-amber-500/20 overflow-hidden" data-testid="last-game-audit-section">
            <CardContent className="p-5">
              {/* Section Header */}
              <div className="flex items-center gap-3 mb-4">
                <div className="w-8 h-8 rounded-full bg-amber-500/20 flex items-center justify-center">
                  <span className="text-amber-400 font-bold text-sm">1</span>
                </div>
                <div className="flex-1">
                  <h2 className="font-semibold">Last Game Audit</h2>
                  <p className="text-xs text-muted-foreground">Did you execute the plan?</p>
                </div>
                {plan_audit?.score && (
                  <span className="text-lg font-bold text-amber-400">{plan_audit.score}</span>
                )}
              </div>

              {/* Last Game Result */}
              {plan_audit?.last_game && (
                <div className="flex items-center gap-2 mb-4 text-sm">
                  <span className={`font-bold ${
                    plan_audit.last_game.result === "win" ? "text-emerald-400" :
                    plan_audit.last_game.result === "loss" ? "text-red-400" : "text-amber-400"
                  }`}>
                    {plan_audit.last_game.result?.toUpperCase()}
                  </span>
                  <span className="text-muted-foreground">vs {plan_audit.last_game.opponent}</span>
                </div>
              )}

              {/* Embedded Chessboard + Audit Cards Layout */}
              {plan_audit?.has_plan ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Embedded Board */}
                  <div className="order-2 md:order-1">
                    <div className="text-xs text-muted-foreground mb-2">{boardTitle}</div>
                    <CoachBoard
                      ref={boardRef}
                      initialFen={currentFen}
                      userColor="white"
                      drillMode={false}
                      showControls={true}
                    />
                  </div>

                  {/* Audit Cards */}
                  <div className="order-1 md:order-2 space-y-2">
                    {plan_audit.audit_cards?.map((card) => {
                      const style = getStatusStyle(card.status);
                      return (
                        <div
                          key={card.domain_id}
                          className={`p-3 rounded-lg border ${style.bg} ${style.border} cursor-pointer transition-all hover:scale-[1.01]`}
                          data-testid={`audit-card-${card.domain_id}`}
                          onClick={() => card.board_link_fen && handleViewPosition(card.board_link_fen, `${card.label} - Move ${card.move_reference}`)}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              {card.status === "executed" && <CheckCircle2 className={`w-4 h-4 ${style.text}`} />}
                              {card.status === "partial" && <AlertTriangle className={`w-4 h-4 ${style.text}`} />}
                              {card.status === "missed" && <XCircle className={`w-4 h-4 ${style.text}`} />}
                              {card.status === "n/a" && <Minus className={`w-4 h-4 ${style.text}`} />}
                              <span className={`text-sm font-medium ${style.text}`}>{card.label}</span>
                            </div>
                            {card.board_link_fen && (
                              <Eye className="w-4 h-4 text-muted-foreground" />
                            )}
                          </div>
                          {card.data_line && (
                            <p className="text-xs text-muted-foreground mt-1 pl-6">{card.data_line}</p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="py-8 text-center border border-dashed border-border/50 rounded-lg">
                  <Eye className="w-8 h-8 mx-auto mb-2 text-muted-foreground/50" />
                  <p className="text-sm text-muted-foreground">Play a game to see your execution review</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Connector */}
          <div className="flex justify-center">
            <ArrowRight className="w-5 h-5 text-muted-foreground/30 rotate-90" />
          </div>

          {/* ============================================ */}
          {/* SECTION 2: NEXT GAME PLAN */}
          {/* ============================================ */}
          <Card className="border-blue-500/20 overflow-hidden" data-testid="next-game-plan-section">
            <CardContent className="p-5">
              {/* Section Header */}
              <div className="flex items-center gap-3 mb-4">
                <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center">
                  <span className="text-blue-400 font-bold text-sm">2</span>
                </div>
                <div>
                  <h2 className="font-semibold">Next Game Plan</h2>
                  <p className="text-xs text-muted-foreground">Focus on these for your next game</p>
                </div>
              </div>

              {/* Primary Focus Callout */}
              {diagnosis?.primary_leak && (
                <div className="mb-4 p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
                  <div className="flex items-center gap-2 mb-1">
                    <Target className="w-4 h-4 text-blue-400" />
                    <span className="text-sm font-semibold text-blue-400">
                      Primary Focus: {diagnosis.primary_leak.label}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground">{diagnosis.primary_leak.explanation}</p>
                </div>
              )}

              {/* Plan Domains */}
              <div className="space-y-2">
                {next_game_plan?.domains?.map((domain) => (
                  <div
                    key={domain.id}
                    className="flex items-start gap-3 p-3 rounded-lg bg-background/50 border border-border/30 hover:border-blue-500/30 transition-colors"
                    data-testid={`plan-domain-${domain.id}`}
                  >
                    <div className="mt-0.5 text-blue-400">{getDomainIcon(domain.id)}</div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium">{domain.label}</div>
                      <p className="text-xs text-muted-foreground">{domain.goal}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Connector */}
          <div className="flex justify-center">
            <ArrowRight className="w-5 h-5 text-muted-foreground/30 rotate-90" />
          </div>

          {/* ============================================ */}
          {/* SECTION 3: MISSION */}
          {/* ============================================ */}
          <Card className={`overflow-hidden ${
            mission?.status === 'completed' 
              ? 'border-emerald-500/30 bg-gradient-to-br from-emerald-500/5 to-transparent' 
              : 'border-amber-500/30 bg-gradient-to-br from-amber-500/5 to-transparent'
          }`} data-testid="mission-section">
            <CardContent className="p-5">
              {/* Section Header */}
              <div className="flex items-center gap-3 mb-4">
                <div className="w-8 h-8 rounded-full bg-amber-500/20 flex items-center justify-center">
                  <span className="text-amber-400 font-bold text-sm">3</span>
                </div>
                <div className="flex-1">
                  <h2 className="font-semibold">Current Mission</h2>
                  <p className="text-xs text-muted-foreground">Your improvement challenge</p>
                </div>
                
                {/* Streak Counter */}
                {mission && (
                  <div className="flex items-center gap-1">
                    <Flame className={`w-5 h-5 ${mission.current_streak > 0 ? 'text-orange-500' : 'text-muted-foreground'}`} />
                    <span className={`text-2xl font-bold ${mission.status === 'completed' ? 'text-emerald-500' : 'text-amber-500'}`}>
                      {mission.current_streak || mission.progress || 0}
                    </span>
                    <span className="text-muted-foreground">/ {mission.target || 3}</span>
                  </div>
                )}
              </div>

              {/* Mission Content */}
              {mission ? (
                <div>
                  {/* Status Badge */}
                  <div className="flex items-center gap-2 mb-3">
                    <Target className={`w-4 h-4 ${mission.status === 'completed' ? 'text-emerald-500' : 'text-amber-500'}`} />
                    <span className={`text-xs font-bold uppercase tracking-wider ${
                      mission.status === 'completed' ? 'text-emerald-500' : 'text-amber-500'
                    }`}>
                      {mission.status === 'completed' ? 'Mission Complete!' : 'Active Mission'}
                    </span>
                  </div>
                  
                  {/* Mission Name & Goal */}
                  <h3 className="text-lg font-bold mb-1">{mission.name}</h3>
                  <p className="text-sm text-muted-foreground mb-4">{mission.goal}</p>
                  
                  {/* Streak Progress Bar */}
                  {mission.is_streak_based && (
                    <div className="flex items-center gap-1.5 mb-3">
                      {[...Array(mission.target || 3)].map((_, i) => (
                        <div
                          key={i}
                          className={`h-3 flex-1 rounded-full transition-all ${
                            i < (mission.current_streak || 0) 
                              ? mission.status === 'completed' ? 'bg-emerald-500' : 'bg-amber-500' 
                              : 'bg-muted/50'
                          }`}
                        />
                      ))}
                    </div>
                  )}
                  
                  {/* Streak Status Messages */}
                  {mission.streak_broken_in_last_game && (
                    <div className="flex items-center gap-1.5 text-sm text-orange-400">
                      <XCircle className="w-4 h-4" />
                      <span>Streak reset - last game didn't meet the criteria</span>
                    </div>
                  )}
                  {mission.last_game_passed && mission.status !== 'completed' && (
                    <div className="flex items-center gap-1.5 text-sm text-emerald-400">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Last game counted! Keep it up.</span>
                    </div>
                  )}
                  
                  {/* Longest Streak */}
                  {mission.longest_streak > 0 && (
                    <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border/30">
                      <span className="text-sm text-muted-foreground">Personal best:</span>
                      <span className="text-sm font-bold text-amber-500 flex items-center gap-1">
                        <Flame className="w-4 h-4" />
                        {mission.longest_streak} game streak
                      </span>
                    </div>
                  )}
                </div>
              ) : (
                <div className="py-8 text-center border border-dashed border-amber-500/20 rounded-lg">
                  <Flame className="w-8 h-8 mx-auto mb-2 text-muted-foreground/50" />
                  <p className="text-sm text-muted-foreground">Mission will appear after more games</p>
                </div>
              )}
            </CardContent>
          </Card>

        </motion.div>
      </div>
    </Layout>
  );
};

export default AdaptiveCoach;
