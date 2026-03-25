/**
 * TRAINING PAGE → Community Intelligence
 * 
 * Every user's mistake is another user's training material.
 * 
 * Two sources:
 * 1. YOUR PATTERNS — positions from your own games
 * 2. FROM PLAYERS LIKE YOU — community positions from similar-rated players
 * 
 * Each position: interactive board → find the best move → feedback + community stats
 */

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Chess } from "chess.js";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import {
  Loader2,
  Brain,
  CheckCircle2,
  XCircle,
  ChevronRight,
  ChevronLeft,
  Target,
  Zap,
  RotateCcw,
  Users,
  User as UserIcon,
  TrendingUp,
  Swords,
} from "lucide-react";

const formatPattern = (key) => {
  if (!key) return "Unknown";
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
};

const ThinkingTraining = ({ user }) => {
  const navigate = useNavigate();

  // Data state
  const [loading, setLoading] = useState(true);
  const [positions, setPositions] = useState([]);
  const [patternStats, setPatternStats] = useState([]);
  const [communityCount, setCommunityCount] = useState(0);
  const [feedMeta, setFeedMeta] = useState({ own_count: 0, community_count: 0 });

  // Current position state
  const [currentIndex, setCurrentIndex] = useState(0);
  const [solveState, setSolveState] = useState("ready"); // ready | correct | incorrect
  const [solveResult, setSolveResult] = useState(null);
  const [sessionSolved, setSessionSolved] = useState(0);
  const [sessionTotal, setSessionTotal] = useState(0);

  // Board
  const [arrows, setArrows] = useState([]);
  const [lastMove, setLastMove] = useState(null);

  useEffect(() => {
    fetchTrainingData();
  }, []);

  const fetchTrainingData = async () => {
    setLoading(true);
    try {
      const [feedRes, countRes] = await Promise.all([
        fetch(`${API}/training/community-feed?limit=12`, { credentials: "include" }),
        fetch(`${API}/training/community-count`, { credentials: "include" }),
      ]);

      if (feedRes.ok) {
        const data = await feedRes.json();
        setPositions(data.positions || []);
        setPatternStats(data.pattern_stats || []);
        setFeedMeta({
          own_count: data.own_count || 0,
          community_count: data.community_count || 0,
        });
      }
      if (countRes.ok) {
        const data = await countRes.json();
        setCommunityCount(data.count || 0);
      }
    } catch (e) {
      console.error("Failed to load training:", e);
      toast.error("Could not load training data");
    } finally {
      setLoading(false);
    }
  };

  const currentPosition = positions[currentIndex] || null;

  const handleMove = useCallback(
    (from, to, promotion) => {
      if (!currentPosition || solveState !== "ready") return false;

      const chess = new Chess(currentPosition.fen);
      try {
        const move = chess.move({ from, to, promotion: promotion || "q" });
        if (!move) return false;

        const userMoveUci = `${from}${to}${promotion || ""}`;
        setSessionTotal((p) => p + 1);

        // Submit to backend
        fetch(`${API}/training/solve-attempt`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            position_id: currentPosition.position_id,
            user_move: userMoveUci,
            time_taken_seconds: 0,
          }),
        })
          .then((r) => r.json())
          .then((result) => {
            setSolveResult(result);
            if (result.solved) {
              setSolveState("correct");
              setSessionSolved((p) => p + 1);
              setLastMove([from, to]);
              setArrows([{ orig: from, dest: to, brush: "green" }]);
            } else {
              setSolveState("incorrect");
              // Show what was correct
              const correctFrom = currentPosition.best_move_uci?.slice(0, 2);
              const correctTo = currentPosition.best_move_uci?.slice(2, 4);
              setArrows([
                { orig: from, dest: to, brush: "red" },
                ...(correctFrom && correctTo
                  ? [{ orig: correctFrom, dest: correctTo, brush: "green" }]
                  : []),
              ]);
            }
          })
          .catch(() => {
            // Fallback: local check
            const isCorrect =
              userMoveUci === currentPosition.best_move_uci ||
              move.san === currentPosition.best_move_san;
            if (isCorrect) {
              setSolveState("correct");
              setSessionSolved((p) => p + 1);
              setArrows([{ orig: from, dest: to, brush: "green" }]);
            } else {
              setSolveState("incorrect");
              const correctFrom = currentPosition.best_move_uci?.slice(0, 2);
              const correctTo = currentPosition.best_move_uci?.slice(2, 4);
              setArrows([
                { orig: from, dest: to, brush: "red" },
                ...(correctFrom && correctTo
                  ? [{ orig: correctFrom, dest: correctTo, brush: "green" }]
                  : []),
              ]);
            }
          });

        return true;
      } catch (e) {
        return false;
      }
    },
    [currentPosition, solveState]
  );

  const goToNext = () => {
    if (currentIndex < positions.length - 1) {
      setCurrentIndex((i) => i + 1);
      setSolveState("ready");
      setSolveResult(null);
      setArrows([]);
      setLastMove(null);
    }
  };

  const retryPosition = () => {
    setSolveState("ready");
    setSolveResult(null);
    setArrows([]);
    setLastMove(null);
  };

  const refreshFeed = () => {
    setCurrentIndex(0);
    setSolveState("ready");
    setSolveResult(null);
    setArrows([]);
    setLastMove(null);
    setSessionSolved(0);
    setSessionTotal(0);
    fetchTrainingData();
  };

  // Loading
  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4" data-testid="training-loading">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <p className="text-muted-foreground">Finding positions for you...</p>
        </div>
      </Layout>
    );
  }

  // Empty state
  if (positions.length === 0) {
    return (
      <Layout user={user}>
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4" data-testid="training-empty">
          <Brain className="w-12 h-12 text-muted-foreground" />
          <h2 className="text-xl font-semibold">No Training Positions Yet</h2>
          <p className="text-muted-foreground text-center max-w-md">
            Play some games and analyze them. Your mistakes (and other players' mistakes) will become training material.
          </p>
          <div className="flex gap-3">
            <Button onClick={() => navigate("/play-with-coach")} data-testid="play-btn">
              <Swords className="w-4 h-4 mr-2" />
              Play a Game
            </Button>
          </div>
          {communityCount > 0 && (
            <p className="text-xs text-muted-foreground mt-4">
              {communityCount} positions in the community pool
            </p>
          )}
        </div>
      </Layout>
    );
  }

  const isOwn = currentPosition?.source_type === "your_game";
  const hasNext = currentIndex < positions.length - 1;
  const isFinished = currentIndex === positions.length - 1 && solveState !== "ready";

  return (
    <Layout user={user}>
      <div className="max-w-5xl mx-auto py-4 px-4" data-testid="thinking-training">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div>
            <h1 className="text-xl font-bold tracking-tight">Train</h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              {feedMeta.own_count > 0 && `${feedMeta.own_count} from your games`}
              {feedMeta.own_count > 0 && feedMeta.community_count > 0 && " · "}
              {feedMeta.community_count > 0 && `${feedMeta.community_count} from the community`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {sessionTotal > 0 && (
              <div className="text-right">
                <p className="text-sm font-medium">
                  {sessionSolved}/{sessionTotal}
                </p>
                <p className="text-xs text-muted-foreground">solved</p>
              </div>
            )}
            <Badge variant="outline" className="text-xs" data-testid="position-counter">
              {currentIndex + 1} / {positions.length}
            </Badge>
          </div>
        </div>

        {/* Progress bar */}
        <Progress
          value={((currentIndex + (solveState !== "ready" ? 1 : 0)) / positions.length) * 100}
          className="h-1 mb-5"
          data-testid="training-progress"
        />

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
          {/* LEFT: Board (3 cols) */}
          <div className="lg:col-span-3 space-y-3">
            <div className="aspect-square max-w-[500px] mx-auto" data-testid="training-board">
              <LichessBoard
                fen={currentPosition.fen}
                orientation={currentPosition.user_color || "white"}
                viewOnly={solveState !== "ready"}
                onMove={solveState === "ready" ? handleMove : undefined}
                lastMove={lastMove}
                arrows={arrows}
              />
            </div>

            {/* Source attribution */}
            <div className="text-center" data-testid="position-source">
              {isOwn ? (
                <p className="text-xs text-muted-foreground">
                  <UserIcon className="w-3 h-3 inline mr-1" />
                  From your game · Move {currentPosition.move_number}
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">
                  <Users className="w-3 h-3 inline mr-1" />
                  From a game by{" "}
                  <span className="font-medium text-foreground">
                    {currentPosition.source_user_name}
                  </span>
                  , {currentPosition.source_user_rating}
                </p>
              )}
            </div>
          </div>

          {/* RIGHT: Context + Actions (2 cols) */}
          <div className="lg:col-span-2 space-y-4">
            <AnimatePresence mode="wait">
              {/* READY STATE */}
              {solveState === "ready" && (
                <motion.div
                  key="ready"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                >
                  <Card className="bg-card border-border" data-testid="solve-prompt">
                    <CardContent className="p-5 space-y-4">
                      <div className="flex items-center gap-2">
                        <Target className="w-5 h-5 text-amber-500" />
                        <h2 className="font-semibold">Find the Best Move</h2>
                      </div>

                      <p className="text-sm text-muted-foreground">
                        {isOwn
                          ? "You made a mistake here. Can you find the right move now?"
                          : `A ${currentPosition.source_user_rating}-rated player missed this. Can you find it?`}
                      </p>

                      <div className="flex items-center gap-2">
                        <Badge
                          variant="secondary"
                          className="text-xs"
                          data-testid="pattern-badge"
                        >
                          {formatPattern(currentPosition.pattern_type)}
                        </Badge>
                        <Badge
                          variant="outline"
                          className={`text-xs ${
                            currentPosition.difficulty === "easy"
                              ? "border-emerald-500/50 text-emerald-500"
                              : currentPosition.difficulty === "hard"
                              ? "border-red-500/50 text-red-500"
                              : "border-amber-500/50 text-amber-500"
                          }`}
                        >
                          {currentPosition.difficulty}
                        </Badge>
                      </div>

                      {currentPosition.solve_rate > 0 && currentPosition.attempts > 2 && (
                        <p className="text-xs text-muted-foreground">
                          {Math.round(currentPosition.solve_rate)}% solve rate
                        </p>
                      )}
                    </CardContent>
                  </Card>
                </motion.div>
              )}

              {/* CORRECT */}
              {solveState === "correct" && (
                <motion.div
                  key="correct"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                >
                  <Card
                    className="bg-emerald-500/5 border-emerald-500/30"
                    data-testid="solve-correct"
                  >
                    <CardContent className="p-5 space-y-4">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                        <h2 className="font-semibold text-emerald-400">You Found It</h2>
                      </div>

                      <p className="text-sm text-muted-foreground">
                        <span className="font-mono text-emerald-400">
                          {solveResult?.correct_move || currentPosition.best_move_san}
                        </span>{" "}
                        was the right move.
                      </p>

                      {solveResult?.miss_rate_at_your_level != null && (
                        <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800">
                          <p className="text-xs text-muted-foreground">
                            <Users className="w-3 h-3 inline mr-1" />
                            {solveResult.miss_rate_at_your_level}% of players at your level
                            missed this
                          </p>
                        </div>
                      )}

                      <div className="flex gap-2">
                        {hasNext && (
                          <Button
                            onClick={goToNext}
                            className="flex-1"
                            data-testid="next-position-btn"
                          >
                            Next
                            <ChevronRight className="w-4 h-4 ml-1" />
                          </Button>
                        )}
                        {!hasNext && (
                          <Button onClick={refreshFeed} className="flex-1" data-testid="refresh-btn">
                            <RotateCcw className="w-4 h-4 mr-2" />
                            More Positions
                          </Button>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              )}

              {/* INCORRECT */}
              {solveState === "incorrect" && (
                <motion.div
                  key="incorrect"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                >
                  <Card
                    className="bg-red-500/5 border-red-500/30"
                    data-testid="solve-incorrect"
                  >
                    <CardContent className="p-5 space-y-4">
                      <div className="flex items-center gap-2">
                        <XCircle className="w-5 h-5 text-red-500" />
                        <h2 className="font-semibold text-red-400">Not Quite</h2>
                      </div>

                      <p className="text-sm text-muted-foreground">
                        The best move was{" "}
                        <span className="font-mono text-emerald-400">
                          {solveResult?.correct_move || currentPosition.best_move_san}
                        </span>
                      </p>

                      {solveResult?.miss_rate_at_your_level != null && (
                        <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800">
                          <p className="text-xs text-muted-foreground">
                            <Users className="w-3 h-3 inline mr-1" />
                            {solveResult.miss_rate_at_your_level}% of players at your level
                            also missed this
                          </p>
                        </div>
                      )}

                      <div className="flex gap-2">
                        <Button
                          onClick={retryPosition}
                          variant="outline"
                          className="flex-1"
                          data-testid="retry-btn"
                        >
                          <RotateCcw className="w-4 h-4 mr-2" />
                          Retry
                        </Button>
                        {hasNext ? (
                          <Button
                            onClick={goToNext}
                            variant="ghost"
                            className="flex-1 text-muted-foreground"
                            data-testid="skip-btn"
                          >
                            Next
                            <ChevronRight className="w-4 h-4 ml-1" />
                          </Button>
                        ) : (
                          <Button
                            onClick={refreshFeed}
                            variant="ghost"
                            className="flex-1 text-muted-foreground"
                            data-testid="refresh-btn-alt"
                          >
                            More
                          </Button>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Pattern Stats */}
            {patternStats.length > 0 && (
              <Card className="bg-card border-border" data-testid="pattern-stats">
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-muted-foreground" />
                    <h3 className="text-sm font-medium">Your Patterns</h3>
                  </div>
                  <div className="space-y-2">
                    {patternStats.slice(0, 4).map((stat) => (
                      <div
                        key={stat.pattern}
                        className="flex items-center justify-between text-xs"
                        data-testid={`pattern-stat-${stat.pattern}`}
                      >
                        <span className="text-muted-foreground">
                          {formatPattern(stat.pattern)}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">
                            {stat.total_solved}/{stat.total_attempts}
                          </span>
                          <div className="w-12 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                            <div
                              className="h-full rounded-full bg-primary transition-all"
                              style={{ width: `${stat.solve_rate || 0}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Session complete state */}
            {isFinished && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <Card className="bg-card border-border" data-testid="session-complete">
                  <CardContent className="p-4 text-center space-y-3">
                    <Zap className="w-8 h-8 text-primary mx-auto" />
                    <p className="font-medium">Session Complete</p>
                    <p className="text-xs text-muted-foreground">
                      Solved {sessionSolved} of {sessionTotal}
                    </p>
                    <Button onClick={refreshFeed} className="w-full" data-testid="new-session-btn">
                      <RotateCcw className="w-4 h-4 mr-2" />
                      New Session
                    </Button>
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default ThinkingTraining;
