/**
 * GAME REVIEW PAGE → Understand
 * 
 * One screen. One job. Understand what went wrong.
 * 
 * Structure:
 * - Board (large, front and center)
 * - Coaching for current move (V5 narrative)
 * - Move list (mistakes highlighted, click to navigate)
 * 
 * That's it. No stats. No strategy tabs. No clutter.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import Layout from "@/components/Layout";
import ChessBoardViewer from "@/components/ChessBoardViewer";
import { toast } from "sonner";
import {
  ArrowLeft,
  Loader2,
  Brain,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  MessageCircle,
  Send,
  X,
  Zap,
  Target,
  Lightbulb,
  PlayCircle
} from "lucide-react";
import { Input } from "@/components/ui/input";

/* ── Game Overview: phases + opening + behaviors ── */
const GameOverview = ({ review, navigate }) => {
  const phases = review.phases || {};
  const opening = review.opening_analysis;
  const behaviors = review.behaviors || [];
  const keyMoments = review.key_moments || [];
  const fundamentals = review.fundamentals || {};

  return (
    <div className="mb-4 space-y-3">
      {/* Phase Accuracy Bar */}
      <div className="flex gap-2">
        {["opening", "middlegame", "endgame"].map(key => {
          const p = phases[key];
          if (!p) return null;
          const color = p.accuracy >= 80 ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
            : p.accuracy >= 60 ? "bg-amber-500/10 border-amber-500/20 text-amber-400"
            : "bg-red-500/10 border-red-500/20 text-red-400";
          return (
            <div key={key} className={`flex-1 rounded-xl border p-3 ${color}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold">{p.name}</span>
                <span className="text-sm font-bold font-mono">{p.accuracy}%</span>
              </div>
              <p className="text-[10px] opacity-70">{p.verdict} · {p.moves} moves</p>
            </div>
          );
        })}
      </div>

      {/* Opening Awareness */}
      {opening && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-widest text-primary/60">Opening</span>
              <span className="text-sm font-medium text-white">{opening.name}</span>
            </div>
            <span className="text-[10px] text-zinc-500">
              {opening.moves_in_theory}/{opening.total_theory_moves} theory moves
            </span>
          </div>

          {opening.deviation && (
            <p className="text-xs text-zinc-400 mb-2">
              Deviated on move {Math.floor(opening.deviation.ply / 2) + 1}: played <span className="font-mono text-red-400">{opening.deviation.played}</span> instead of <span className="font-mono text-emerald-400">{opening.deviation.expected}</span>
              {opening.deviation.idea && <span className="text-zinc-500"> — {opening.deviation.idea.toLowerCase()}</span>}
            </p>
          )}

          {!opening.deviation && opening.moves_in_theory === opening.total_theory_moves && (
            <p className="text-xs text-emerald-400/70">Followed theory perfectly.</p>
          )}

          {opening.traps?.length > 0 && opening.traps.map((t, i) => {
            const trapColor = t.sprung && t.victim_color === review.user_color
              ? "bg-red-500/10 border-red-500/20"  // User fell for it
              : t.sprung
              ? "bg-emerald-500/10 border-emerald-500/20"  // User sprung it on opponent
              : t.avoided
              ? "bg-emerald-500/5 border-emerald-500/15"  // User avoided it
              : "bg-amber-500/5 border-amber-500/15";  // Position reached
            const iconColor = t.sprung && t.victim_color === review.user_color
              ? "text-red-400" : t.sprung ? "text-emerald-400" : "text-amber-500";

            return (
              <div key={i} className={`mt-2 rounded-lg border px-3 py-2 ${trapColor}`}>
                <div className="flex items-center gap-1.5">
                  <Zap className={`w-3 h-3 ${iconColor}`} strokeWidth={2.5} />
                  <span className={`text-[10px] font-bold ${iconColor}`}>{t.name}</span>
                  {t.sprung && <span className="text-[9px] px-1 py-0 rounded bg-zinc-800 text-zinc-400 ml-auto">
                    {t.victim_color === review.user_color ? "Fell for it" : "Caught them"}
                  </span>}
                  {t.avoided && <span className="text-[9px] px-1 py-0 rounded bg-zinc-800 text-emerald-400 ml-auto">Avoided</span>}
                </div>
                <p className="text-[10px] text-zinc-400 mt-0.5">{t.story || t.explanation}</p>
                {t.sprung && t.victim_color === review.user_color && t.refutation && (
                  <p className="text-[10px] text-zinc-500 mt-1 italic">How to avoid: {t.refutation}</p>
                )}
              </div>
            );
          })}

          {opening.branches && (
            <div className="mt-2 flex items-center gap-2">
              <span className="text-[10px] text-zinc-500">Variations:</span>
              {opening.branches.branches.map((b, i) => (
                <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">{b.name}</span>
              ))}
            </div>
          )}

          <button
            onClick={() => navigate(`/play-with-coach?opening=${encodeURIComponent(opening.name)}`)}
            className="mt-2 text-[10px] text-primary hover:text-primary/80 flex items-center gap-1"
          >
            Practice this opening with Coach <ChevronRight className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* Behavioral Summary + Fundamentals */}
      {(behaviors.length > 0 || Object.keys(fundamentals).length > 0) && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          {/* Behaviors */}
          {behaviors.length > 0 && (
            <div className="mb-3">
              <p className="text-xs font-bold uppercase tracking-widest text-red-400/60 mb-2">What went wrong</p>
              {behaviors.map((b, i) => (
                <div key={i} className="flex items-center justify-between py-1">
                  <span className="text-sm text-zinc-300">{b.label}</span>
                  <span className="text-xs font-mono text-zinc-500">{b.count}x</span>
                </div>
              ))}
            </div>
          )}

          {/* Fundamentals by phase */}
          {Object.entries(fundamentals).map(([phase, funds]) => {
            if (!funds || funds.length === 0) return null;
            return (
              <div key={phase} className="mb-2">
                <p className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1 capitalize">{phase} fundamentals</p>
                {funds.map((f, i) => (
                  <div key={i} className="flex items-center gap-2 py-0.5">
                    <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${f.progress >= 70 ? "bg-emerald-500" : f.progress >= 40 ? "bg-amber-400" : "bg-red-400"}`}
                        style={{ width: `${f.progress}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-zinc-400 w-32 truncate">{f.name}</span>
                    <span className="text-[10px] font-mono text-zinc-500 w-6 text-right">{f.progress}</span>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};


const GameAnalysis = ({ user }) => {
  const { gameId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialMove = searchParams.get('move');
  
  const [game, setGame] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [currentMoveIndex, setCurrentMoveIndex] = useState(0);
  const [initialMoveHandled, setInitialMoveHandled] = useState(false);
  
  // V5 Decryption data
  const [decryptionData, setDecryptionData] = useState(null);
  const [decryptionLoading, setDecryptionLoading] = useState(false);
  const [decryptionStatus, setDecryptionStatus] = useState(null);
  // Toggle: when ON show LLM-polished caption (caption_llm) if available;
  // when OFF show the deterministic template (caption). Persisted in
  // localStorage so it syncs with /admin/captions toggle.
  const [useLlmCaption, setUseLlmCaption] = useState(() => {
    try {
      const v = localStorage.getItem("useLlmCaption");
      return v === null ? true : v === "true";
    } catch (e) { return true; }
  });
  useEffect(() => {
    try { localStorage.setItem("useLlmCaption", String(useLlmCaption)); } catch (e) {}
  }, [useLlmCaption]);
  
  // Coach Review (fundamentals, phases, opening, behaviors)
  const [coachReview, setCoachReview] = useState(null);

  // Ask About Move
  const [askQuestion, setAskQuestion] = useState("");
  const [askLoading, setAskLoading] = useState(false);
  const [showAsk, setShowAsk] = useState(false);
  const [conversationHistory, setConversationHistory] = useState([]);

  // v70 (2026-05-23) — "Play this line" state. coachLineActive marks
  // that we're showing a variation (the side panel renders); the step
  // index drives which step's explanation is highlighted as the board
  // animates. Resets to inactive when user changes move via navigation.
  const [coachLineActive, setCoachLineActive] = useState(false);
  const [coachLineStepIndex, setCoachLineStepIndex] = useState(-1);

  const boardRef = useRef(null);

  // Fetch game and analysis
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [gameRes, analysisRes] = await Promise.all([
          fetch(`${API}/games/${gameId}`, { credentials: "include" }),
          fetch(`${API}/analysis/${gameId}`, { credentials: "include" })
        ]);
        
        if (!gameRes.ok) throw new Error("Game not found");
        setGame(await gameRes.json());
        
        if (analysisRes.ok) {
          setAnalysis(await analysisRes.json());
        }
      } catch (error) {
        toast.error("Failed to load game");
        navigate("/lab");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [gameId, navigate]);

  // Fetch coach review (fundamentals, phases, opening)
  useEffect(() => {
    if (!analysis) return;
    (async () => {
      try {
        const res = await fetch(`${API}/games/${gameId}/coach-review`, { credentials: "include" });
        if (res.ok) setCoachReview(await res.json());
      } catch (e) { console.error("Coach review fetch failed:", e); }
    })();
  }, [analysis, gameId]);

  // v71 (2026-05-23) — game-wide board-state trends (P5). Surfaces
  // patterns that persisted across multiple user moves (e.g. "your
  // pieces stayed on your side for 12 moves") — insight no
  // single-position caption can give.
  const [boardSummary, setBoardSummary] = useState(null);
  useEffect(() => {
    if (!analysis) return;
    (async () => {
      try {
        const res = await fetch(`${API}/games/${gameId}/board-summary`, { credentials: "include" });
        if (res.ok) setBoardSummary(await res.json());
      } catch (e) { console.error("Board summary fetch failed:", e); }
    })();
  }, [analysis, gameId]);

  // v72 (2026-05-23) — P2 detector memory: per-game pattern misses.
  // Shows which catalogued patterns (queen_fork, clearance_then_check,
  // etc.) the user missed in THIS game, with miss-count per pattern.
  // Corpus-wide aggregate lives at /api/coach/pattern-progress.
  const [patternMisses, setPatternMisses] = useState(null);
  useEffect(() => {
    if (!analysis) return;
    (async () => {
      try {
        const res = await fetch(`${API}/games/${gameId}/pattern-misses`, { credentials: "include" });
        if (res.ok) setPatternMisses(await res.json());
      } catch (e) { console.error("Pattern misses fetch failed:", e); }
    })();
  }, [analysis, gameId]);

  // Fetch V5 decryption data
  useEffect(() => {
    if (!analysis) return;
    
    const fetchDecryption = async () => {
      setDecryptionLoading(true);
      try {
        const res = await fetch(`${API}/coach/decryption/v5/${gameId}`, { 
          credentials: "include" 
        });
        const data = await res.json();
        
        if (data.status === "complete") {
          setDecryptionData(data.decryption_data || []);
          setDecryptionStatus("complete");
        } else if (data.status === "generating") {
          setDecryptionStatus("generating");
          // Poll for completion
          setTimeout(fetchDecryption, 3000);
        } else {
          setDecryptionStatus("error");
        }
      } catch (e) {
        console.error("Decryption fetch error:", e);
        setDecryptionStatus("error");
      } finally {
        setDecryptionLoading(false);
      }
    };
    
    fetchDecryption();
  }, [analysis, gameId]);

  // Jump to initial move from URL.
  //
  // NOTE: GameAnalysis.jsx is the legacy game-review page; production
  // /game/:gameId routes to LabV2 (see App.js). The real fix for the
  // ?move=N URL lives in LabV2.jsx. This file is kept for legacy
  // routes / admin tools but no production user lands here. Same
  // ply conversion preserved here for parity if it ever does.
  useEffect(() => {
    if (!initialMoveHandled && initialMove && boardRef.current && !loading && decryptionData) {
      const moveNum = parseInt(initialMove, 10);
      if (!isNaN(moveNum) && moveNum > 0) {
        const userColor = (game?.user_color || "white").toLowerCase();
        const targetPly = (moveNum - 1) * 2 + (userColor === "black" ? 1 : 0);
        setTimeout(() => {
          boardRef.current.goToMove(targetPly);
          setCurrentMoveIndex(targetPly);
          setInitialMoveHandled(true);
        }, 300);
      }
    }
  }, [initialMove, loading, initialMoveHandled, decryptionData, game]);

  // Clear conversation when move changes
  useEffect(() => {
    setConversationHistory([]);
    setShowAsk(false);
    // v70: any in-flight "Play this line" playback is cancelled by
    // the board itself on goToMove; we also reset our side-panel
    // state so the explanations don't keep showing for the prior
    // move's variation.
    setCoachLineActive(false);
    setCoachLineStepIndex(-1);
  }, [currentMoveIndex]);

  // Derived data
  const pgn = game?.pgn || "";
  const userColor = game?.user_color || "white";
  
  // Get current move's coaching data
  const currentMoveData = decryptionData?.[currentMoveIndex] || null;

  // Visual-shape detections for the current move (pattern-recognition layer
  // sitting alongside the V5 narrative — see project_visual_danger_language
  // memo. The shapes array lives on each move_evaluation; first-occurrence
  // dedup happens in analysis_interpreter so at most one entry per type).
  const currentMoveShapes =
    analysis?.stockfish_analysis?.move_evaluations?.[currentMoveIndex]?.shapes || [];

  // Get all moves for the move list
  const moves = decryptionData || [];

  // v70 (2026-05-23) — derived "Play this line" payload for the
  // current move. Trap-line takes precedence (richer per-step
  // explanations from data/traps.json); otherwise we slice pv_after_best
  // to the backend's coach_line_length_hint (defaults to 3 plies for
  // user mistakes). Returns null when there's nothing meaningful to
  // play, so the button is conditionally rendered.
  const coachLine = (() => {
    // v79.1 (2026-05-24) — Mohit: button should fire on BOTH user AND
    // opp mistakes. For opp moves the backend ships an explicit
    // coach_line_moves list ([opp_played, user_reply, opp_followup,
    // user_continuation]). For user moves we keep falling back to
    // pv_after_best sliced by hint.
    if (!currentMoveData) return null;
    const trap = currentMoveData.trap_line_full;
    if (Array.isArray(trap) && trap.length > 0) {
      return {
        kind: "trap",
        moves: trap.map((s) => s.move).filter(Boolean),
        steps: trap,
      };
    }
    if (Array.isArray(currentMoveData.coach_line_moves) && currentMoveData.coach_line_moves.length > 0) {
      const moves = currentMoveData.coach_line_moves;
      return {
        kind: currentMoveData.is_user_move ? "pv" : "punishment",
        moves,
        steps: moves.map((m) => ({ move: m, explanation: null })),
      };
    }
    if (!currentMoveData.is_user_move) return null;
    const pv = currentMoveData.pv_after_best || [];
    const hint = currentMoveData.coach_line_length_hint;
    if (!pv.length || !hint || hint < 1) return null;
    const sliced = pv.slice(0, hint);
    if (!sliced.length) return null;
    return {
      kind: "pv",
      moves: sliced,
      steps: sliced.map((m) => ({ move: m, explanation: null })),
    };
  })();

  const handlePlayCoachLine = useCallback(() => {
    if (!coachLine || !currentMoveData?.fen_before || !boardRef.current) return;
    setCoachLineActive(true);
    setCoachLineStepIndex(-1);
    boardRef.current.playVariation(
      currentMoveData.fen_before,
      coachLine.moves,
      userColor,
      {
        stepDelayMs: 2000,
        onStep: (idx) => setCoachLineStepIndex(idx),
      }
    );
  }, [coachLine, currentMoveData, userColor]);

  // Handle analyze
  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const res = await fetch(`${API}/analyze-game`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ game_id: gameId })
      });
      
      if (!res.ok) throw new Error("Analysis failed");
      
      const data = await res.json();
      setAnalysis(data);
      toast.success("Analysis complete!");
    } catch (e) {
      toast.error("Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  // Handle ask about position
  const handleAsk = async () => {
    if (!askQuestion.trim() || askLoading) return;
    
    const question = askQuestion.trim();
    setAskQuestion("");
    setAskLoading(true);
    
    try {
      const res = await fetch(`${API}/game/${gameId}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          fen: currentMoveData?.fen_after || currentMoveData?.fen_before,
          fen_before: currentMoveData?.fen_before,
          question,
          played_move: currentMoveData?.move_san,
          move_number: currentMoveData?.move_number,
          user_color: userColor,
          conversation_history: conversationHistory.map(h => ({
            question: h.question,
            answer: h.answer
          }))
        })
      });
      
      if (!res.ok) throw new Error("Failed to get answer");
      
      const data = await res.json();
      setConversationHistory(prev => [...prev, {
        question,
        answer: data.answer,
        stockfish: data.stockfish
      }]);
    } catch (e) {
      toast.error("Could not get answer");
      setAskQuestion(question);
    } finally {
      setAskLoading(false);
    }
  };

  // Get severity color
  const getSeverityColor = (severity) => {
    switch (severity) {
      case "blunder": return "text-red-500 bg-red-500/10";
      case "mistake": return "text-orange-500 bg-orange-500/10";
      case "inaccuracy": return "text-yellow-500 bg-yellow-500/10";
      case "good": case "best": return "text-emerald-500 bg-emerald-500/10";
      case "opp_blunder": case "opp_mistake": return "text-blue-500 bg-blue-500/10";
      default: return "text-zinc-400 bg-zinc-500/10";
    }
  };

  const getSeverityIcon = (severity) => {
    switch (severity) {
      case "blunder": return <Zap className="w-4 h-4" />;
      case "mistake": return <AlertTriangle className="w-4 h-4" />;
      case "inaccuracy": return <AlertCircle className="w-4 h-4" />;
      case "good": case "best": return <CheckCircle2 className="w-4 h-4" />;
      case "opp_blunder": case "opp_mistake": return <Target className="w-4 h-4" />;
      default: return null;
    }
  };

  const getSeverityLabel = (severity, isUserMove) => {
    if (!isUserMove) {
      if (severity === "opp_blunder") return "Their blunder";
      if (severity === "opp_mistake") return "Their mistake";
      if (severity === "opp_inaccuracy") return "Their slip";
      return null;
    }
    switch (severity) {
      case "blunder": return "Blunder";
      case "mistake": return "Mistake";
      case "inaccuracy": return "Inaccuracy";
      case "good": return "Good";
      case "best": return "Best";
      default: return null;
    }
  };

  // Loading state
  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="max-w-6xl mx-auto py-4 px-4" data-testid="game-review-page">
        {/* Header - Minimal */}
        <div className="flex items-center gap-3 mb-4">
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={() => navigate("/lab")}
            className="h-8 w-8"
          >
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-semibold text-white truncate">
              vs {userColor === "white" ? game?.black_player : game?.white_player}
            </h1>
            <p className="text-xs text-zinc-500">
              {game?.result} · {game?.opening_name || "Unknown opening"}
            </p>
          </div>
          {!analysis && (
            <Button onClick={handleAnalyze} disabled={analyzing} size="sm">
              {analyzing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Brain className="w-4 h-4 mr-2" />}
              Analyze
            </Button>
          )}
        </div>

        {/* Game Overview — Phase analysis + Opening + Behaviors */}
        {coachReview && <GameOverview review={coachReview} navigate={navigate} />}

        {/* v72/v73 — Per-game patterns. Shows both hits (user played
            the pattern move) and misses (user played something worse).
            Each pattern row: human_name, hit/miss counts, and clickable
            move chips colored by outcome. Renders only when ≥1 event
            was recorded for this game. v1 voice — Mohit to tune. */}
        {patternMisses?.patterns?.length > 0 && (
          <Card className="bg-zinc-900/50 border-zinc-800 mb-4">
            <CardContent className="p-4 space-y-3">
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4 text-rose-400" />
                <h3 className="text-sm font-semibold text-zinc-200">
                  Patterns in this game
                </h3>
                <span className="text-xs text-zinc-500">
                  {patternMisses.total_hits > 0 && (
                    <span className="text-emerald-500">{patternMisses.total_hits} {patternMisses.total_hits === 1 ? 'hit' : 'hits'}</span>
                  )}
                  {patternMisses.total_hits > 0 && patternMisses.total_misses > 0 && <span>, </span>}
                  {patternMisses.total_misses > 0 && (
                    <span className="text-rose-400">{patternMisses.total_misses} {patternMisses.total_misses === 1 ? 'miss' : 'misses'}</span>
                  )}
                </span>
              </div>
              <ul className="space-y-2">
                {patternMisses.patterns.slice(0, 8).map((p) => (
                  <li
                    key={p.pattern_id}
                    className="text-sm text-zinc-300 flex items-start gap-2"
                  >
                    <span className="mt-0.5 text-xs font-mono whitespace-nowrap">
                      {p.hit_count > 0 && <span className="text-emerald-500">✓{p.hit_count}</span>}
                      {p.hit_count > 0 && p.miss_count > 0 && <span className="text-zinc-600 mx-1">/</span>}
                      {p.miss_count > 0 && <span className="text-rose-400">×{p.miss_count}</span>}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-zinc-200">{p.human_name}</div>
                      {p.short_description && (
                        <div className="text-xs text-zinc-500 mt-0.5">{p.short_description}</div>
                      )}
                      {p.moves?.length > 0 && (
                        <div className="text-xs text-zinc-500 mt-1 flex flex-wrap gap-x-2 items-center">
                          {p.moves.map((m, i) => {
                            const idx = (m.move_number - 1) * 2 + (userColor === 'black' ? 1 : 0);
                            const isHit = m.outcome === 'hit';
                            return (
                              <button
                                key={i}
                                onClick={() => {
                                  boardRef.current?.goToMove?.(idx);
                                  setCurrentMoveIndex(idx);
                                }}
                                className={`font-mono underline-offset-2 hover:underline ${
                                  isHit
                                    ? "text-emerald-400 hover:text-emerald-300"
                                    : "text-rose-300 hover:text-rose-200"
                                }`}
                                title={`Jump to move ${m.move_number} (${m.outcome})`}
                              >
                                {isHit ? "✓" : "×"} m{m.move_number} {m.move_san}
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        {/* v71 — Board patterns across the game. Surfaces only when at
            least one trend persisted across ≥3 user moves; otherwise
            silent. Geometry-level game flow that no per-move caption
            can show. */}
        {boardSummary?.trends?.length > 0 && (
          <Card className="bg-zinc-900/50 border-zinc-800 mb-4">
            <CardContent className="p-4 space-y-3">
              <div className="flex items-center gap-2">
                <Target className="w-4 h-4 text-sky-400" />
                <h3 className="text-sm font-semibold text-zinc-200">
                  Board patterns across the game
                </h3>
                <span className="text-xs text-zinc-500">
                  ({boardSummary.user_move_count} user moves)
                </span>
              </div>
              <ul className="space-y-2">
                {boardSummary.trends.slice(0, 4).map((t) => (
                  <li
                    key={t.fact_id}
                    className="text-sm text-zinc-300 flex items-start gap-2"
                  >
                    <span className="text-sky-400 mt-0.5">•</span>
                    <div className="flex-1 min-w-0">
                      <span>{t.label}</span>
                      {Array.isArray(t.move_numbers) && t.move_numbers.length > 0 && (
                        <span className="ml-2 text-xs text-zinc-500">
                          (m{t.move_numbers[0]}{t.move_numbers.length > 1 ? `–m${t.move_numbers[t.move_numbers.length - 1]}` : ''})
                        </span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        {/* Main Content - Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">

          {/* LEFT: Board + Coaching (3 cols) */}
          <div className="lg:col-span-3 space-y-4">
            
            {/* Chess Board */}
            <Card className="bg-zinc-900/50 border-zinc-800">
              <CardContent className="p-4">
                {analyzing ? (
                  <div className="flex flex-col items-center justify-center py-20">
                    <div className="relative">
                      <div className="w-16 h-16 rounded-full border-4 border-primary border-t-transparent animate-spin" />
                      <Brain className="w-8 h-8 text-primary absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
                    </div>
                    <p className="mt-4 text-sm text-zinc-400">Analyzing game...</p>
                  </div>
                ) : (
                  <ChessBoardViewer 
                    ref={boardRef}
                    pgn={pgn} 
                    userColor={userColor} 
                    onMoveChange={setCurrentMoveIndex}
                  />
                )}
              </CardContent>
            </Card>

            {/* Coaching Panel - The Heart of Review */}
            {analysis && (
              <Card className="bg-zinc-900/50 border-zinc-800">
                <CardContent className="p-4">
                  {decryptionStatus === "generating" ? (
                    <div className="flex items-center gap-3 py-6">
                      <Loader2 className="w-5 h-5 animate-spin text-primary" />
                      <div>
                        <p className="text-sm font-medium">Coach is analyzing...</p>
                        <p className="text-xs text-zinc-500">This takes about 45 seconds</p>
                      </div>
                    </div>
                  ) : currentMoveData ? (
                    <div className="space-y-4">
                      {/* Move Header */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-2xl font-bold text-white">
                            {currentMoveData.move_number}. {currentMoveData.move_san}
                          </span>
                          {getSeverityLabel(currentMoveData.severity, currentMoveData.is_user_move) && (
                            <span className={`text-xs px-2 py-1 rounded-full flex items-center gap-1 ${getSeverityColor(currentMoveData.severity)}`}>
                              {getSeverityIcon(currentMoveData.severity)}
                              {getSeverityLabel(currentMoveData.severity, currentMoveData.is_user_move)}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setUseLlmCaption(v => !v)}
                            className={`px-2 py-0.5 rounded text-[10px] font-medium border ${
                              useLlmCaption
                                ? "bg-sky-500 text-white border-transparent"
                                : "bg-zinc-800 text-zinc-400 border-zinc-700"
                            }`}
                            title="Toggle between LLM-polished caption and deterministic template"
                          >
                            {useLlmCaption ? "LLM" : "Template"}
                          </button>
                          <span className="text-xs text-zinc-500 capitalize">
                            {currentMoveData.phase}
                          </span>
                        </div>
                      </div>

                      {/* Main Caption: prefer caption_llm when toggle ON
                          and value non-empty; else fall back to caption;
                          else narrative (legacy). */}
                      <p className="text-sm text-zinc-300 leading-relaxed">
                        {(useLlmCaption && currentMoveData.caption_llm)
                          || currentMoveData.caption
                          || currentMoveData.narrative}
                      </p>

                      {/* Pattern Spotted — visual shape detector layer.
                          Only renders on moves where a shape was detected
                          (one teaching moment per shape type per game). */}
                      {currentMoveShapes.length > 0 && (
                        <div className="p-3 rounded-lg bg-violet-500/5 border border-violet-500/20">
                          <div className="flex items-start gap-2">
                            <Target className="w-4 h-4 text-violet-400 mt-0.5 flex-shrink-0" />
                            <div className="flex-1 min-w-0">
                              <div className="text-xs uppercase tracking-wide text-violet-400 font-medium mb-1">
                                Pattern spotted
                              </div>
                              <p className="text-sm text-zinc-200 leading-relaxed">
                                {currentMoveShapes[0].coach_line}
                              </p>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Your Plan Now */}
                      {currentMoveData.your_plan_now && (
                        <div className="p-3 rounded-lg bg-primary/5 border border-primary/20">
                          <p className="text-sm">
                            <span className="text-primary font-medium">→ </span>
                            {currentMoveData.your_plan_now}
                          </p>
                        </div>
                      )}

                      {/* Best Move (if user made a mistake) */}
                      {currentMoveData.is_user_move &&
                       currentMoveData.best_move_san &&
                       currentMoveData.severity !== "good" &&
                       currentMoveData.severity !== "best" && (
                        <div className="flex items-center gap-2 text-sm flex-wrap">
                          <span className="text-zinc-500">Best was:</span>
                          <span className="font-mono text-emerald-400">{currentMoveData.best_move_san}</span>
                        </div>
                      )}

                      {/* v79.1 — Play this line button. Renders for
                          ANY move with a coach line available (user
                          mistake OR opp mistake). Separate from the
                          "Best was:" block so opp moves get it too. */}
                      {coachLine && !coachLineActive && (
                        <div>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-xs text-amber-400 hover:text-amber-300 hover:bg-amber-500/10"
                            onClick={handlePlayCoachLine}
                            title="Watch this line play out on the board"
                          >
                            <PlayCircle className="w-3.5 h-3.5 mr-1" />
                            Play this line
                          </Button>
                        </div>
                      )}

                      {/* v70 — "Play this line" step list. Renders only
                          while playback is active OR when there's a
                          trap line (so the user can scan the curated
                          per-step text). For PV lines without authored
                          explanations, only the moves list is shown. */}
                      {coachLine && coachLineActive && (
                        <div className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/20 space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-xs uppercase tracking-wide text-amber-400 font-medium">
                              {coachLine.kind === "trap" ? "Trap line"
                                : coachLine.kind === "punishment" ? "Punishment line"
                                : "Engine line"}
                            </span>
                            <button
                              onClick={() => {
                                boardRef.current?.cancelVariation?.();
                                boardRef.current?.goToMove?.(currentMoveIndex);
                                setCoachLineActive(false);
                                setCoachLineStepIndex(-1);
                              }}
                              className="text-xs text-zinc-500 hover:text-zinc-300"
                            >
                              Back to game
                            </button>
                          </div>
                          <ol className="space-y-1">
                            {coachLine.steps.map((s, i) => {
                              const isCurrent = i === coachLineStepIndex;
                              const isPlayed = i <= coachLineStepIndex;
                              return (
                                <li
                                  key={`${i}-${s.move}`}
                                  className={`text-xs leading-relaxed ${
                                    isCurrent
                                      ? "text-amber-200"
                                      : isPlayed
                                      ? "text-zinc-300"
                                      : "text-zinc-500"
                                  }`}
                                >
                                  <span className="font-mono mr-2">{i + 1}. {s.move}</span>
                                  {s.explanation && (
                                    <span>{s.explanation}</span>
                                  )}
                                </li>
                              );
                            })}
                          </ol>
                        </div>
                      )}

                      {/* Transferable Learning */}
                      {currentMoveData.plan?.transferable_learning && (
                        <div className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/20">
                          <div className="flex items-start gap-2">
                            <Lightbulb className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
                            <p className="text-sm text-amber-200/80">
                              {currentMoveData.plan.transferable_learning}
                            </p>
                          </div>
                        </div>
                      )}

                      {/* Ask Button */}
                      <div className="pt-2">
                        {!showAsk ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setShowAsk(true)}
                            className="text-zinc-400 hover:text-white"
                          >
                            <MessageCircle className="w-4 h-4 mr-2" />
                            Ask about this position
                          </Button>
                        ) : (
                          <div className="space-y-3 p-3 rounded-lg bg-zinc-800/50 border border-zinc-700">
                            <div className="flex items-center justify-between">
                              <span className="text-xs text-zinc-500">Ask your coach</span>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6"
                                onClick={() => setShowAsk(false)}
                              >
                                <X className="w-3 h-3" />
                              </Button>
                            </div>
                            
                            {/* Conversation History */}
                            {conversationHistory.length > 0 && (
                              <div className="space-y-2 max-h-40 overflow-y-auto">
                                {conversationHistory.map((ex, i) => (
                                  <div key={i} className="space-y-1">
                                    <p className="text-xs text-zinc-400">Q: {ex.question}</p>
                                    <p className="text-sm text-zinc-200">{ex.answer}</p>
                                  </div>
                                ))}
                              </div>
                            )}
                            
                            {/* Quick suggestions */}
                            <div className="flex flex-wrap gap-1">
                              {["Why is this bad?", "What if I played differently?", "What's the idea here?"].map(q => (
                                <button
                                  key={q}
                                  onClick={() => setAskQuestion(q)}
                                  className="text-xs px-2 py-1 rounded bg-zinc-700 text-zinc-300 hover:bg-zinc-600"
                                >
                                  {q}
                                </button>
                              ))}
                            </div>
                            
                            {/* Input */}
                            <div className="flex gap-2">
                              <Input
                                value={askQuestion}
                                onChange={(e) => setAskQuestion(e.target.value)}
                                placeholder="Ask anything..."
                                className="flex-1 text-sm bg-zinc-800 border-zinc-700"
                                onKeyDown={(e) => e.key === "Enter" && handleAsk()}
                                disabled={askLoading}
                              />
                              <Button size="sm" onClick={handleAsk} disabled={askLoading || !askQuestion.trim()}>
                                {askLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                              </Button>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="py-8 text-center text-zinc-500">
                      <Brain className="w-8 h-8 mx-auto mb-2 opacity-30" />
                      <p className="text-sm">Navigate through the game to see coaching</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>

          {/* RIGHT: Move List (2 cols) */}
          <div className="lg:col-span-2">
            <Card className="bg-zinc-900/50 border-zinc-800 h-full">
              <CardContent className="p-0">
                <div className="p-3 border-b border-zinc-800">
                  <h3 className="text-sm font-medium text-zinc-400">Moves</h3>
                </div>
                <ScrollArea className="h-[600px]">
                  <div className="p-2">
                    {moves.length > 0 ? (
                      <div className="space-y-0.5">
                        {moves.map((move, idx) => {
                          const isActive = idx === currentMoveIndex;
                          const hasSeverity = move.severity && move.severity !== "context" && move.severity !== "good";
                          const isUserMistake = move.is_user_move && hasSeverity;
                          const isOppMistake = !move.is_user_move && (move.severity === "opp_blunder" || move.severity === "opp_mistake");
                          
                          return (
                            <button
                              key={idx}
                              onClick={() => {
                                setCurrentMoveIndex(idx);
                                boardRef.current?.goToMove(idx);
                              }}
                              className={`w-full text-left px-3 py-2 rounded-lg flex items-center gap-2 transition-colors ${
                                isActive 
                                  ? "bg-primary/20 border border-primary/30" 
                                  : isUserMistake
                                    ? "bg-red-500/5 hover:bg-red-500/10 border border-transparent"
                                    : isOppMistake
                                      ? "bg-blue-500/5 hover:bg-blue-500/10 border border-transparent"
                                      : "hover:bg-zinc-800 border border-transparent"
                              }`}
                            >
                              {/* Move number + notation */}
                              <span className={`font-mono text-sm ${
                                isActive ? "text-white" : "text-zinc-400"
                              }`}>
                                {move.move_number}.{!move.is_white && ".."} {move.move_san}
                              </span>
                              
                              {/* Severity badge */}
                              {(isUserMistake || isOppMistake) && (
                                <span className={`ml-auto flex items-center gap-1 text-xs ${getSeverityColor(move.severity)}`}>
                                  {getSeverityIcon(move.severity)}
                                  {move.is_user_move ? (
                                    move.severity === "blunder" ? "!" : 
                                    move.severity === "mistake" ? "?" : "?!"
                                  ) : (
                                    "opportunity"
                                  )}
                                </span>
                              )}
                              
                              {/* Arrow for active */}
                              {isActive && (
                                <ChevronRight className="w-4 h-4 text-primary ml-auto" />
                              )}
                            </button>
                          );
                        })}
                      </div>
                    ) : analysis ? (
                      <div className="py-8 text-center text-zinc-500">
                        <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" />
                        <p className="text-xs">Loading moves...</p>
                      </div>
                    ) : (
                      <div className="py-8 text-center text-zinc-500">
                        <p className="text-sm">Analyze the game first</p>
                      </div>
                    )}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default GameAnalysis;
