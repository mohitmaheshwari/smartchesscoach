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
import EvalBadge from "@/components/shared/EvalBadge";
import { InlineFlag } from "@/components/shared/FlagMoveDialog";
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
  AlertTriangle,
} from "lucide-react";

// Known Trap Card
const KnownTrapCard = ({ trap }) => {
  if (!trap) return null;
  return (
    <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30">
      <div className="flex items-center gap-2 mb-2">
        <AlertTriangle className="w-4 h-4 text-amber-600" strokeWidth={1.5} />
        <span className="text-sm font-medium text-amber-700">Known Trap: {trap.name}</span>
        <Badge variant="outline" className="text-[10px] ml-auto">{trap.opening}</Badge>
      </div>
      <p className="text-sm text-foreground mb-2">{trap.explanation}</p>
      <p className="text-xs text-muted-foreground">
        <span className="font-medium text-amber-600">How to avoid:</span> {trap.refutation}
      </p>
      {trap.full_line?.length > 0 && (
        <div className="flex items-center gap-1 flex-wrap mt-2">
          {trap.full_line.map((m, i) => (
            <span key={i} className="text-[10px] font-mono px-1 py-0.5 rounded bg-amber-500/10 text-amber-700">
              {i % 2 === 0 ? `${Math.floor(i/2)+1}.` : ""}{m}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

const formatPattern = (key) => {
  if (!key) return "Unknown";
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
};

const MOMENT_TAG_CONFIG = {
  game_changer: { label: "Game Changer", cls: "text-red-500 bg-red-500/10 border-red-500/20", desc: "This move turned a winning position into a losing one" },
  threw_advantage: { label: "Threw Advantage", cls: "text-orange-500 bg-orange-500/10 border-orange-500/20", desc: "You had a clear advantage and let it slip" },
  decisive_moment: { label: "Decisive Moment", cls: "text-amber-500 bg-amber-500/10 border-amber-500/20", desc: "The game was equal — this move decided it" },
  missed_defense: { label: "Critical Defense", cls: "text-blue-500 bg-blue-500/10 border-blue-500/20", desc: "You needed to find the right defensive move here" },
  critical_mistake: { label: "Critical Mistake", cls: "text-red-400 bg-red-500/10 border-red-500/20", desc: "A big swing — this mistake cost a lot" },
};

const MomentTag = ({ tag }) => {
  const config = MOMENT_TAG_CONFIG[tag];
  if (!config) return null;
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border ${config.cls}`} title={config.desc}>
      {config.label}
    </span>
  );
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
  const [consecutiveWrong, setConsecutiveWrong] = useState(0);
  const [trainingComplete, setTrainingComplete] = useState(false);
  const REQUIRED_CORRECT = 5;

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

      const from = moveData.from;
      const to = moveData.to;
      
      const chess = new Chess(currentFiltered.fen);
      try {
        const move = chess.move({ from, to, promotion: "q" });
        if (!move) return false;

        const userMoveUci = `${from}${to}`;
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
            setSolveResult(result);
            if (result.solved || result.near_miss) {
              setSolveState(result.solved ? "correct" : "near_miss");
              setSessionSolved((p) => {
                const next = p + 1;
                if (next >= REQUIRED_CORRECT) setTrainingComplete(true);
                return next;
              });
              setConsecutiveWrong(0);
              setLastMove([from, to]);
              if (result.solved) {
                setArrows([[from, to, "green"]]);
              } else {
                const correctFrom = currentFiltered.best_move_uci?.slice(0, 2);
                const correctTo = currentFiltered.best_move_uci?.slice(2, 4);
                setArrows([
                  [from, to, "blue"],
                  ...(correctFrom && correctTo ? [[correctFrom, correctTo, "green"]] : []),
                ]);
              }
            } else {
              setSolveState("incorrect");
              setConsecutiveWrong((p) => {
                const next = p + 1;
                // Reset progress on 2 consecutive wrong
                if (next >= 2) {
                  setSessionSolved((s) => Math.max(0, s - 1));
                  return 0;
                }
                return next;
              });
              const correctFrom = currentFiltered.best_move_uci?.slice(0, 2);
              const correctTo = currentFiltered.best_move_uci?.slice(2, 4);
              setArrows([
                [from, to, "red"],
                ...(correctFrom && correctTo
                  ? [[correctFrom, correctTo, "green"]]
                  : []),
              ]);
            }
          })
          .catch(() => {
            // Fallback: local check
            const isCorrect =
              userMoveUci === currentFiltered.best_move_uci ||
              move.san === currentFiltered.best_move_san;
            if (isCorrect) {
              setSolveState("correct");
              setSessionSolved((p) => p + 1);
              setArrows([[from, to, "green"]]);
            } else {
              setSolveState("incorrect");
              const correctFrom = currentFiltered.best_move_uci?.slice(0, 2);
              const correctTo = currentFiltered.best_move_uci?.slice(2, 4);
              setArrows([
                [from, to, "red"],
                ...(correctFrom && correctTo
                  ? [[correctFrom, correctTo, "green"]]
                  : []),
              ]);
            }
          });

        return true;
      } catch (e) {
        return false;
      }
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
            {focusPattern && (
              <div className="text-right">
                <p className="text-sm font-mono font-bold">
                  {Math.min(sessionSolved, REQUIRED_CORRECT)}/{REQUIRED_CORRECT}
                </p>
                <p className="text-[10px] text-muted-foreground">correct</p>
              </div>
            )}
            {!focusPattern && sessionTotal > 0 && (
              <div className="text-right">
                <p className="text-sm font-medium">{sessionSolved}/{sessionTotal}</p>
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
                viewOnly={solveState !== "ready"}
                interactive={solveState === "ready"}
                movableColor={solveState === "ready" ? (currentFiltered.fen?.split(" ")[1] === "w" ? "white" : "black") : undefined}
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
            <AnimatePresence mode="wait">
              {/* TRAINING COMPLETE */}
              {trainingComplete && solveState !== "ready" && (
                <motion.div
                  key="complete"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                >
                  <Card className="bg-emerald-500/5 border-emerald-500/30">
                    <CardContent className="p-6 text-center space-y-4">
                      <div className="w-14 h-14 rounded-2xl bg-emerald-500/15 flex items-center justify-center mx-auto">
                        <CheckCircle2 className="w-7 h-7 text-emerald-500" strokeWidth={2} />
                      </div>
                      <h2 className="text-xl font-heading text-foreground">Training Complete</h2>
                      <p className="text-sm text-muted-foreground leading-relaxed max-w-sm mx-auto">
                        You solved {REQUIRED_CORRECT} puzzles correctly. Now review your games and apply what you practiced.
                      </p>
                      <Button
                        onClick={() => navigate("/lab")}
                        className="w-full gradient-gold text-black font-semibold hover:opacity-90"
                      >
                        Open Lab
                        <ChevronRight className="w-4 h-4 ml-1" />
                      </Button>
                    </CardContent>
                  </Card>
                </motion.div>
              )}

              {/* READY STATE */}
              {solveState === "ready" && !trainingComplete && (
                <motion.div
                  key="ready"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                >
                  <Card className="bg-card border-border" data-testid="solve-prompt">
                    <CardContent className="p-5 space-y-4">
                      {/* Position eval + Reading Prompt */}
                      {currentFiltered.eval_label && (
                        <EvalBadge evalLabel={currentFiltered.eval_label} size="md" showDescription />
                      )}

                      {currentFiltered.reading_prompt && (
                        <div className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/15 space-y-2.5">
                          <div className="flex items-center justify-between">
                            <p className="text-xs font-semibold uppercase tracking-wider text-amber-600">Read the board first</p>
                            {currentFiltered.reading_prompt.phase && (
                              <span className="text-[10px] font-mono text-muted-foreground/60 uppercase">{currentFiltered.reading_prompt.phase}</span>
                            )}
                          </div>
                          <p className="text-sm text-foreground leading-relaxed">{currentFiltered.reading_prompt.prompt}</p>
                          {currentFiltered.reading_prompt.observations?.filter(Boolean).length > 0 && (
                            <ul className="space-y-1 ml-0.5">
                              {currentFiltered.reading_prompt.observations.filter(Boolean).slice(0, 3).map((obs, i) => (
                                <li key={i} className="text-xs text-muted-foreground flex items-start gap-1.5">
                                  <span className="text-amber-500 mt-0.5">•</span> {obs}
                                </li>
                              ))}
                            </ul>
                          )}
                          {currentFiltered.reading_prompt.question && (
                            <p className="text-sm font-medium text-amber-700 dark:text-amber-400 pt-1 border-t border-amber-500/10">{currentFiltered.reading_prompt.question}</p>
                          )}
                        </div>
                      )}

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
                        {currentFiltered.moment_tag && currentFiltered.moment_tag !== "learning_moment" && (
                          <MomentTag tag={currentFiltered.moment_tag} />
                        )}
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

                      {/* WHY this was the best move — position specific */}
                      {solveResult?.explanation && (
                        <div className="space-y-2 p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
                          <p className="text-sm text-foreground">{solveResult.explanation.why_best}</p>
                          
                          {/* The continuation — what happens next */}
                          {solveResult.explanation.continuation?.length > 0 && (
                            <div className="flex items-center gap-1 flex-wrap">
                              {solveResult.explanation.continuation.map((m, i) => (
                                <span key={i} className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                                  m.by === "you" ? "bg-emerald-500/20 text-emerald-700" : "bg-red-500/10 text-red-500"
                                }`}>
                                  {m.move}
                                </span>
                              ))}
                            </div>
                          )}

                          {/* The trap — why the obvious move was bad */}
                          {solveResult.explanation.trap && (
                            <p className="text-xs text-amber-600 italic">{solveResult.explanation.trap}</p>
                          )}

                          {!solveResult?.coaching_feedback && (
                            <div className="border-t border-emerald-500/10 pt-2">
                              <p className="text-xs text-muted-foreground"><span className="font-medium text-emerald-600">Lesson:</span> {solveResult.explanation.lesson}</p>
                            </div>
                          )}
                        </div>
                      )}

                      {/* COACHING FEEDBACK — why it was right + remember */}
                      {solveResult?.coaching_feedback && (
                        <div className="rounded-xl border border-emerald-500/15 bg-emerald-500/[0.03] p-4 space-y-3 relative">
                          <div className="absolute top-2 right-2">
                            <InlineFlag
                              section="training_coaching_feedback"
                              flaggedText={`WHY: ${solveResult.coaching_feedback.why || ""} | REMEMBER: ${solveResult.coaching_feedback.remember || ""}`}
                              context={{ fen: currentFiltered?.fen, moveSan: solveResult?.correct_move, source: "training", component: "coaching_feedback" }}
                            />
                          </div>
                          {solveResult.coaching_feedback.why && (
                            <div>
                              <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 mb-1">Why this works</p>
                              <p className="text-sm text-foreground leading-relaxed">{solveResult.coaching_feedback.why}</p>
                            </div>
                          )}
                          {solveResult.coaching_feedback.remember && (
                            <div className="pt-2 border-t border-emerald-500/10">
                              <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 mb-1">Remember this</p>
                              <p className="text-sm text-foreground font-medium leading-relaxed">{solveResult.coaching_feedback.remember}</p>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Candidate Moves */}
                      <CandidateMoves candidates={solveResult?.candidates} />

                      {/* Known Trap */}
                      <KnownTrapCard trap={solveResult?.known_trap} />

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

              {/* NEAR MISS — good move, but not the best */}
              {solveState === "near_miss" && (
                <motion.div
                  key="near_miss"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                >
                  <Card className="bg-blue-500/5 border-blue-500/30" data-testid="solve-near-miss">
                    <CardContent className="p-5 space-y-4">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-5 h-5 text-blue-500" />
                        <h2 className="font-heading text-blue-600 dark:text-blue-400">Good Move — But There's Better</h2>
                      </div>

                      <p className="text-sm text-muted-foreground">
                        Your move{" "}
                        <span className="font-mono text-blue-600 dark:text-blue-400">{solveResult?.user_move_san}</span>{" "}
                        is a strong choice. But the best was{" "}
                        <span className="font-mono text-emerald-600">{solveResult?.correct_move}</span>.
                      </p>

                      {/* Show why the best is better */}
                      {solveResult?.explanation && (
                        <div className="space-y-2 p-3 rounded-lg bg-blue-500/5 border border-blue-500/15">
                          <p className="text-sm text-foreground">{solveResult.explanation.why_best}</p>
                          {solveResult.explanation.continuation?.length > 0 && (
                            <div>
                              <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">What happens next</p>
                              <div className="flex items-center gap-1 flex-wrap">
                                {solveResult.explanation.continuation.map((m, i) => (
                                  <span key={i} className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                                    m.by === "you" ? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-400" : "bg-red-500/10 text-red-500 dark:text-red-400"
                                  }`}>{m.move}</span>
                                ))}
                              </div>
                            </div>
                          )}
                          {!solveResult?.coaching_feedback && (
                            <div className="border-t border-blue-500/10 pt-2">
                              <p className="text-xs text-muted-foreground"><span className="font-medium text-blue-500">Takeaway:</span> {solveResult.explanation.lesson}</p>
                            </div>
                          )}
                        </div>
                      )}

                      {/* COACHING FEEDBACK */}
                      {solveResult?.coaching_feedback && (
                        <div className="rounded-xl border border-blue-500/15 bg-blue-500/[0.03] p-4 space-y-3 relative">
                          <div className="absolute top-2 right-2">
                            <InlineFlag
                              section="training_coaching_feedback"
                              flaggedText={`WHY: ${solveResult.coaching_feedback.why || ""} | REMEMBER: ${solveResult.coaching_feedback.remember || ""}`}
                              context={{ fen: currentFiltered?.fen, moveSan: solveResult?.correct_move, source: "training", component: "coaching_feedback" }}
                            />
                          </div>
                          {solveResult.coaching_feedback.why && (
                            <div>
                              <p className="text-[10px] font-bold uppercase tracking-wider text-blue-500 mb-1">What made the difference</p>
                              <p className="text-sm text-foreground leading-relaxed">{solveResult.coaching_feedback.why}</p>
                            </div>
                          )}
                          {solveResult.coaching_feedback.remember && (
                            <div className="pt-2 border-t border-blue-500/10">
                              <p className="text-[10px] font-bold uppercase tracking-wider text-blue-500 mb-1">Remember this</p>
                              <p className="text-sm text-foreground font-medium leading-relaxed">{solveResult.coaching_feedback.remember}</p>
                            </div>
                          )}
                        </div>
                      )}

                      <CandidateMoves candidates={solveResult?.candidates} />

                      <div className="flex gap-2">
                        {hasNext && (
                          <Button onClick={goToNext} className="flex-1 bg-blue-600 hover:bg-blue-700" data-testid="next-btn">
                            Next Position
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

                      {/* Side-by-side comparison — your move vs best move */}
                      {solveResult?.comparison && (
                        <div className="rounded-lg border border-border overflow-hidden">
                          <div className="grid grid-cols-2 divide-x divide-border">
                            <div className="p-3 bg-red-500/5">
                              <p className="text-[10px] font-bold uppercase tracking-wider text-red-500 mb-1">Your move</p>
                              <p className="text-sm font-mono font-semibold text-red-600 mb-1">{solveResult.comparison.your_move}</p>
                              <p className="text-xs text-muted-foreground leading-relaxed">{solveResult.comparison.your_move_does}</p>
                            </div>
                            <div className="p-3 bg-emerald-500/5">
                              <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-500 mb-1">Best move</p>
                              <p className="text-sm font-mono font-semibold text-emerald-600 mb-1">{solveResult.comparison.best_move}</p>
                              <p className="text-xs text-muted-foreground leading-relaxed">{solveResult.comparison.best_move_does}</p>
                            </div>
                          </div>
                          {solveResult.comparison.difference && (
                            <div className="px-3 py-2 bg-muted/30 border-t border-border">
                              <p className="text-xs text-foreground leading-relaxed">{solveResult.comparison.difference}</p>
                            </div>
                          )}
                        </div>
                      )}

                      {/* What's wrong with YOUR move (fallback if no comparison) */}
                      {!solveResult?.comparison && solveResult?.your_move_analysis && (
                        <div className="p-3 rounded-lg bg-red-500/5 border border-red-500/20 space-y-2">
                          <p className="text-xs font-medium text-red-500">Your move: <span className="font-mono">{solveResult.your_move_analysis.your_move}</span></p>
                          <p className="text-sm text-foreground">{solveResult.your_move_analysis.what_it_does}</p>
                          <p className="text-xs text-muted-foreground">{solveResult.your_move_analysis.why_bad}</p>
                          {solveResult.your_move_analysis.opponent_punishes && (
                            <div className="border-t border-red-500/10 pt-2">
                              <p className="text-xs text-red-500 font-medium">
                                Opponent responds: <span className="font-mono">{solveResult.your_move_analysis.opponent_punishes.move}</span>
                              </p>
                              <p className="text-xs text-muted-foreground">{solveResult.your_move_analysis.opponent_punishes.description}</p>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Opponent punishment (shown below comparison) */}
                      {solveResult?.comparison && solveResult?.your_move_analysis?.opponent_punishes && (
                        <div className="p-3 rounded-lg bg-red-500/5 border border-red-500/15">
                          <p className="text-xs text-red-500 font-medium">
                            After your move, opponent plays: <span className="font-mono">{solveResult.your_move_analysis.opponent_punishes.move}</span>
                          </p>
                          <p className="text-xs text-muted-foreground mt-0.5">{solveResult.your_move_analysis.opponent_punishes.description}</p>
                        </div>
                      )}

                      {/* WHY this was the best move — only show parts not already in comparison */}
                      {solveResult?.explanation && (
                        <div className="space-y-2 p-3 rounded-lg bg-muted/50 border border-border">
                          {/* Only show why_best if there's no comparison card (avoids repeating) */}
                          {!solveResult?.comparison && (
                            <p className="text-sm text-foreground">{solveResult.explanation.why_best}</p>
                          )}

                          {/* Continuation moves — always useful */}
                          {solveResult.explanation.continuation?.length > 0 && (
                            <div>
                              <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">What happens next</p>
                              <div className="flex items-center gap-1 flex-wrap">
                                {solveResult.explanation.continuation.map((m, i) => (
                                  <span key={i} className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                                    m.by === "you" ? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-400" : "bg-red-500/10 text-red-500 dark:text-red-400"
                                  }`}>
                                    {m.move}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Trap — only show if no comparison (comparison already explains why your move is bad) */}
                          {!solveResult?.comparison && solveResult.explanation.trap && (
                            <p className="text-xs text-amber-600 italic">{solveResult.explanation.trap}</p>
                          )}

                          {/* Lesson — fallback if no coaching feedback */}
                          {!solveResult?.coaching_feedback && (
                            <div className="border-t border-border pt-2">
                              <p className="text-xs text-muted-foreground"><span className="font-medium text-primary">Lesson:</span> {solveResult.explanation.lesson}</p>
                            </div>
                          )}
                        </div>
                      )}

                      {/* COACHING FEEDBACK — why + remember + behavior */}
                      {solveResult?.coaching_feedback && (
                        <div className="rounded-xl border border-amber-500/15 bg-amber-500/[0.03] p-4 space-y-3 relative">
                          <div className="absolute top-2 right-2">
                            <InlineFlag
                              section="training_coaching_feedback"
                              flaggedText={`WHY: ${solveResult.coaching_feedback.why || ""} | REMEMBER: ${solveResult.coaching_feedback.remember || ""}`}
                              context={{ fen: currentFiltered?.fen, moveSan: solveResult?.correct_move, source: "training", component: "coaching_feedback" }}
                            />
                          </div>
                          {solveResult.coaching_feedback.why && (
                            <div>
                              <p className="text-[10px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400 mb-1">Why you missed this</p>
                              <p className="text-sm text-foreground leading-relaxed">{solveResult.coaching_feedback.why}</p>
                            </div>
                          )}
                          {solveResult.coaching_feedback.remember && (
                            <div className="pt-2 border-t border-amber-500/10">
                              <p className="text-[10px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400 mb-1">Remember this</p>
                              <p className="text-sm text-foreground font-medium leading-relaxed">{solveResult.coaching_feedback.remember}</p>
                            </div>
                          )}
                          {solveResult.coaching_feedback.behavior && (
                            <p className="text-xs text-muted-foreground italic pt-1">{solveResult.coaching_feedback.behavior}</p>
                          )}
                        </div>
                      )}

                      {/* Candidate Moves — show what was possible */}
                      <CandidateMoves candidates={solveResult?.candidates} />

                      {/* Known Trap */}
                      <KnownTrapCard trap={solveResult?.known_trap} />

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
          className={`flex items-start gap-3 p-2.5 rounded-lg border transition-colors ${
            c.is_best
              ? "bg-emerald-500/5 border-emerald-500/20"
              : "bg-muted/30 border-zinc-700/30"
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
