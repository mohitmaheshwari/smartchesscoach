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

import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
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
  const [searchParams] = useSearchParams();
  const focusPattern = searchParams.get('focus');

  // Data state
  const [loading, setLoading] = useState(true);
  const [positions, setPositions] = useState([]);
  const [patternStats, setPatternStats] = useState([]);
  const [communityCount, setCommunityCount] = useState(0);
  const [feedMeta, setFeedMeta] = useState({ own_count: 0, community_count: 0 });
  const [activeFilter, setActiveFilter] = useState(focusPattern || "all"); // "all" or pattern_type

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
  }, [focusPattern]);

  const fetchTrainingData = async () => {
    setLoading(true);
    try {
      const feedUrl = focusPattern
        ? `${API}/training/community-feed?limit=20&pattern=${encodeURIComponent(focusPattern)}`
        : `${API}/training/community-feed?limit=12`;
      const [feedRes, countRes] = await Promise.all([
        fetch(feedUrl, { credentials: "include" }),
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

  // Get unique pattern types for filter tabs
  const patternTypes = useMemo(() => {
    const types = new Set(positions.map((p) => p.pattern_type));
    return Array.from(types);
  }, [positions]);

  // Filtered positions based on active filter
  const filteredPositions = useMemo(() => {
    if (activeFilter === "all") return positions;
    return positions.filter((p) => p.pattern_type === activeFilter);
  }, [positions, activeFilter]);

  const currentFiltered = filteredPositions[currentIndex] || null;

  const handleMove = useCallback(
    (moveData) => {
      if (!currentFiltered || solveState !== "ready") return false;
      if (!moveData || !moveData.from || !moveData.to) return false;

      const from = moveData.from;
      const to = moveData.to;
      const userMoveUci = `${from}${to}`;
      console.log("[TRAINING] Move made:", userMoveUci, "position:", currentFiltered?.position_id);
      setSessionTotal((p) => p + 1);

      // Submit to backend
      fetch(`${API}/training/solve-attempt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          position_id: currentFiltered.position_id,
          user_move: userMoveUci,
          time_taken_seconds: 0,
        }),
      })
        .then((r) => r.json())
        .then((result) => {
          setSolveResult(result || {});
          console.log("[TRAINING] Solve result:", result?.solved, "candidates:", result?.candidates?.length);
          if (result && result.solved) {
            setSolveState("correct");
            setSessionSolved((p) => p + 1);
            setLastMove([from, to]);
            setArrows([{ orig: from, dest: to, brush: "green" }]);
          } else {
            setSolveState("incorrect");
            const correctFrom = (currentFiltered.best_move_uci || "").slice(0, 2);
            const correctTo = (currentFiltered.best_move_uci || "").slice(2, 4);
            const newArrows = [{ orig: from, dest: to, brush: "red" }];
            if (correctFrom && correctTo) {
              newArrows.push({ orig: correctFrom, dest: correctTo, brush: "green" });
            }
            setArrows(newArrows);
          }
        })
        .catch((err) => {
          console.error("Solve attempt failed:", err);
          // Fallback: local check
          const isCorrect = userMoveUci === currentFiltered.best_move_uci;
          if (isCorrect) {
            setSolveState("correct");
            setSessionSolved((p) => p + 1);
            setArrows([{ orig: from, dest: to, brush: "green" }]);
          } else {
            setSolveState("incorrect");
            const correctFrom = (currentFiltered.best_move_uci || "").slice(0, 2);
            const correctTo = (currentFiltered.best_move_uci || "").slice(2, 4);
            const newArrows = [{ orig: from, dest: to, brush: "red" }];
            if (correctFrom && correctTo) {
              newArrows.push({ orig: correctFrom, dest: correctTo, brush: "green" });
            }
            setArrows(newArrows);
          }
        });

      return true;
    },
    [currentFiltered, solveState]
  );

  const goToNext = () => {
    if (currentIndex < filteredPositions.length - 1) {
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
    setActiveFilter("all");
    fetchTrainingData();
  };

  const handleFilterChange = (filter) => {
    setActiveFilter(filter);
    setCurrentIndex(0);
    setSolveState("ready");
    setSolveResult(null);
    setArrows([]);
    setLastMove(null);
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
          <h2 className="text-xl font-heading">No Training Positions Yet</h2>
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

  const isOwn = currentFiltered?.source_type === "your_game";
  const hasNext = currentIndex < filteredPositions.length - 1;
  const isFinished = currentIndex === filteredPositions.length - 1 && solveState !== "ready";

  return (
    <Layout user={user}>
      <div className="max-w-5xl mx-auto py-4 px-4" data-testid="thinking-training">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div>
            <h1 className="text-2xl font-heading tracking-tight">Train</h1>
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
              {currentIndex + 1} / {filteredPositions.length}
            </Badge>
          </div>
        </div>

        {/* Pattern filter tabs */}
        {patternTypes.length > 1 && (
          <div className="flex flex-wrap gap-1.5 mb-3" data-testid="pattern-filter">
            <button
              className={`text-xs px-2.5 py-1 rounded-sm border transition-colors ${
                activeFilter === "all"
                  ? "border-current bg-amber-50 text-amber-700"
                  : "border-zinc-700 text-muted-foreground hover:border-zinc-500"
              }`}
              onClick={() => handleFilterChange("all")}
              data-testid="filter-all"
            >
              All ({positions.length})
            </button>
            {patternTypes.map((pt) => (
              <button
                key={pt}
                className={`text-xs px-2.5 py-1 rounded-sm border transition-colors ${
                  activeFilter === pt
                    ? "border-current bg-amber-50 text-amber-700"
                    : "border-zinc-700 text-muted-foreground hover:border-zinc-500"
                }`}
                onClick={() => handleFilterChange(pt)}
                data-testid={`filter-${pt}`}
              >
                {formatPattern(pt)} ({positions.filter((p) => p.pattern_type === pt).length})
              </button>
            ))}
          </div>
        )}

        {/* Progress bar */}
        <Progress
          value={((currentIndex + (solveState !== "ready" ? 1 : 0)) / filteredPositions.length) * 100}
          className="h-1 mb-5"
          data-testid="training-progress"
        />

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
          {/* LEFT: Board (3 cols) */}
          <div className="lg:col-span-3 space-y-3">
            <div className="aspect-square max-w-[500px] mx-auto" data-testid="training-board">
              <LichessBoard
                fen={currentFiltered.fen}
                orientation={currentFiltered.user_color || "white"}
                viewOnly={false}
                interactive={true}
                movableColor={currentFiltered.user_color || "white"}
                onMove={handleMove}
                lastMove={lastMove}
                arrows={arrows}
              />
            </div>

            {/* Source attribution */}
            <div className="text-center" data-testid="position-source">
              {isOwn ? (
                <p className="text-xs text-muted-foreground">
                  <UserIcon className="w-3 h-3 inline mr-1" />
                  From your game · Move {currentFiltered.move_number}
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">
                  <Users className="w-3 h-3 inline mr-1" />
                  From a game by{" "}
                  <span className="font-medium text-foreground">
                    {currentFiltered.source_user_name}
                  </span>
                  , {currentFiltered.source_user_rating}
                </p>
              )}
            </div>
          </div>

          {/* RIGHT: Context + Actions (2 cols) */}
          <div className="lg:col-span-2 space-y-4">
            <AnimatePresence>
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
                        <Target className="w-5 h-5 text-amber-600" />
                        <h2 className="font-heading">Find the Best Move</h2>
                      </div>

                      <p className="text-sm text-muted-foreground">
                        {isOwn
                          ? "You made a mistake here. Can you find the right move now?"
                          : `A ${currentFiltered.source_user_rating}-rated player missed this. Can you find it?`}
                      </p>

                      <div className="flex items-center gap-2">
                        <Badge
                          variant="secondary"
                          className="text-xs"
                          data-testid="pattern-badge"
                        >
                          {formatPattern(currentFiltered.pattern_type)}
                        </Badge>
                        <Badge
                          variant="outline"
                          className={`text-xs ${
                            currentFiltered.difficulty === "easy"
                              ? "border-emerald-500/50 text-emerald-500"
                              : currentFiltered.difficulty === "hard"
                              ? "border-red-500/50 text-red-500"
                              : "border-amber-500/50 text-amber-600"
                          }`}
                        >
                          {currentFiltered.difficulty}
                        </Badge>
                      </div>

                      {currentFiltered.solve_rate > 0 && currentFiltered.attempts > 2 && (
                        <p className="text-xs text-muted-foreground">
                          {Math.round(currentFiltered.solve_rate)}% solve rate
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
                        <h2 className="font-heading text-emerald-600">You Found It</h2>
                      </div>

                      <p className="text-sm text-muted-foreground">
                        <span className="font-mono text-emerald-600">
                          {solveResult?.correct_move || currentFiltered.best_move_san}
                        </span>{" "}
                        was the right move.
                        {solveResult?.original_player_move && (
                          <span className="text-muted-foreground"> The original player played <span className="font-mono text-red-600">{solveResult.original_player_move}</span>.</span>
                        )}
                      </p>

                      {/* Candidate Moves */}
                      <CandidateMoves candidates={solveResult?.candidates} />

                      {solveResult?.miss_rate_at_your_level != null && (
                        <div className="p-3 rounded-lg bg-muted/50 border border-border">
                          <p className="text-sm text-muted-foreground">
                            <Users className="w-3.5 h-3.5 inline mr-1.5" />
                            <span className="text-emerald-600 font-medium">{solveResult.miss_rate_at_your_level}%</span>{" "}
                            of players at your level missed this
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
                        <h2 className="font-heading text-red-600">Not Quite</h2>
                      </div>

                      <p className="text-sm text-muted-foreground">
                        The best move was{" "}
                        <span className="font-mono text-emerald-600">
                          {solveResult?.correct_move || currentFiltered.best_move_san}
                        </span>
                        {solveResult?.original_player_move && (
                          <span className="text-muted-foreground">. The original player also missed it — they played <span className="font-mono text-red-600">{solveResult.original_player_move}</span>.</span>
                        )}
                      </p>

                      {/* Candidate Moves — show what was possible */}
                      <CandidateMoves candidates={solveResult?.candidates} />

                      {solveResult?.miss_rate_at_your_level != null && (
                        <div className="p-3 rounded-lg bg-muted/50 border border-border">
                          <p className="text-sm text-muted-foreground">
                            <Users className="w-3.5 h-3.5 inline mr-1.5" />
                            <span className="text-amber-600 font-medium">{solveResult.miss_rate_at_your_level}%</span>{" "}
                            of players at your level also missed this
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
                          <div className="w-12 h-1.5 rounded-full bg-muted overflow-hidden">
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

// Candidate Moves display — shows the top engine moves with explanations
const CandidateMoves = ({ candidates }) => {
  if (!candidates || candidates.length === 0) return null;

  return (
    <div className="space-y-2" data-testid="candidate-moves">
      <p className="text-xs text-muted-foreground uppercase tracking-wide">Ideas in this position</p>
      {candidates.map((c, i) => (
        <div
          key={i}
          className={`flex items-start gap-3 p-2.5 rounded-sm border transition-colors ${
            c.is_best
              ? "bg-emerald-50 border-emerald-200"
              : "bg-muted/30 border-border"
          }`}
          data-testid={`candidate-${i}`}
        >
          <Badge
            variant="outline"
            className={`text-xs font-mono flex-shrink-0 mt-0.5 ${
              c.is_best ? "text-emerald-600 border-emerald-500/30" : "text-muted-foreground border-zinc-600"
            }`}
          >
            {c.move}
          </Badge>
          <div className="flex-1 min-w-0">
            <p className={`text-sm leading-relaxed ${c.is_best ? "text-emerald-300" : "text-muted-foreground"}`}>
              {c.idea}
            </p>
            {c.type && c.type !== "engine_choice" && (
              <span className="text-[10px] text-muted-foreground capitalize">{c.type.replace(/_/g, " ")}</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};


export default ThinkingTraining;
