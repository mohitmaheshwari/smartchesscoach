import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
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
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronRight,
  Eye,
  Zap,
  Shield,
  Clock,
  Crown,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Flame,
  Play,
} from "lucide-react";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

/**
 * AdaptiveCoach - The GM-Style Performance Briefing System
 *
 * 4 Sections:
 * 1. Coach Diagnosis - Your Current Growth Priority (ONE primary leak)
 * 2. Next Game Plan - 5 domains with intensity levels
 * 3. Plan Audit - Last Game Execution Review
 * 4. Skill Signals - Live Performance Monitoring
 */
const AdaptiveCoach = ({ user }) => {
  const navigate = useNavigate();
  const boardRef = useRef(null);

  // Data states
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [coachData, setCoachData] = useState(null);

  // Board state
  const [currentFen, setCurrentFen] = useState(START_FEN);
  const [boardTitle, setBoardTitle] = useState("Interactive Board");

  // Sync status
  const [syncStatus, setSyncStatus] = useState(null);

  // Fetch Adaptive Coach data
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const response = await fetch(`${API}/adaptive-coach`, {
          credentials: "include",
        });

        if (response.ok) {
          const data = await response.json();
          setCoachData(data);
        } else {
          setError("Failed to load coaching data");
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
        const response = await fetch(`${API}/sync-status`, {
          credentials: "include",
        });
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

  // Get trend icon
  const getTrendIcon = (trend) => {
    if (trend === "improving") return <TrendingUp className="w-4 h-4 text-emerald-400" />;
    if (trend === "declining") return <TrendingDown className="w-4 h-4 text-red-400" />;
    return <Minus className="w-4 h-4 text-amber-400" />;
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

  // Get status color
  const getStatusColor = (status) => {
    if (status === "executed") return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
    if (status === "partial") return "text-amber-400 bg-amber-500/10 border-amber-500/30";
    if (status === "missed") return "text-red-400 bg-red-500/10 border-red-500/30";
    return "text-muted-foreground bg-muted/30 border-border/50";
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
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card className="border-2 border-dashed border-muted-foreground/20">
              <CardContent className="py-12 text-center">
                <Brain className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
                <h3 className="text-lg font-medium mb-2">Building Your Profile</h3>
                <p className="text-muted-foreground mb-6">
                  Analyze {coachData.games_required - coachData.games_analyzed} more games to unlock personalized coaching
                </p>
                <Progress
                  value={(coachData.games_analyzed / coachData.games_required) * 100}
                  className="w-48 mx-auto mb-4"
                />
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

  const { diagnosis, next_game_plan, plan_audit, skill_signals, opening_recommendation } = coachData || {};

  return (
    <Layout user={user}>
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between mb-6"
        >
          <div>
            <h1 className="text-2xl font-bold">Focus</h1>
            <p className="text-sm text-muted-foreground">
              {coachData?.rating_band} • {coachData?.games_analyzed} games analyzed
            </p>
          </div>

          {/* Sync Timer */}
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
                    Next sync:{" "}
                    <span className="font-mono font-medium text-foreground">
                      {formatSyncTime(syncStatus.next_sync_in_seconds)}
                    </span>
                  </span>
                </>
              )}
            </div>
          )}
        </motion.div>

        {/* Main Layout: Board on Left, Sections on Right */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* LEFT PANEL: Interactive Board */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="lg:sticky lg:top-20 lg:self-start"
          >
            <Card className="border-2 border-border/50">
              <CardContent className="p-4">
                <div className="text-sm text-muted-foreground mb-2">{boardTitle}</div>
                <CoachBoard
                  ref={boardRef}
                  initialFen={currentFen}
                  userColor="white"
                  drillMode={false}
                  showControls={true}
                />
              </CardContent>
            </Card>
          </motion.div>

          {/* RIGHT PANEL: 4 Sections */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="space-y-6"
          >
            {/* SECTION 1: Coach Diagnosis */}
            <Card className="border-red-500/30 bg-red-500/5" data-testid="coach-diagnosis">
              <CardContent className="py-5">
                <div className="flex items-center gap-2 mb-3">
                  <AlertTriangle className="w-5 h-5 text-red-400" />
                  <h3 className="font-semibold text-red-400">{diagnosis?.title}</h3>
                </div>

                {/* Primary Leak */}
                <div className="mb-4">
                  <div className="text-lg font-bold mb-1">{diagnosis?.primary_leak?.label}</div>
                  <p className="text-sm text-muted-foreground">
                    {diagnosis?.primary_leak?.explanation}
                  </p>
                </div>

                {/* See Pattern Button */}
                {diagnosis?.primary_leak?.example_position?.fen && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="border-red-500/30 text-red-400 hover:bg-red-500/10"
                    onClick={() =>
                      handleViewPosition(
                        diagnosis.primary_leak.example_position.fen,
                        `Typical ${diagnosis.primary_leak.label} Pattern`
                      )
                    }
                    data-testid="view-leak-pattern"
                  >
                    <Eye className="w-3.5 h-3.5 mr-1.5" />
                    See Typical Pattern
                  </Button>
                )}

                {/* Secondary Leak (if any) */}
                {diagnosis?.secondary_leak && (
                  <div className="mt-4 pt-4 border-t border-border/30">
                    <div className="text-xs text-muted-foreground mb-1">Secondary Focus</div>
                    <div className="text-sm font-medium">{diagnosis.secondary_leak.label}</div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* SECTION 2: Next Game Plan */}
            <Card className="border-blue-500/30 bg-blue-500/5" data-testid="next-game-plan">
              <CardContent className="py-5">
                <div className="flex items-center gap-2 mb-4">
                  <Target className="w-5 h-5 text-blue-400" />
                  <h3 className="font-semibold text-blue-400">Next Game Plan</h3>
                </div>

                <div className="space-y-3">
                  {next_game_plan?.domains?.map((domain) => (
                    <div
                      key={domain.id}
                      className="flex items-start gap-3 p-3 rounded-lg bg-background/50 border border-border/30"
                      data-testid={`plan-domain-${domain.id}`}
                    >
                      <div className="mt-0.5 text-blue-400">
                        {getDomainIcon(domain.id)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium mb-0.5">{domain.label}</div>
                        <p className="text-sm text-muted-foreground">{domain.goal}</p>
                      </div>
                      {domain.has_board_drill && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-blue-400"
                          onClick={() => handleViewPosition(START_FEN, domain.label)}
                        >
                          <Play className="w-3.5 h-3.5" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>

                {/* Opening Recommendation */}
                {opening_recommendation?.best_opening_white && (
                  <div className="mt-4 pt-4 border-t border-border/30">
                    <div className="text-xs text-muted-foreground mb-2">Recommended Opening</div>
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-white border border-border" />
                      <span className="text-sm font-medium">
                        {opening_recommendation.best_opening_white.name}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        (Stability: {opening_recommendation.best_opening_white.stability}%)
                      </span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* SECTION 3: Plan Audit */}
            <Card className="border-amber-500/30 bg-amber-500/5" data-testid="plan-audit">
              <CardContent className="py-5">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Shield className="w-5 h-5 text-amber-400" />
                    <h3 className="font-semibold text-amber-400">Last Game Execution</h3>
                  </div>
                  {plan_audit?.score && (
                    <span className="text-sm font-bold text-amber-400">{plan_audit.score}</span>
                  )}
                </div>

                {/* Last Game Info */}
                {plan_audit?.last_game && (
                  <div className="flex items-center gap-3 mb-4 p-2 rounded bg-background/30">
                    <span
                      className={`text-sm font-bold ${
                        plan_audit.last_game.result === "win"
                          ? "text-emerald-400"
                          : plan_audit.last_game.result === "loss"
                          ? "text-red-400"
                          : "text-amber-400"
                      }`}
                    >
                      {plan_audit.last_game.result?.toUpperCase()}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      vs {plan_audit.last_game.opponent}
                    </span>
                  </div>
                )}

                {/* Audit Cards */}
                {plan_audit?.has_plan ? (
                  <div className="space-y-2">
                    {plan_audit.audit_cards?.map((card) => (
                      <div
                        key={card.domain_id}
                        className={`p-2.5 rounded-lg border ${getStatusColor(card.status)}`}
                        data-testid={`audit-card-${card.domain_id}`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            {card.status === "executed" && <CheckCircle2 className="w-4 h-4" />}
                            {card.status === "partial" && <AlertTriangle className="w-4 h-4" />}
                            {card.status === "missed" && <XCircle className="w-4 h-4" />}
                            {card.status === "n/a" && <Minus className="w-4 h-4" />}
                            <span className="text-sm font-medium">{card.label}</span>
                          </div>

                          {card.board_link_fen && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 px-2"
                              onClick={() =>
                                handleViewPosition(card.board_link_fen, `${card.label} - Move ${card.move_reference}`)
                              }
                            >
                              <Eye className="w-3.5 h-3.5" />
                            </Button>
                          )}
                        </div>
                        
                        {/* Data line - single data point */}
                        {card.data_line && (
                          <div className="mt-1.5 text-xs text-muted-foreground pl-6">
                            {card.data_line}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No previous plan to audit. Play a game and come back!
                  </p>
                )}
              </CardContent>
            </Card>

            {/* SECTION 4: Skill Signals */}
            <Card className="border-purple-500/30 bg-purple-500/5" data-testid="skill-signals">
              <CardContent className="py-5">
                <div className="flex items-center gap-2 mb-4">
                  <Flame className="w-5 h-5 text-purple-400" />
                  <h3 className="font-semibold text-purple-400">Skill Development Signals</h3>
                </div>

                {skill_signals?.has_enough_data ? (
                  <div className="space-y-3">
                    {skill_signals.signals?.map((signal) => (
                      <div
                        key={signal.id}
                        className="flex items-center justify-between"
                        data-testid={`signal-${signal.id}`}
                      >
                        <div className="flex items-center gap-3">
                          {getTrendIcon(signal.trend)}
                          <div>
                            <div className="text-sm font-medium">{signal.label}</div>
                            <div className="text-xs text-muted-foreground">{signal.reason}</div>
                          </div>
                        </div>

                        {signal.example_position?.fen && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 px-2 text-muted-foreground"
                            onClick={() =>
                              handleViewPosition(signal.example_position.fen, signal.label)
                            }
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Analyze more games to see your skill trends
                  </p>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>
    </Layout>
  );
};

export default AdaptiveCoach;
